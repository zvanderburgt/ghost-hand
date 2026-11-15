"""Point-and-pinch cursor checks (no real pointer movement).

Covers the techniques taken from comparable projects: One Euro smoothing,
pointer freeze while pinching, pinch hysteresis, tap-vs-drag, and virtual-screen
mapping.

    python scripts/cursor_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.cursor import CursorController  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


class FakeMouse:
    def __init__(self) -> None:
        self.position = (0, 0)
        self.calls: list[tuple] = []

    def click(self, button, count: int = 1) -> None:
        self.calls.append(("click", getattr(button, "name", str(button))))

    def press(self, button) -> None:
        self.calls.append(("press", getattr(button, "name", str(button))))

    def release(self, button) -> None:
        self.calls.append(("release", getattr(button, "name", str(button))))

    def scroll(self, dx, dy) -> None:
        self.calls.append(("scroll", dx, dy))


SCREEN = (0, 0, 1000, 500)


def settings() -> Settings:
    s = Settings()
    s.set("cursor.region_x0", 0.20)
    s.set("cursor.region_x1", 0.80)
    s.set("cursor.region_y0", 0.20)
    s.set("cursor.region_y1", 0.80)
    s.set("cursor.gain", 1.0)
    s.set("cursor.one_euro_min_cutoff", 1.0)   # fast convergence for testing
    s.set("cursor.one_euro_beta", 0.0)
    s.set("cursor.pinch_enter", 0.40)
    s.set("cursor.pinch_exit", 0.55)
    s.set("cursor.drag_hold_ms", 400)
    s.set("cursor.click_cooldown_ms", 320)
    return s


def settle(cur, nx: float, ny: float, t: float, frames: int = 40) -> tuple[dict, float]:
    info: dict = {}
    for _ in range(frames):
        info = cur.update(nx, ny, 1.0, t)
        t += 33.0
    return info, t


def main() -> int:
    # ---- mapping ------------------------------------------------------- #
    mouse = FakeMouse()
    cur = CursorController(settings(), mouse=mouse, screen=SCREEN)

    info, t = settle(cur, 0.5, 0.5, 0.0)
    check("centre maps to centre", abs(info["x"] - 499) <= 2 and abs(info["y"] - 249) <= 2, str(info))

    info, t = settle(cur, 0.0, 0.0, t)
    check("outside region clamps to top-left", abs(info["x"]) <= 2 and abs(info["y"]) <= 2, str(info))

    info, t = settle(cur, 1.0, 1.0, t)
    check("outside region clamps to bottom-right",
          abs(info["x"] - 999) <= 2 and abs(info["y"] - 499) <= 2, str(info))

    screen_offset = CursorController(settings(), mouse=FakeMouse(), screen=(-1920, -200, 3440, 1440))
    info, _ = settle(screen_offset, 0.0, 0.0, 0.0)
    check("virtual screen offset respected", (info["x"], info["y"]) == (-1920, -200), str(info))

    # ---- One Euro smoothing -------------------------------------------- #
    smooth = CursorController(settings(), mouse=FakeMouse(), screen=SCREEN)
    _, t = settle(smooth, 0.5, 0.5, 0.0)
    step = smooth.update(0.75, 0.5, 1.0, t)
    check("single fast step is damped, not snapped",
          499 < step["x"] < 749, f"x={step['x']}")

    # ---- pinch freeze --------------------------------------------------- #
    freeze = CursorController(settings(), mouse=FakeMouse(), screen=SCREEN)
    _, t = settle(freeze, 0.5, 0.5, 0.0)
    info = freeze.update(0.5, 0.5, 0.30, t)           # engage pinch
    before = info["x"]
    info = freeze.update(0.9, 0.9, 0.30, t + 40.0)    # move hand while pinched
    check("pointer freezes while pinching", info["x"] == before, f"{before} -> {info['x']}")

    # ---- hysteresis ------------------------------------------------------ #
    hyst = CursorController(settings(), mouse=FakeMouse(), screen=SCREEN)
    info = hyst.update(0.5, 0.5, 0.50, 0.0)           # above enter -> no pinch
    check("mid-range value does not engage", not info["pinching"], str(info))
    hyst.update(0.5, 0.5, 0.30, 40.0)                 # engage
    info = hyst.update(0.5, 0.5, 0.50, 80.0)          # between thresholds
    check("mid-range value holds an active pinch", info["pinching"], str(info))
    info = hyst.update(0.5, 0.5, 0.60, 120.0)         # above exit -> release
    check("loose value releases the pinch", not info["pinching"], str(info))

    # ---- tap = click, hold = drag ---------------------------------------- #
    tap = FakeMouse()
    cur = CursorController(settings(), mouse=tap, screen=SCREEN)
    settle(cur, 0.5, 0.5, 0.0)
    cur.update(0.5, 0.5, 0.30, 2000.0)                # pinch down
    info = cur.update(0.5, 0.5, 0.70, 2150.0)         # release after 150 ms
    check("short pinch is a click", info["clicked"] and ("click", "left") in tap.calls,
          str(tap.calls))

    drag = FakeMouse()
    cur = CursorController(settings(), mouse=drag, screen=SCREEN)
    settle(cur, 0.5, 0.5, 0.0)
    cur.update(0.5, 0.5, 0.30, 3000.0)
    info = cur.update(0.5, 0.5, 0.30, 3500.0)         # hold > drag_hold_ms
    check("long pinch starts a drag", info["dragging"] and ("press", "left") in drag.calls,
          str(drag.calls))
    info = cur.update(0.5, 0.5, 0.70, 3600.0)
    check("releasing ends the drag without a click",
          not info["dragging"] and ("release", "left") in drag.calls
          and ("click", "left") not in drag.calls,
          str(drag.calls))

    # ---- guaranteed release --------------------------------------------- #
    lost = FakeMouse()
    cur = CursorController(settings(), mouse=lost, screen=SCREEN)
    settle(cur, 0.5, 0.5, 0.0)
    cur.update(0.5, 0.5, 0.30, 4000.0)
    cur.update(0.5, 0.5, 0.30, 4600.0)                # dragging
    cur.reset()                                       # hand left the frame
    check("hand loss releases a held drag",
          ("release", "left") in lost.calls and not cur.dragging, str(lost.calls))

    # ---- right click ----------------------------------------------------- #
    right = FakeMouse()
    cur = CursorController(settings(), mouse=right, screen=SCREEN)
    settle(cur, 0.5, 0.5, 0.0)
    info = cur.update(0.5, 0.5, 0.90, 4000.0, middle_pinch_ratio=0.20)
    check("middle pinch alone does not click yet", not info["right_clicked"], str(info))
    info = cur.update(0.5, 0.5, 0.90, 4060.0, middle_pinch_ratio=0.60)
    check("releasing the middle pinch right-clicks",
          info["right_clicked"] and ("click", "right") in right.calls, str(right.calls))

    both = FakeMouse()
    cur = CursorController(settings(), mouse=both, screen=SCREEN)
    settle(cur, 0.5, 0.5, 0.0)
    cur.update(0.5, 0.5, 0.20, 5000.0, middle_pinch_ratio=0.20)   # both pinched
    cur.update(0.5, 0.5, 0.70, 5100.0, middle_pinch_ratio=0.70)   # both released
    check("left pinch wins over right", both.calls == [("click", "left")], str(both.calls))

    # ---- scroll ---------------------------------------------------------- #
    scrolling = FakeMouse()
    cur = CursorController(settings(), mouse=scrolling, screen=SCREEN)
    cur.update(0.5, 0.50, 1.0, 6000.0, scroll_mode=True)          # baseline
    before = cur.last
    info = cur.update(0.5, 0.54, 1.0, 6040.0, scroll_mode=True)   # hand down 4%
    check("moving down scrolls down",
          info["scrolled"] > 0 and ("scroll", 0, -info["scrolled"]) in scrolling.calls,
          str(scrolling.calls))
    check("pointer stays put while scrolling", cur.last == before, f"{before} -> {cur.last}")

    cur.update(0.5, 0.50, 1.0, 6100.0, scroll_mode=True)          # back to start
    info = cur.update(0.5, 0.46, 1.0, 6140.0, scroll_mode=True)   # hand up 8%
    check("moving up scrolls up",
          info["scrolled"] < 0 and ("scroll", 0, -info["scrolled"]) in scrolling.calls,
          str(scrolling.calls))

    # ---- dwell clicking -------------------------------------------------- #
    dwell_settings = settings()
    dwell_settings.set("cursor.dwell_enabled", True)
    dwell_settings.set("cursor.dwell_ms", 500)
    dwell_mouse = FakeMouse()
    cur = CursorController(dwell_settings, mouse=dwell_mouse, screen=SCREEN)

    info = cur.update(0.5, 0.5, 1.0, 8000.0)
    dwell_fired = False
    for step in range(1, 21):                       # ~800 ms still
        info = cur.update(0.5, 0.5, 1.0, 8000.0 + step * 40)
        dwell_fired = dwell_fired or bool(info.get("dwell"))
    check("holding still dwells a click",
          dwell_fired and ("click", "left") in dwell_mouse.calls, str(dwell_mouse.calls))

    count = len(dwell_mouse.calls)
    info = cur.update(0.5, 0.5, 1.0, 8900.0)
    check("dwell does not repeat while still",
          not info.get("dwell") and len(dwell_mouse.calls) == count, str(dwell_mouse.calls))

    cur.update(0.9, 0.5, 1.0, 9000.0)               # move beyond the radius
    info = cur.update(0.9, 0.5, 1.0, 9050.0)
    dwell_fired = False
    for step in range(1, 46):                       # let smoothing settle, then hold
        info = cur.update(0.9, 0.5, 1.0, 9050.0 + step * 40)
        dwell_fired = dwell_fired or bool(info.get("dwell"))
    check("dwell re-arms after moving", dwell_fired, str(info))

    cancel_settings = settings()
    cancel_settings.set("cursor.dwell_enabled", True)
    cancel_settings.set("cursor.dwell_ms", 400)
    cancel_mouse = FakeMouse()
    cur = CursorController(cancel_settings, mouse=cancel_mouse, screen=SCREEN)
    cur.update(0.5, 0.5, 1.0, 9000.0)
    cur.update(0.5, 0.5, 1.0, 9100.0)
    cur.update(0.5, 0.5, 0.20, 9200.0)               # pinch cancels dwell
    cur.update(0.5, 0.5, 0.90, 9300.0)
    info = cur.update(0.5, 0.5, 1.0, 9600.0)
    check("pinching cancels a pending dwell", not info.get("dwell"), str(cancel_mouse.calls))

    failures = 0
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail and not ok else ''}")
        if not ok:
            failures += 1
    print()
    print("all checks pass" if not failures else f"{failures} FAILURE(S)")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
