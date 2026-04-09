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
            request_length=1,
            arrival_tick=1,     # joins at tick 1
        )
    ],
    total_ticks= 20,
    tick_duration_ms=1000,   # animation speed (lower = faster)
)

# config = SimulationConfig(
#     clients=[
#         ClientConfig(
#             name="Client A",
#             weight=2,
#             request_length=2,   # each recurring request takes 2 ticks
#             arrival_tick=0,     # joins at tick 0
#         ),
#         ClientConfig(
#             name="Client B",
#             weight=2,
#             request_length=1,
#             arrival_tick=1,     # joins at tick 1
#         ),
#         ClientConfig(
#             name="Client C",
#             weight=4,
#             request_length=1,
#             arrival_tick=4, 
#         )
#     ],
#     total_ticks= 20,
#     tick_duration_ms=1000,   # animation speed (lower = faster)
# )

# config = SimulationConfig(
#     clients=[
#         ClientConfig(
#             name="Client A",
#             weight=2,
#             request_length=2,   # each recurring request takes 2 ticks
#             arrival_tick=0,     # joins at tick 0
#         ),
#         ClientConfig(
#             name="Client B",
#             weight=2,
#             request_length=1,
#             arrival_tick=1,     # joins at tick 1
#         ),
#         ClientConfig(
#             name="Client C",
#             weight=4,
#             request_length=1,
#             arrival_tick=4,     # joins at tick 4
#         ),
#                 ClientConfig(
#             name="Client D",
#             weight=1,
#             request_length=3,
#             arrival_tick=6,     # joins at tick 6
#         ),
#                 ClientConfig(
#             name="Client E",
#             weight=8,
#             request_length=3,
#             arrival_tick=10,     # joins at tick 10
#         ),
#     ],
#     total_ticks= 50,
#     tick_duration_ms=1000,   # animation speed (lower = faster)
# )


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
