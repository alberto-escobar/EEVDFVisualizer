from __future__ import annotations

from dataclasses import dataclass, field

from config import ClientConfig


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

@dataclass
class Request:
    """A single service request from a client."""
    client_index: int
    length: int
    remaining: int = 0
    eligible_time: float = 0.0   # virtual eligible time (ve)
    deadline: float = 0.0        # virtual deadline (vd)

    def __post_init__(self):
        self.remaining = self.length


@dataclass
class Client:
    """Runtime state for one client inside the scheduler."""
    index: int
    name: str
    weight: int
    request_length: int
    arrival_tick: int
    active: bool = False         # True once the client has joined
    pending: list[Request] = field(default_factory=list)
    last_deadline: float = 0.0   # vd of last admitted request
    virtual_time_at_join: float = 0.0  # V(t) when client became active
    service_received: int = 0          # actual ticks of service received


# ---------------------------------------------------------------------------
# Per-tick snapshot returned to the visualizer
# ---------------------------------------------------------------------------

@dataclass
class RequestSnapshot:
    eligible_time: float
    deadline: float
    remaining: int
    length: int


@dataclass
class ClientSnapshot:
    name: str
    weight: int
    active: bool
    pending_count: int
    current_request: RequestSnapshot | None
    lag: float = 0.0


@dataclass
class TickState:
    """Complete scheduler state at one tick — used by the visualizer."""
    real_time: int
    virtual_time: float
    total_weight: int
    running_client: int | None
    clients: list[ClientSnapshot]
    phase: str = "running"   # "deciding" | "running"


# ---------------------------------------------------------------------------
# EEVDF Scheduler
# ---------------------------------------------------------------------------

class EEVDFScheduler:
    """Earliest Eligible Virtual Deadline First scheduler.

    Each client automatically receives a new request of its configured
    length as soon as its previous request completes (recurring model).

    Usage:
        scheduler = EEVDFScheduler(client_configs)
        history   = scheduler.run(total_ticks)
    """

    def __init__(self, client_configs: list[ClientConfig]):
        self.clients: list[Client] = [
            Client(
                index=i,
                name=cfg.name,
                weight=cfg.weight,
                request_length=cfg.request_length,
                arrival_tick=cfg.arrival_tick,
            )
            for i, cfg in enumerate(client_configs)
        ]
        self.real_time: int = 0
        self.virtual_time: float = 0.0

    # -- properties ---------------------------------------------------------

    @property
    def total_weight(self) -> int:
        """Sum of weights of all active clients."""
        return sum(c.weight for c in self.clients if c.active)

    # -- internal helpers ---------------------------------------------------

    def _admit_new_request(self, client: Client) -> None:
        """Create a new request for *client* and compute its ve / vd."""
        req = Request(client_index=client.index, length=client.request_length)
        req.eligible_time = max(self.virtual_time, client.last_deadline)
        req.deadline = req.eligible_time + req.length / client.weight
        client.last_deadline = req.deadline
        client.pending.append(req)

    def _activate_clients(self) -> None:
        """Activate clients whose arrival_tick has been reached and
        ensure every active client has a pending request."""
        for client in self.clients:
            if not client.active and client.arrival_tick <= self.real_time:
                client.active = True
                client.virtual_time_at_join = self.virtual_time
                self._admit_new_request(client)
            elif client.active and not client.pending:
                self._admit_new_request(client)

    def _select_client(self) -> int | None:
        """Pick the eligible client with the earliest virtual deadline.
        Ties are broken by lag — prefer the most under-served client
        (highest lag)."""
        best_index: int | None = None
        best_deadline = float("inf")
        best_lag = float("-inf")
        best_name = ""

        for client in self.clients:
            if not client.pending:
                continue
            req = client.pending[0]
            # Eligible: ve <= current virtual time
            if req.eligible_time <= self.virtual_time + 1e-9:
                lag = self._compute_lag(client)
                if (req.deadline < best_deadline - 1e-9 or
                        (abs(req.deadline - best_deadline) < 1e-9 and
                         lag > best_lag + 1e-9) or
                        (abs(req.deadline - best_deadline) < 1e-9 and
                         abs(lag - best_lag) < 1e-9 and
                         client.name > best_name)):
                    best_index = client.index
                    best_deadline = req.deadline
                    best_lag = lag
                    best_name = client.name

        return best_index

    def _compute_lag(self, client: Client) -> float:
        """Compute lag for a client: ideal fair-share service minus actual.

        lag = weight * (V(now) - V(join)) - service_received
        Positive = under-served, negative = over-served.
        """
        if not client.active:
            return 0.0
        ideal = client.weight * (self.virtual_time - client.virtual_time_at_join)
        return ideal - client.service_received

    def _snapshot(self, running: int | None, phase: str = "running") -> TickState:
        client_snaps: list[ClientSnapshot] = []
        for c in self.clients:
            req_snap = None
            if c.pending:
                r = c.pending[0]
                req_snap = RequestSnapshot(
                    eligible_time=round(r.eligible_time, 4),
                    deadline=round(r.deadline, 4),
                    remaining=r.remaining,
                    length=r.length,
                )
            client_snaps.append(ClientSnapshot(
                name=c.name,
                weight=c.weight,
                active=c.active,
                pending_count=len(c.pending),
                current_request=req_snap,
                lag=round(self._compute_lag(c), 4),
            ))
        return TickState(
            real_time=self.real_time,
            virtual_time=round(self.virtual_time, 4),
            total_weight=self.total_weight,
            running_client=running,
            clients=client_snaps,
            phase=phase,
        )

    # -- public API ---------------------------------------------------------

    def run(self, total_ticks: int) -> list[TickState]:
        """Simulate *total_ticks* ticks and return per-tick state history.

        Each tick emits two TickState entries:
          1. phase="deciding" — state after activating clients but before
             selecting who runs.  The visualizer auto-pauses here so the
             presenter can ask the audience who they think runs next.
          2. phase="running"  — state showing which client was actually
             selected to run this tick.
        """
        history: list[TickState] = []

        for t in range(total_ticks):
            self.real_time = t

            # 1. Activate new clients & give idle clients a fresh request.
            self._activate_clients()

            # 2. DECIDING snapshot — shown before the selection is revealed.
            history.append(self._snapshot(None, phase="deciding"))

            # 3. Pick which client to run this tick.
            running = self._select_client()

            # 4. RUNNING snapshot — shows who actually runs.
            history.append(self._snapshot(running, phase="running"))

            # 5. Capture weight *before* execution (client is active this tick).
            w = self.total_weight

            # 6. Execute one tick of work.
            if running is not None:
                client = self.clients[running]
                req = client.pending[0]
                req.remaining -= 1
                client.service_received += 1
                if req.remaining <= 0:
                    client.pending.pop(0)

            # 7. Advance virtual time using pre-execution weight.
            if w > 0:
                self.virtual_time += 1.0 / w

        return history
