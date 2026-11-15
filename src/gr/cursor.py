"""Point-and-pinch cursor: the index fingertip drives the Windows pointer.

Smoothing is a One Euro filter (Casiez, Roussel & Vogel, CHI 2012): a low-pass
whose cutoff rises with speed, so the pointer is steady when your hand is still
and responsive when you move. Every mature gesture-mouse project surveyed
(GestureHud, Air-Cursor, Mouseless, Vimoose, Mausely) converges on this.

Click handling uses two techniques borrowed from those projects:

* the pointer **freezes while pinching**, so closing your hand doesn't drag the
  cursor off the button you aimed at;
* pinch uses **hysteresis** (separate engage/release thresholds), so a hand at
  the boundary doesn't produce click chatter;
* a short pinch is a click, a long pinch becomes a **drag** that is always
  released, even if the hand leaves the frame.
"""

from __future__ import annotations

import ctypes
import math

from pynput.mouse import Button, Controller


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if value < lo else hi if value > hi else value


def virtual_screen_rect() -> tuple[int, int, int, int]:
    """(x, y, width, height) covering every monitor, or the primary screen."""
    try:
        user32 = ctypes.windll.user32
        x = int(user32.GetSystemMetrics(76))   # SM_XVIRTUALSCREEN
        y = int(user32.GetSystemMetrics(77))   # SM_YVIRTUALSCREEN
        w = int(user32.GetSystemMetrics(78))   # SM_CXVIRTUALSCREEN
        h = int(user32.GetSystemMetrics(79))   # SM_CYVIRTUALSCREEN
        if w > 0 and h > 0:
            return x, y, w, h
    except Exception:  # noqa: BLE001 - non-Windows / headless
        pass
    try:
        user32 = ctypes.windll.user32
        return 0, 0, int(user32.GetSystemMetrics(0)), int(user32.GetSystemMetrics(1))
    except Exception:  # noqa: BLE001
        return 0, 0, 1920, 1080


class _LowPass:
    def __init__(self) -> None:
        self.value: float | None = None

    def __call__(self, x: float, alpha: float) -> float:
        if self.value is None:
            self.value = x
        else:
            self.value = alpha * x + (1.0 - alpha) * self.value
        return self.value

    def reset(self) -> None:
        self.value = None


