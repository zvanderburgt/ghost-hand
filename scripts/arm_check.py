"""Check that only the configured arming pose arms the engine.

    python scripts/arm_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.gestures import GestureEngine  # noqa: E402
from gr.synthetic import make_hand  # noqa: E402


def run(pose: str, seconds: float = 1.5) -> bool:
    settings = Settings()          # defaults: arm_pose = rock
    engine = GestureEngine(settings)
    t = 1000.0
    armed = False
    for _ in range(int(seconds * 1000 / 33)):
        state = engine.update(
            [make_hand(pose, 1280, 720, size_px=417, center=(640, 400))], t
        )
        t += 33.0
        armed = armed or state.armed
    return armed


CASES = [
    ("rock", True),
    ("open_palm", False),
    ("fist", False),
    ("peace", False),
    ("point_up", False),
    ("three", False),
    ("thumbs_up", False),
    ("ok_sign", False),
]


def main() -> int:
    failures = 0
    for pose, expected in CASES:
        armed = run(pose)
        ok = armed == expected
        label = "arms" if armed else "does not arm"
        print(f"  {'PASS' if ok else 'FAIL'}  {pose:<12} {label:<14} (wanted {'arms' if expected else 'no arm'})")
        if not ok:
            failures += 1
    print()
    print("all cases pass" if not failures else f"{failures} FAILURE(S)")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
