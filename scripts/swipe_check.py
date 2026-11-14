"""Swipe detection checks.

    python scripts/swipe_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.gestures import GestureEngine  # noqa: E402
from gr.synthetic import make_hand  # noqa: E402

W, H = 1280, 720
START = (480.0, 380.0)


def new_engine(bind_open_palm: str | None = None) -> GestureEngine:
    settings = Settings()
    settings.set("engine.swipe_enabled", True)
    settings.set("engine.swipe_pose", "open_palm")
    settings.set("engine.swipe_window_ms", 320)
    settings.set("engine.swipe_min_distance", 1.3)
    settings.set("engine.swipe_cooldown_ms", 600)
    settings.set("engine.fire_hold_ms", 400)
    if bind_open_palm:
        settings.set_binding("open_palm", bind_open_palm)
    return GestureEngine(settings)


def hand(pose: str, cx: float, cy: float):
    return make_hand(pose, W, H, size_px=417, center=(cx, cy))


def arm(engine: GestureEngine, t: float) -> float:
    for _ in range(60):
        engine.update([hand("rock", *START)], t)
        t += 33.0
    return t


def settle(engine: GestureEngine, t: float, frames: int = 12) -> tuple[float, list[str]]:
    fired: list[str] = []
    for _ in range(frames):
        state = engine.update([hand("open_palm", *START)], t)
        t += 33.0
        fired.extend(state.fired)
    return t, fired


def move(engine: GestureEngine, t: float, dx: float, dy: float,
         frames: int = 8, pose: str = "open_palm") -> tuple[float, list[str]]:
    fired: list[str] = []
    for i in range(1, frames + 1):
        cx = START[0] + dx * i / frames
        cy = START[1] + dy * i / frames
        state = engine.update([hand(pose, cx, cy)], t)
        t += 33.0
        fired.extend(state.fired)
    return t, fired


def scenario(pose: str, dx: float, dy: float, frames: int = 8,
             bind_open_palm: str | None = None) -> list[str]:
    engine = new_engine(bind_open_palm)
    t = arm(engine, 1000.0)
    t, fired = settle(engine, t)
    t, fired2 = move(engine, t, dx, dy, frames, pose)
    return fired + fired2


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        results.append((name, bool(condition), detail))

    fast_right = scenario("open_palm", 400, 0)
    check("fast right swipe fires swipe_right", fast_right == ["swipe_right"], str(fast_right))

    fast_left = scenario("open_palm", -400, 0)
    check("fast left swipe fires swipe_left", fast_left == ["swipe_left"], str(fast_left))

    up = scenario("open_palm", 0, -260)
    check("upward swipe fires swipe_up", up == ["swipe_up"], str(up))

    down = scenario("open_palm", 0, 260)
    check("downward swipe fires swipe_down", down == ["swipe_down"], str(down))

    diagonal = scenario("open_palm", 260, 260)
    check("diagonal movement does nothing", diagonal == [], str(diagonal))

    slow = scenario("open_palm", 400, 0, frames=40)
    check("slow movement does nothing", slow == [], str(slow))

    wrong_pose = scenario("peace", 400, 0)
    check("swipe only works from open palm", wrong_pose == [], str(wrong_pose))

    # Holding the palm still *after* a swipe must not fire the pose binding late.
    engine = new_engine(bind_open_palm="media.play_pause")
    t = arm(engine, 1000.0)
    t, before = settle(engine, t, frames=6)          # stable, still under fire_hold
    t, during = move(engine, t, 400, 0)
    t, after = settle(engine, t, frames=30)          # keep holding, well past fire_hold
    check("holding after a swipe does not fire the pose",
          before + during + after == ["swipe_right"], str(before + during + after))

    # cooldown: two swipes inside 600 ms should yield one event
    engine = new_engine()
    t = arm(engine, 1000.0)
    t, fired = settle(engine, t)
    t, second = move(engine, t, 400, 0)
    t, third = move(engine, t, -400, 0)
    check("second swipe inside cooldown is ignored",
          fired + second + third == ["swipe_right"], str(fired + second + third))

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
