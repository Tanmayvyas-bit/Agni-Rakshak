"""Turn noisy per-frame detections into clean alarm events."""
from __future__ import annotations

import sys
import threading
import time


class AlertTracker:
    """Raise an alert only after fire is seen in N consecutive frames, then stay quiet for a cooldown.

    A single frame with a red jacket should not set off the alarm; five frames in a row of real
    flame should. After alarming we wait `cooldown_seconds` before alarming again so the
    dashboard isn't flooded with one event per frame.
    """

    def __init__(self, min_consecutive_frames: int = 5, cooldown_seconds: float = 30, clock=time.monotonic):
        self.min_frames = max(1, int(min_consecutive_frames))
        self.cooldown = float(cooldown_seconds)
        self._clock = clock
        self._streak = 0
        self._last_alert = None

    @property
    def streak(self) -> int:
        return self._streak

    def update(self, fire_present: bool) -> bool:
        """Feed one frame's result. Returns True exactly when a new alert should fire."""
        self._streak = self._streak + 1 if fire_present else 0
        if self._streak < self.min_frames:
            return False
        now = self._clock()
        if self._last_alert is not None and now - self._last_alert < self.cooldown:
            return False
        self._last_alert = now
        return True

    def reset(self) -> None:
        self._streak = 0
        self._last_alert = None


def beep(times: int = 3) -> None:
    """Sound the laptop speaker without blocking the video loop."""

    def _run():
        for _ in range(times):
            if sys.platform.startswith("win"):
                import winsound

                winsound.Beep(2500, 300)
            else:
                sys.stdout.write("\a")
                sys.stdout.flush()
                time.sleep(0.3)

    threading.Thread(target=_run, daemon=True).start()
