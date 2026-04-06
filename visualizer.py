from __future__ import annotations

import math

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

        # Precompute virtual time at each tick boundary (after tick executes).
        self._vt_boundaries = self._compute_vt_boundaries()
        self._max_vt = self._vt_boundaries[-1] if self._vt_boundaries[-1] > 0 else 1.0

        self._setup_axes()

        # Animated artists that we update each frame.
        self.time_line = self.ax_real.axvline(1, color="red", lw=1.5)
        self.virt_line = self.ax_virt.axvline(0, color="red", lw=1.5)
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

        # Virtual time axis — constant linear scale in virtual-time units.
        # The red line speeds up / slows down as total weight changes.
        self.ax_virt.set_xlim(0, self._max_vt)
        self.ax_virt.set_ylim(0, 1)
        self.ax_virt.set_yticks([])
        self.ax_virt.set_ylabel("Virtual\nTime", rotation=0, labelpad=40, va="center")
        # Choose nice evenly-spaced tick marks.
        vt_step = self._nice_step(self._max_vt, target_ticks=10)
        vt_ticks = self._arange_nice(0, self._max_vt, vt_step)
        self.ax_virt.set_xticks(vt_ticks)
        self.ax_virt.set_xticklabels([self._fmt_vt(v) for v in vt_ticks])

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

        # Real time red line moves at constant speed (1 per tick).
        x_real = state.real_time + 1
        self.time_line.set_xdata([x_real, x_real])

        # Virtual time red line moves to the actual virtual time value,
        # so it speeds up when fewer clients are active and slows down
        # when more clients share the CPU.
        x_virt = self._vt_boundaries[frame + 1]
        self.virt_line.set_xdata([x_virt, x_virt])

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
            if cs.active:
                lag_sign = "+" if cs.lag > 0 else ""
                lines.append(f"    lag={lag_sign}{cs.lag:.4f}")
            elif cs.active:
                lines.append("    (between requests)")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _nice_step(data_range: float, target_ticks: int = 10) -> float:
        """Return a 'nice' step size for axis ticks."""
        raw = data_range / max(target_ticks, 1)
        mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
        normalized = raw / mag
        if normalized <= 1:
            nice = 1
        elif normalized <= 2:
            nice = 2
        elif normalized <= 5:
            nice = 5
        else:
            nice = 10
        return nice * mag

    @staticmethod
    def _arange_nice(start: float, stop: float, step: float) -> list[float]:
        """Return evenly spaced values from start up to and including stop."""
        vals: list[float] = []
        v = start
        while v <= stop + step * 1e-9:
            vals.append(round(v, 6))
            v += step
        return vals

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
