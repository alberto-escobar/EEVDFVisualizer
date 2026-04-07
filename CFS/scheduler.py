from __future__ import annotations

from dataclasses import dataclass, field

from config import TaskConfig


# ---------------------------------------------------------------------------
# Nice-to-weight table (from the Linux kernel: kernel/sched/core.c)
#
# Each nice level corresponds to roughly a 10% difference in CPU share
# (a factor of ~1.25 between adjacent levels).  Nice 0 = weight 1024.
# ---------------------------------------------------------------------------

NICE_TO_WEIGHT: dict[int, int] = {
    -20: 88761, -19: 71755, -18: 56483, -17: 46273, -16: 36291,
    -15: 29154, -14: 23254, -13: 18705, -12: 14949, -11: 11916,
    -10:  9548,  -9:  7620,  -8:  6100,  -7:  4904,  -6:  3906,
     -5:  3121,  -4:  2501,  -3:  1991,  -2:  1586,  -1:  1277,
      0:  1024,   1:   820,   2:   655,   3:   526,   4:   423,
      5:   335,   6:   272,   7:   215,   8:   172,   9:   137,
     10:   110,  11:    87,  12:    70,  13:    56,  14:    45,
     15:    36,  16:    29,  17:    23,  18:    18,  19:    15,
}

NICE_0_WEIGHT = 1024  # reference weight for nice 0


def nice_to_weight(nice: int) -> int:
    """Convert a nice value to a scheduling weight."""
    return NICE_TO_WEIGHT[max(-20, min(19, nice))]


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------

@dataclass
class Request:
    """A single service request from a task."""
    task_index: int
    length: int
    remaining: int = 0

    def __post_init__(self):
        self.remaining = self.length


@dataclass
class Task:
    """Runtime state for one task inside the scheduler."""
    index: int
    name: str
    nice: int
    weight: int
    request_length: int
    arrival_tick: int
    active: bool = False
    pending: list[Request] = field(default_factory=list)
    vruntime: float = 0.0
    service_received: int = 0


# ---------------------------------------------------------------------------
# Per-tick snapshot returned to the visualizer
# ---------------------------------------------------------------------------

@dataclass
class RequestSnapshot:
    remaining: int
    length: int


@dataclass
class TaskSnapshot:
    name: str
    nice: int
    weight: int
    active: bool
    pending_count: int
    current_request: RequestSnapshot | None
    vruntime: float
    lag: float = 0.0


@dataclass
class TickState:
    """Complete scheduler state at one tick — used by the visualizer."""
    real_time: int
    min_vruntime: float
    total_weight: int
    running_task: int | None
    tasks: list[TaskSnapshot]


# ---------------------------------------------------------------------------
# CFS Scheduler
# ---------------------------------------------------------------------------

class CFSScheduler:
    """Completely Fair Scheduler simulation.

    CFS always picks the runnable task with the lowest virtual runtime
    (vruntime).  When a task runs for one tick its vruntime increases by:

        delta_vruntime = 1 * (NICE_0_WEIGHT / task_weight)

    Tasks with lower nice values have higher weights, so their vruntime
    grows more slowly and they get scheduled more often.

    Each task automatically receives a new request of its configured
    length as soon as its previous request completes (recurring model).

    Usage:
        scheduler = CFSScheduler(task_configs)
        history   = scheduler.run(total_ticks)
    """

    def __init__(self, task_configs: list[TaskConfig]):
        self.tasks: list[Task] = [
            Task(
                index=i,
                name=cfg.name,
                nice=cfg.nice,
                weight=nice_to_weight(cfg.nice),
                request_length=cfg.request_length,
                arrival_tick=cfg.arrival_tick,
            )
            for i, cfg in enumerate(task_configs)
        ]
        self.real_time: int = 0
        self.min_vruntime: float = 0.0

    # -- properties ---------------------------------------------------------

    @property
    def total_weight(self) -> int:
        return sum(t.weight for t in self.tasks if t.active)

    # -- internal helpers ---------------------------------------------------

    def _admit_new_request(self, task: Task) -> None:
        req = Request(task_index=task.index, length=task.request_length)
        task.pending.append(req)

    def _activate_tasks(self) -> None:
        for task in self.tasks:
            if not task.active and task.arrival_tick <= self.real_time:
                task.active = True
                task.vruntime = self.min_vruntime
                self._admit_new_request(task)
            elif task.active and not task.pending:
                self._admit_new_request(task)

    def _select_task(self) -> int | None:
        """Pick the runnable task with the smallest vruntime."""
        best_index: int | None = None
        best_vruntime = float("inf")

        for task in self.tasks:
            if not task.pending:
                continue
            if task.vruntime < best_vruntime - 1e-9:
                best_index = task.index
                best_vruntime = task.vruntime
        return best_index

    def _update_min_vruntime(self) -> None:
        """Advance min_vruntime to the smallest vruntime among runnable tasks."""
        active_vruntimes = [
            t.vruntime for t in self.tasks if t.active and t.pending
        ]
        if active_vruntimes:
            self.min_vruntime = max(self.min_vruntime, min(active_vruntimes))

    def _compute_lag(self, task: Task) -> float:
        """Compute lag: ideal fair-share service minus actual.

        ideal = (weight / total_weight) * elapsed_ticks
        lag   = ideal - service_received
        Positive = under-served.
        """
        if not task.active:
            return 0.0
        elapsed = self.real_time - task.arrival_tick
        tw = self.total_weight
        if tw == 0:
            return 0.0
        ideal = (task.weight / tw) * elapsed
        return ideal - task.service_received

    def _snapshot(self, running: int | None) -> TickState:
        task_snaps: list[TaskSnapshot] = []
        for t in self.tasks:
            req_snap = None
            if t.pending:
                r = t.pending[0]
                req_snap = RequestSnapshot(remaining=r.remaining, length=r.length)
            task_snaps.append(TaskSnapshot(
                name=t.name,
                nice=t.nice,
                weight=t.weight,
                active=t.active,
                pending_count=len(t.pending),
                current_request=req_snap,
                vruntime=round(t.vruntime, 4),
                lag=round(self._compute_lag(t), 4),
            ))
        return TickState(
            real_time=self.real_time,
            min_vruntime=round(self.min_vruntime, 4),
            total_weight=self.total_weight,
            running_task=running,
            tasks=task_snaps,
        )

    # -- public API ---------------------------------------------------------

    def run(self, total_ticks: int) -> list[TickState]:
        """Simulate *total_ticks* ticks and return per-tick state history."""
        history: list[TickState] = []

        for t in range(total_ticks):
            self.real_time = t

            # 1. Activate new tasks & give idle tasks a fresh request.
            self._activate_tasks()

            # 2. Pick which task to run this tick.
            running = self._select_task()

            # 3. Snapshot state *before* execution.
            history.append(self._snapshot(running))

            # 4. Execute one tick of work.
            if running is not None:
                task = self.tasks[running]
                req = task.pending[0]
                req.remaining -= 1
                task.service_received += 1
                # vruntime advances: delta * (NICE_0_WEIGHT / task_weight)
                task.vruntime += NICE_0_WEIGHT / task.weight
                if req.remaining <= 0:
                    task.pending.pop(0)

            # 5. Advance min_vruntime.
            self._update_min_vruntime()

        return history
