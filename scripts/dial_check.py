"""Headless check for the rotary volume dial.

    python scripts/dial_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.gestures import GestureEngine  # noqa: E402
from gr.synthetic import make_hand  # noqa: E402


def dial_hand(rotation: float):
    """A fist with the thumb tip pinched onto the index tip."""
    hand = make_hand("fist", 1280, 720, size_px=417, center=(640, 400),
                     rotation_deg=rotation)
    px = list(hand.px)
    px[4] = px[8]
    px[3] = ((px[2][0] + px[4][0]) / 2, (px[2][1] + px[4][1]) / 2)
    hand.px = px
    return hand


def arm(engine: GestureEngine, t: float) -> float:
    for _ in range(60):
        engine.update([make_hand("rock", 1280, 720, size_px=417, center=(640, 400))], t)
        t += 33.0
    return t


def run(step_deg: float, sweep: float) -> None:
    settings = Settings()
    settings.set("engine.dial_degrees_per_step", step_deg)
    engine = GestureEngine(settings)
    t = arm(engine, 1000.0)

    ticks = 0
    fired: list[str] = []
    engaged = False
    for rotation in range(0, int(sweep) + 1, 3):
        state = engine.update([dial_hand(rotation)], t)
        t += 33.0
        ticks += engine.take_dial_ticks()
        engaged = engaged or state.dial_active
        fired.extend(state.fired)

    fired_text = ",".join(fired) if fired else "none"
    print(
        f"degrees/step={step_deg:4.1f}  sweep={sweep:3.0f}deg  "
        f"engaged={engaged}  ticks={ticks:3d}  wrong-fires={fired_text}"
    )


def main() -> int:
    for step, sweep in ((6.0, 48), (12.0, 48), (3.0, 24)):
        run(step, sweep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
