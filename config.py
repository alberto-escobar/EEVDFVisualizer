from dataclasses import dataclass


@dataclass
class ClientConfig:
    """Configuration for a single client in the EEVDF scheduler.

    Attributes:
        name: Display name for this client.
        weight: Scheduling weight (higher = larger CPU share).
        request_length: Service ticks each recurring request needs.
        arrival_tick: When this client joins the system.
    """
    name: str
    weight: int
    request_length: int
    arrival_tick: int = 0


@dataclass
class SimulationConfig:
    """Top-level configuration for the simulation.

    Attributes:
        clients: List of client configurations.
        total_ticks: How many real time ticks to simulate.
        tick_duration_ms: Milliseconds per tick in the animation.
    """
    clients: list[ClientConfig]
    total_ticks: int = 30
    tick_duration_ms: int = 600
