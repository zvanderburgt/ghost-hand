"""Verify that continuous ramping follows the *binding*, not the gesture.

    python scripts/ramp_check.py

Regression for: unbinding thumbs-up/down from volume still changed volume.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.gestures import GestureEngine  # noqa: E402
from gr.synthetic import make_hand  # noqa: E402


def hold(gesture: str, binding: str | None, seconds: float = 1.2):
    settings = Settings()
    settings.set("engine.fire_hold_ms", 400)
    settings.set("engine.volume_hold_ms", 300)
    settings.set_binding(gesture, binding)

    engine = GestureEngine(settings)
    t = 1000.0
    for _ in range(60):  # arm with the configured arming pose (rock sign)
        engine.update([make_hand("rock", 1280, 720, size_px=417, center=(640, 400))], t)
        t += 33.0

    ticks = 0
    fired: list[str] = []
    ramped = False
    frames = int(seconds * 1000 / 33)
    for _ in range(frames):
        state = engine.update([make_hand(gesture, 1280, 720, size_px=417, center=(640, 400))], t)
        t += 33.0
        ticks += engine.take_ramp_ticks()
        ramped = ramped or state.ramp_active
        fired.extend(state.fired)
    return ticks, fired, ramped


CASES = [
    ("thumbs up -> system.copy (no ramp expected)", "thumbs_up", "system.copy", 0, 1),
    ("thumbs up -> volume_up (ramp expected)", "thumbs_up", "media.volume_up", 1, 0),
    ("thumbs down -> volume_down (ramp expected)", "thumbs_down", "media.volume_down", 1, 0),
    ("thumbs up -> unbound (nothing expected)", "thumbs_up", None, 0, 0),
    ("V sign -> play_pause (single shot)", "peace", "media.play_pause", 0, 1),
]


def main() -> int:
    failures = 0
    for desc, gesture, binding, want_ticks, want_fires in CASES:
        ticks, fired, ramped = hold(gesture, binding)
        got_ticks = 1 if ticks > 0 else 0
        ok = got_ticks == want_ticks and len(fired) == want_fires
        status = "PASS" if ok else "FAIL"
        fired_text = ",".join(fired) if fired else "none"
        print(
            f"  {status}  {desc:<46} ticks={ticks:3d}  fires={len(fired)} [{fired_text}]  ramped={ramped}"
        )
        if not ok:
            failures += 1
    print()
    print("all cases pass" if not failures else f"{failures} FAILURE(S)")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
