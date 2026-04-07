from dataclasses import dataclass


@dataclass
class TaskConfig:
    """Configuration for a single task in the CFS scheduler.

    Attributes:
        name: Display name for this task.
        nice: Nice value (-20 to 19).  Lower = higher priority / more CPU.
              Default 0 is normal priority.
        request_length: Service ticks each recurring request needs.
        arrival_tick: When this task joins the system.
    """
    name: str
    nice: int = 0
    request_length: int = 1
    arrival_tick: int = 0


@dataclass
class SimulationConfig:
    """Top-level configuration for the CFS simulation.

    Attributes:
        tasks: List of task configurations.
        total_ticks: How many real time ticks to simulate.
        tick_duration_ms: Milliseconds per tick in the animation.
    """
    tasks: list[TaskConfig]
    total_ticks: int = 30
    tick_duration_ms: int = 600
