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
    """Animated EEVDF schedule viewer driven by a list of TickState snapshots.

    Each real tick produces two frames in the history:
      - phase="deciding": auto-pauses so the presenter can ask the class
        who they think will be selected next.
      - phase="running": reveals which client was actually selected.
    """

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

        # Maximum virtual time reached (for axis scaling).
        self._max_vt = self._compute_max_vt()

        self._setup_axes()

        # Animated artists that we update each frame.
        self.time_line = self.ax_real.axvline(0, color="red", lw=1.5)
        self.virt_line = self.ax_virt.axvline(0, color="red", lw=1.5)
        self.state_text = self.ax_state.text(
            0.05, 0.95, "", transform=self.ax_state.transAxes,
            fontsize=10, verticalalignment="top", fontfamily="monospace",
        )

        # Set of real-tick indices whose blocks have already been drawn.
        self._drawn_ticks: set[int] = set()

        # Pause state — animation starts paused.
        self._paused = True

    # ---- axis setup -------------------------------------------------------

    def _compute_max_vt(self) -> float:
        """Max virtual time value across all running frames (for vt axis)."""
        max_vt = 0.0
        for s in self.history:
            if s.phase == "running" and s.total_weight > 0:
                vt = s.virtual_time + 1.0 / s.total_weight
                if vt > max_vt:
                    max_vt = vt
        return max_vt if max_vt > 0 else 1.0

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
        self.ax_virt.set_xlim(0, self._max_vt)
        self.ax_virt.set_ylim(0, 1)
        self.ax_virt.set_yticks([])
        self.ax_virt.set_ylabel("Virtual\nTime", rotation=0, labelpad=40, va="center")
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

        # Draw blocks for any running frames up to and including this one
        # that haven't been drawn yet (handles fast-forward edge cases).
        for f in range(frame + 1):
            s = self.history[f]
            if s.phase != "running" or s.running_client is None:
                continue
            t = s.real_time
            if t in self._drawn_ticks:
                continue
            self._drawn_ticks.add(t)
            ci = s.running_client
            rect = mpatches.FancyBboxPatch(
                (t + 0.05, 0.1), 0.9, 0.8,
                boxstyle="round,pad=0.05",
                facecolor=self.colors[ci], edgecolor="white", lw=0.8,
            )
            self.ax_clients[ci].add_patch(rect)

        # Real time red line:
        #   deciding → at the start of the tick (before it runs)
        #   running  → at the end of the tick (after it runs)
        if state.phase == "deciding":
            x_real = state.real_time
        else:
            x_real = state.real_time + 1
        self.time_line.set_xdata([x_real, x_real])

        # Virtual time red line:
        #   deciding → current virtual time (before advancement)
        #   running  → virtual time after this tick's advancement
        if state.phase == "deciding":
            x_virt = state.virtual_time
        else:
            if state.total_weight > 0:
                x_virt = state.virtual_time + 1.0 / state.total_weight
            else:
                x_virt = state.virtual_time
        self.virt_line.set_xdata([x_virt, x_virt])

        # State panel text.
        self.state_text.set_text(self._build_state_text(state))

        return []

    def _build_state_text(self, state: TickState) -> str:
        sep = "─" * 28

        if state.phase == "deciding":
            header = "  ? Who runs next?"
        else:
            header = "  Scheduler State"

        lines = [
            header,
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
                eligible = r.eligible_time <= state.virtual_time + 1e-9
                # In deciding mode, mark whether the request is eligible.
                if state.phase == "deciding":
                    elig = " [eligible]" if eligible else " [not yet]"
                else:
                    elig = ""
                lines.append(f"    virtual eligible time = {r.eligible_time:.4f}")
                lines.append(f"    virtual deadline = {r.deadline:.4f}")
                lines.append(f"    remaining time = {r.remaining}/{r.length}")
            if cs.active:
                lag_sign = "+" if cs.lag > 0 else ""
                lines.append(f"    lag = {lag_sign}{cs.lag:.4f}")
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
            return "(deciding...)" if state.phase == "deciding" else "(idle)"
        return state.clients[state.running_client].name

    # ---- play / pause -----------------------------------------------------

    def _on_key(self, event) -> None:
        """Toggle play/pause on spacebar press."""
        if event.key != " ":
            return
        if self._paused:
            self.anim.resume()
            self._paused = False
            self._pause_text.set_text("")
        else:
            self.anim.pause()
            self._paused = True
            self._pause_text.set_text("PAUSED  (press Space to resume)")
        self.fig.canvas.draw_idle()

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
        self._pause_text = self.fig.text(
            0.35, 0.01, "PAUSED  (press Space to start)",
            fontsize=11, color="red", fontweight="bold",
            ha="center",
        )
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)
        plt.tight_layout()

        # FuncAnimation connects _start to draw_event (stored in
        # _first_draw_id).  _start fires on the first draw and restarts the
        # timer, overriding any pause() called before plt.show().
        # Fix: disconnect that handler and replace it with a wrapper that
        # lets _start initialise the frame sequence, then immediately pauses.
        self.fig.canvas.mpl_disconnect(self.anim._first_draw_id)
        def _start_then_pause(event):
            self.fig.canvas.mpl_disconnect(_cid)
            self.anim._start(event)
            self.anim.pause()
        _cid = self.fig.canvas.mpl_connect('draw_event', _start_then_pause)

        plt.show()
