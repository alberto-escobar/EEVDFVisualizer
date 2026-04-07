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

# config = SimulationConfig(
#     clients=[
#         ClientConfig(
#             name="Interactive",
#             weight=3,            # higher weight = more CPU share
#             request_length=1,    # short bursts
#             arrival_tick=0,
#         ),
#         ClientConfig(
#             name="Batch 1",
#             weight=1,            # normal weight
#             request_length=4,
#             arrival_tick=0,
#         ),
#         ClientConfig(
#             name="Batch 2",
#             weight=1,
#             request_length=4,
#             arrival_tick=0,
#         ),
#         ClientConfig(
#             name="Batch 3",
#             weight=1,            # low weight (like nice 5 in CFS)
#             request_length=4,
#             arrival_tick=0,
#         ),
#         ClientConfig(
#             name="Batch 4",
#             weight=1,
#             request_length=4,
#             arrival_tick=0,
#         ),
#     ],
#     total_ticks=40,
#     tick_duration_ms=2000,   # animation speed (lower = faster)
# )

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
            request_length=1,
            arrival_tick=1,     # joins at tick 1
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
