"""Custom gesture learning checks.

    python scripts/custom_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.custom import descriptor, distance, match_score, template_from  # noqa: E402
from gr.gestures import GestureEngine  # noqa: E402
from gr.synthetic import POSE_SPECS, make_hand  # noqa: E402

W, H = 1280, 720
POSE_SPECS["index_ring"] = "1010"  # not a built-in gesture


def hand(pose: str, cx: float = 640.0, cy: float = 400.0, rotation: float = 0.0):
    return make_hand(pose, W, H, size_px=380, center=(cx, cy), rotation_deg=rotation)


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        results.append((name, bool(condition), detail))

    # ---- descriptor invariance ----------------------------------------- #
    base = descriptor(hand("index_ring"))
    moved = descriptor(hand("index_ring", cx=380.0, cy=300.0))
    rotated = descriptor(hand("index_ring", rotation=18.0))
    scaled = descriptor(make_hand("index_ring", W, H, size_px=520, center=(700.0, 420.0)))

    check("descriptor ignores position", distance(base, moved) < 0.02, f"{distance(base, moved):.3f}")
    check("descriptor ignores wrist roll", distance(base, rotated) < 0.05, f"{distance(base, rotated):.3f}")
    check("descriptor ignores distance", distance(base, scaled) < 0.05, f"{distance(base, scaled):.3f}")
    check("different shapes are far apart",
          distance(base, descriptor(hand("peace"))) > 0.15,
          f"{distance(base, descriptor(hand('peace'))):.3f}")

    # ---- template + scoring -------------------------------------------- #
    samples = [descriptor(hand("index_ring", cx=600 + i * 6, rotation=i * 1.5)) for i in range(20)]
    template = template_from(samples)
    check("template built from samples", template is not None and len(template) == 42,
          str(None if template is None else len(template)))
    check("matching shape scores high", match_score(template, descriptor(hand("index_ring"))) > 0.8,
          f"{match_score(template, descriptor(hand('index_ring'))):.2f}")
    check("other shape scores low", match_score(template, descriptor(hand("peace"))) < 0.2,
          f"{match_score(template, descriptor(hand('peace'))):.2f}")
    check("missing hand scores zero", match_score(template, None) == 0.0)

    # ---- end to end through the engine ---------------------------------- #
    settings = Settings()
    settings.set("engine.fire_hold_ms", 400)
    settings.add_custom_gesture({
        "id": "learned1", "name": "Learned", "template": template, "samples": 20,
    })
    settings.set_binding("custom:learned1", "media.play_pause")

    engine = GestureEngine(settings)
    t = 1000.0
    for _ in range(60):
        engine.update([hand("rock")], t)
        t += 33.0

    fired: list[str] = []
    for _ in range(40):
        state = engine.update([hand("index_ring", cx=500 + (_ % 5) * 3)], t)
        t += 33.0
        fired.extend(state.fired)
    check("learned gesture fires once held", fired == ["custom:learned1"], str(fired))

    other = GestureEngine(settings)
    t = 1000.0
    for _ in range(60):
        other.update([hand("rock")], t)
        t += 33.0
    fired = []
    for _ in range(40):
        state = other.update([hand("peace")], t)
        t += 33.0
        fired.extend(state.fired)
    check("other poses do not trigger it", "custom:learned1" not in fired, str(fired))

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