class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0,
                 d_cutoff: float = 1.0) -> None:
        self.min_cutoff = max(0.01, min_cutoff)
        self.beta = beta
        self.d_cutoff = max(0.01, d_cutoff)
        self._x = _LowPass()
        self._dx = _LowPass()
        self._last_t: float | None = None
        self._last_x: float | None = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def reset(self) -> None:
        self._x.reset()
        self._dx.reset()
        self._last_t = None
        self._last_x = None

    def filter(self, x: float, t: float) -> float:
        dt = 1.0 / 30.0 if self._last_t is None else max(1e-3, t - self._last_t)
        # A stalled frame (paused app, debugger) must not make the filter snap.
        dt = min(dt, 0.1)
        raw_dx = 0.0 if self._last_x is None else (x - self._last_x) / dt
        dx_hat = self._dx(raw_dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(dx_hat)
        value = self._x(x, self._alpha(cutoff, dt))
        self._last_t = t
        self._last_x = x
        return value


class CursorController:
    def __init__(self, settings, mouse=None,
                 screen: tuple[int, int, int, int] | None = None) -> None:
        self.s = settings
        self._mouse = mouse if mouse is not None else Controller()
        self.screen_x, self.screen_y, self.screen_w, self.screen_h = (
            screen if screen else virtual_screen_rect()
        )
        self._fx = OneEuroFilter()
        self._fy = OneEuroFilter()
        self._configure_filters()

        self._pinch = False
        self._dragging = False
        self._pinch_since = 0.0
        self._last_click_ms = -1e9
        self._right_pinch = False
        self._last_right_click_ms = -1e9
        self._last_scroll_y: float | None = None
        self._scroll_accum = 0.0
        self._dwell_anchor: tuple[int, int] | None = None
        self._dwell_since = 0.0
        self._dwell_fired = False
        self.last = (0, 0)

    def _configure_filters(self) -> None:
        cutoff = float(self.s.get("cursor.one_euro_min_cutoff", 0.35))
        beta = float(self.s.get("cursor.one_euro_beta", 0.08))
        self._fx.min_cutoff = self._fy.min_cutoff = max(0.01, cutoff)
        self._fx.beta = self._fy.beta = beta

    @property
    def dragging(self) -> bool:
        return self._dragging

    def reset(self) -> None:
        """Release any held button and forget the filter state."""
        if self._dragging:
            try:
                self._mouse.release(Button.left)
            except Exception:  # noqa: BLE001
                pass
            self._dragging = False
        self._pinch = False
        self._right_pinch = False
        self._last_scroll_y = None
        self._scroll_accum = 0.0
        self._dwell_anchor = None
        self._dwell_fired = False
        self._fx.reset()
        self._fy.reset()

    # ------------------------------------------------------------------ #

    def _scroll(self, ny: float) -> int:
        """Vertical hand movement to wheel ticks; down is negative like a mouse."""
        step = max(0.001, float(self.s.get("cursor.scroll_step", 0.02)))
        if self._last_scroll_y is None:
            self._last_scroll_y = ny
            return 0
        self._scroll_accum += ny - self._last_scroll_y
        self._last_scroll_y = ny
        ticks = int(self._scroll_accum / step)
        if ticks:
            try:
                self._mouse.scroll(0, -ticks)
            except Exception:  # noqa: BLE001
                pass
            self._scroll_accum -= ticks * step
        return ticks

    def update(self, nx: float, ny: float, pinch_ratio: float, now_ms: float,
               middle_pinch_ratio: float = 1.0,
               scroll_mode: bool = False) -> dict:
        self._configure_filters()
        t = now_ms / 1000.0

        if scroll_mode:
            if self._dragging:
                try:
                    self._mouse.release(Button.left)
                except Exception:  # noqa: BLE001
                    pass
                self._dragging = False
            self._pinch = False
            self._right_pinch = False
            ticks = self._scroll(ny)
            return {
                "x": self.last[0], "y": self.last[1],
                "clicked": False, "right_clicked": False,
                "dragging": False, "pinching": False, "scrolled": ticks,
            }

        self._last_scroll_y = None
        self._scroll_accum = 0.0

        x0 = float(self.s.get("cursor.region_x0", 0.18))
        x1 = float(self.s.get("cursor.region_x1", 0.82))
        y0 = float(self.s.get("cursor.region_y0", 0.18))
        y1 = float(self.s.get("cursor.region_y1", 0.82))

        u = _clamp((nx - x0) / (x1 - x0)) if x1 > x0 else 0.5
        v = _clamp((ny - y0) / (y1 - y0)) if y1 > y0 else 0.5

        gain = float(self.s.get("cursor.gain", 1.0))
        u = _clamp(0.5 + (u - 0.5) * gain)
        v = _clamp(0.5 + (v - 0.5) * gain)

        # Hysteresis: a lower threshold engages, a higher one releases.
        enter = float(self.s.get("cursor.pinch_enter", 0.40))
        release = float(self.s.get("cursor.pinch_exit", 0.55))
        was_pinching = self._pinch
        if self._pinch:
            self._pinch = pinch_ratio <= release
        else:
            self._pinch = pinch_ratio <= enter

        clicked = False
        if not self._pinch:
            sx = self._fx.filter(u, t)
            sy = self._fy.filter(v, t)
            px = self.screen_x + int(_clamp(sx) * (self.screen_w - 1))
            py = self.screen_y + int(_clamp(sy) * (self.screen_h - 1))
            try:
                self._mouse.position = (px, py)
            except Exception:  # noqa: BLE001 - pointer moves must never crash the loop
                pass
            self.last = (px, py)
        # While pinching the pointer stays put, so the click lands where you aimed.

        if self._pinch and not was_pinching:
            self._pinch_since = now_ms

        drag_hold = float(self.s.get("cursor.drag_hold_ms", 400))
        if self._pinch and not self._dragging and (now_ms - self._pinch_since) >= drag_hold:
            try:
                self._mouse.press(Button.left)
            except Exception:  # noqa: BLE001
                pass
            self._dragging = True

        if not self._pinch and was_pinching:
            if self._dragging:
                try:
                    self._mouse.release(Button.left)
                except Exception:  # noqa: BLE001
                    pass
                self._dragging = False
            else:
                cooldown = float(self.s.get("cursor.click_cooldown_ms", 320))
                if (now_ms - self._last_click_ms) >= cooldown:
                    try:
                        self._mouse.click(Button.left)
                    except Exception:  # noqa: BLE001
                        pass
                    self._last_click_ms = now_ms
                    clicked = True

        # Right click is thumb-to-middle, and yields to the left pinch.
        right_enter = float(self.s.get("cursor.right_pinch_enter", 0.30))
        right_exit = float(self.s.get("cursor.right_pinch_exit", 0.42))
        was_right = self._right_pinch
        if self._pinch:
            self._right_pinch = False
        elif self._right_pinch:
            self._right_pinch = middle_pinch_ratio <= right_exit
        else:
            self._right_pinch = middle_pinch_ratio <= right_enter

        right_clicked = False
        if not self._right_pinch and was_right and not self._pinch:
            cooldown = float(self.s.get("cursor.click_cooldown_ms", 320))
            if (now_ms - self._last_right_click_ms) >= cooldown:
                try:
                    self._mouse.click(Button.right)
                except Exception:  # noqa: BLE001
                    pass
                self._last_right_click_ms = now_ms
                right_clicked = True

        # Dwell: click by holding the pointer still. Cancelled by any pinch.
        dwell_clicked = False
        if self._pinch or self._right_pinch:
            self._dwell_anchor = None
            self._dwell_fired = False
        elif bool(self.s.get("cursor.dwell_enabled", False)) and not self._dragging:
            radius = float(self.s.get("cursor.dwell_radius_px", 14))
            if self._dwell_anchor is None:
                self._dwell_anchor = self.last
                self._dwell_since = now_ms
            else:
                ax, ay = self._dwell_anchor
                if ((self.last[0] - ax) ** 2 + (self.last[1] - ay) ** 2) ** 0.5 > radius:
                    self._dwell_anchor = self.last
                    self._dwell_since = now_ms
                    self._dwell_fired = False

            hold = float(self.s.get("cursor.dwell_ms", 800))
            if not self._dwell_fired and (now_ms - self._dwell_since) >= hold:
                try:
                    self._mouse.click(Button.left)
                except Exception:  # noqa: BLE001
                    pass
                self._dwell_fired = True
                dwell_clicked = True

        return {
            "x": self.last[0],
            "y": self.last[1],
            "clicked": clicked or dwell_clicked,
            "dwell": dwell_clicked,
            "right_clicked": right_clicked,
            "dragging": self._dragging,
            "pinching": self._pinch,
            "scrolled": 0,
        }
