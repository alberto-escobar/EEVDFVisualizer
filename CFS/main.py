"""CFS Scheduler Visualizer — entry point.

Edit the configuration below to change tasks, nice values, and requests,
then run:  python main.py
"""

from config import TaskConfig, SimulationConfig
from scheduler import CFSScheduler
from visualizer import Visualizer


# ──────────────────────────────────────────────────────────────────────────
#  CONFIGURATION — edit this section to set up your scenario
#
#  nice values: -20 (highest priority) to 19 (lowest priority), default 0
#  Lower nice = more CPU share.  Each level is ~10% difference.
# ──────────────────────────────────────────────────────────────────────────

config = SimulationConfig(
    tasks=[
        TaskConfig(
            name="Interactive",
            nice=-5,             # higher priority
            request_length=1,
            arrival_tick=0,
        ),
        TaskConfig(
            name="Batch 1",
            nice=0,              # normal priority
            request_length=4,
            arrival_tick=0,
        ),
        TaskConfig(
            name="Batch 2",
            nice=0,
            request_length=4,
            arrival_tick=0,
        ),
        TaskConfig(
            name="Batch 3",
            nice=5,              # lower priority
            request_length=4,
            arrival_tick=0,
        ),
        TaskConfig(
            name="Batch 4",
            nice=5,
            request_length=4,
            arrival_tick=0,
        ),
    ],
    total_ticks=40,
    tick_duration_ms=2000,   # animation speed (lower = faster)
)


# ──────────────────────────────────────────────────────────────────────────
#  RUN
# ──────────────────────────────────────────────────────────────────────────

def main():
    scheduler = CFSScheduler(config.tasks)
    history = scheduler.run(config.total_ticks)
    viz = Visualizer(config, history)
    viz.play()


if __name__ == "__main__":
    main()
