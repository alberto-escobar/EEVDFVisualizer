"""EEVDF Scheduler Visualizer — entry point.

Edit the configuration below to change clients, weights, and requests,
then run:  python main.py
"""

from config import ClientConfig, SimulationConfig
from scheduler import EEVDFScheduler
from visualizer import Visualizer


# ──────────────────────────────────────────────────────────────────────────
#  CONFIGURATION — edit this section to set up your scenario
# ──────────────────────────────────────────────────────────────────────────

config = SimulationConfig(
    clients=[
        ClientConfig(
            name="Client A",
            weight=2,
            request_length=2,   # each recurring request takes 2 ticks
            arrival_tick=0,     # joins at tick 0
        ),
        ClientConfig(
            name="Client B",
            weight=2,
            request_length=20,
            arrival_tick=0,     # joins at tick 1
        ),
    ],
    total_ticks=20,
    tick_duration_ms=2000,   # animation speed (lower = faster)
)


# ──────────────────────────────────────────────────────────────────────────
#  RUN
# ──────────────────────────────────────────────────────────────────────────

def main():
    scheduler = EEVDFScheduler(config.clients)
    history = scheduler.run(config.total_ticks)
    viz = Visualizer(config, history)
    viz.play()


if __name__ == "__main__":
    main()
