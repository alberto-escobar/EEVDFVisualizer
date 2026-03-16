from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.animation import FuncAnimation

from config import SimulationConfig
from scheduler import TickState


# Distinct colors for up to 10 clients.
CLIENT_COLORS = [
    "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3",
    "#937860", "#DA8BC3", "#8C8C8C", "#CCB974", "#64B5CD",
]


class Visualizer:
    """Animated EEVDF schedule viewer driven by a list of TickState snapshots."""

    def __init__(self, config: SimulationConfig, history: list[TickState]):
        self.config = config
        self.history = history
        self.num_clients = len(config.clients)
        self.total_ticks = config.total_ticks
        self.colors = CLIENT_COLORS[: self.num_clients]

        # ---- figure layout ------------------------------------------------
        # Left 70%: timelines.  Right 30%: state panel.
        self.fig = plt.figure(figsize=(14, 3 + 1.2 * self.num_clients))
        gs = gridspec.GridSpec(
            1, 2, width_ratios=[7, 3], wspace=0.05, figure=self.fig,
        )

        # Timeline axes: one row per client + 2 for real/virtual time.
        n_rows = self.num_clients + 2
        inner_gs = gs[0].subgridspec(n_rows, 1, hspace=0.4)

        self.ax_real = self.fig.add_subplot(inner_gs[0])
        self.ax_virt = self.fig.add_subplot(inner_gs[1])
        self.ax_clients: list[plt.Axes] = [
            self.fig.add_subplot(inner_gs[i + 2])
            for i in range(self.num_clients)
        ]

        # State panel (text only, no axes).
        self.ax_state = self.fig.add_subplot(gs[1])
        self.ax_state.axis("off")

        self._setup_axes()

        # Precompute virtual time at each tick boundary (after tick executes).
        self._vt_boundaries = self._compute_vt_boundaries()

        # Animated artists that we update each frame.
        self.time_line = self.ax_real.axvline(1, color="red", lw=1.5)
        self.virt_line = self.ax_virt.axvline(1, color="red", lw=1.5)
        self.state_text = self.ax_state.text(
            0.05, 0.95, "", transform=self.ax_state.transAxes,
            fontsize=10, verticalalignment="top", fontfamily="monospace",
        )

        # Store patches we've already drawn so we don't duplicate.
        self._drawn_ticks: set[int] = set()

    # ---- axis setup -------------------------------------------------------

    def _compute_vt_boundaries(self) -> list[float]:
        """Compute virtual time value at each tick boundary.

        Returns a list of length total_ticks + 1 where entry i is the
        virtual time at real time i (i.e. after tick i-1 completes,
        or 0 for the initial boundary).
        """
        boundaries = [0.0]
        for s in self.history:
            vt = s.virtual_time
            if s.total_weight > 0:
                vt += 1.0 / s.total_weight
            boundaries.append(round(vt, 4))
        return boundaries

    def _setup_axes(self) -> None:
        tick_range = (0, self.total_ticks)

        # Real time axis.
        self.ax_real.set_xlim(*tick_range)
        self.ax_real.set_ylim(0, 1)
        self.ax_real.set_yticks([])
        self.ax_real.set_ylabel("Real\nTime", rotation=0, labelpad=40, va="center")
        self.ax_real.set_title("EEVDF Scheduler Visualization", fontsize=13, fontweight="bold")
        self.ax_real.set_xticks(range(self.total_ticks + 1))

        # Virtual time axis — same horizontal space as real time, but
        # labeled with virtual time values at each tick boundary.
        # This shows how virtual time stretches / compresses.
        self.ax_virt.set_xlim(*tick_range)
        self.ax_virt.set_ylim(0, 1)
        self.ax_virt.set_yticks([])
        self.ax_virt.set_ylabel("Virtual\nTime", rotation=0, labelpad=40, va="center")
        # Initially empty — tick labels are added as the animation progresses.
        self.ax_virt.set_xticks([])

        # Per-client axes.
        for i, ax in enumerate(self.ax_clients):
            ax.set_xlim(*tick_range)
            ax.set_ylim(0, 1)
            ax.set_yticks([])
            name = self.config.clients[i].name
            ax.set_ylabel(name, rotation=0, labelpad=40, va="center",
                          color=self.colors[i], fontweight="bold")
            ax.set_xticks(range(self.total_ticks + 1))
            if i < self.num_clients - 1:
                ax.tick_params(labelbottom=False)
            else:
                ax.set_xlabel("Real Time (ticks)")

    # ---- per-frame update -------------------------------------------------

    def _update(self, frame: int):
        state = self.history[frame]

        # Draw blocks for all ticks up to current frame.
        for t in range(frame + 1):
            if t in self._drawn_ticks:
                continue
            self._drawn_ticks.add(t)
            s = self.history[t]
            if s.running_client is not None:
                ci = s.running_client
                rect = mpatches.FancyBboxPatch(
                    (t + 0.05, 0.1), 0.9, 0.8,
                    boxstyle="round,pad=0.05",
                    facecolor=self.colors[ci], edgecolor="white", lw=0.8,
                )
                self.ax_clients[ci].add_patch(rect)

        # Both red lines move together at x = real_time + 1
        # (right edge of the tick that just completed).
        x = state.real_time + 1
        self.time_line.set_xdata([x, x])
        self.virt_line.set_xdata([x, x])

        # Update virtual time tick labels up to the current boundary.
        positions = list(range(frame + 2))  # 0 .. frame+1
        labels = [self._fmt_vt(self._vt_boundaries[i]) for i in positions]
        self.ax_virt.set_xticks(positions)
        self.ax_virt.set_xticklabels(labels)

        # State panel text.
        lines = self._build_state_text(state)
        self.state_text.set_text(lines)

        return []

    def _build_state_text(self, state: TickState) -> str:
        sep = "─" * 28
        lines = [
            "  Scheduler State",
            sep,
            f"  Real Time    : {state.real_time}",
            f"  Virtual Time : {state.virtual_time:.4f}",
            f"  Total Weight : {state.total_weight}",
            f"  Running      : {self._running_label(state)}",
            sep,
        ]

        for i, cs in enumerate(state.clients):
            marker = " ▶" if state.running_client == i else "  "
            status = "" if cs.active else "  [not joined]"
            lines.append(f"{marker} {cs.name}  (w={cs.weight}){status}")
            if cs.current_request is not None:
                r = cs.current_request
                lines.append(f"    ve={r.eligible_time:.4f}  vd={r.deadline:.4f}")
                lines.append(f"    remaining={r.remaining}/{r.length}")
                lines.append(f"    queued={cs.pending_count}")
            elif cs.active:
                lines.append("    (between requests)")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _fmt_vt(v: float) -> str:
        """Format a virtual time value truncated to 2 decimal places."""
        if v == int(v):
            return str(int(v))
        return f"{v:.2f}"

    @staticmethod
    def _running_label(state: TickState) -> str:
        if state.running_client is None:
            return "(idle)"
        return state.clients[state.running_client].name

    # ---- public API -------------------------------------------------------

    def play(self) -> None:
        """Launch the animated visualization window."""
        self.anim = FuncAnimation(
            self.fig,
            self._update,
            frames=len(self.history),
            interval=self.config.tick_duration_ms,
            repeat=False,
        )
        plt.tight_layout()
        plt.show()
