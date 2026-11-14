"""Classifier regression tests, including the real-world near-misses.

    python scripts/pose_regression.py

Two families of cases:
  * the canonical poses from synthetic.py
  * "tricky" hands that used to misclassify: a fist whose thumb rests over the
    fingers (reads as a thumbs-up), and left/right thumbs that tilt upward.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.gestures import extract_features, score_poses  # noqa: E402
from gr.synthetic import POSE_SPECS, make_hand  # noqa: E402

W, H, SIZE, CENTER = 640, 480, 300.0, (320.0, 264.0)


def classify(hand) -> tuple[str, float, dict[str, float]]:
    feats = extract_features(hand)
    if feats is None:
        return "-", 0.0, {}
    scores = score_poses(feats)
    label, value = max(scores.items(), key=lambda kv: kv[1])
    return label, value, scores


def with_thumb(pose: str, tip_units: tuple[float, float]):
    """Rebuild a hand with the thumb tip moved to a specific position."""
    hand = make_hand(pose, W, H, size_px=SIZE, center=CENTER)
    cx, cy = CENTER
    tip = (cx + tip_units[0] * SIZE, cy + tip_units[1] * SIZE)
    px = list(hand.px)
    mcp = px[2]
    px[4] = tip
    px[3] = ((mcp[0] + tip[0]) / 2.0, (mcp[1] + tip[1]) / 2.0)
    hand.px = px
    return hand


# (description, pose, thumb tip in hand units, expected label)
#
# Thumb tips are placed at a realistic distance from the thumb MCP (lm2 at
# roughly (-0.28, 0.50)); ~0.35 hand units is a fully extended thumb, so the
# "comfortable" cases below are what a relaxed gesture actually looks like.
TRICKY = [
    # A fist's thumb lies across the fingers, level with or below the index
    # knuckle. This used to read as "thumbs up".
    ("fist, thumb across fingers", "fist", (-0.05, 0.34), "fist"),
    ("fist, thumb high on fingers", "fist", (-0.08, 0.25), "fist"),
    ("fist, thumb at palm edge", "fist", (-0.25, 0.42), "fist"),
    # Comfortable sideways thumbs, which used to need over-extension.
    ("thumb left, 25 deg up", "thumb_left", (-0.609, 0.381), "thumb_left"),
    ("thumb left, 10 deg down", "thumb_left", (-0.625, 0.561), "thumb_left"),
    ("thumb left, 40 deg up", "thumb_left", (-0.548, 0.275), "thumb_left"),
    ("thumb right, 15 deg up", "thumb_right", (0.550, 0.409), "thumb_right"),
    ("thumb right, 15 deg down", "thumb_right", (0.550, 0.591), "thumb_right"),
    # Vertical thumbs must keep winning, including with a natural tilt.
    ("thumbs up, slight tilt", "thumbs_up", (-0.34, -0.02), "thumbs_up"),
    ("thumbs up, 20 deg tilt", "thumbs_up", (-0.40, 0.17), "thumbs_up"),
    ("thumbs down, slight tilt", "thumbs_down", (-0.22, 1.02), "thumbs_down"),
]


def main() -> int:
    failures: list[str] = []
    print("canonical poses")
    for pose in POSE_SPECS:
        label, value, scores = classify(make_hand(pose, W, H, size_px=SIZE, center=CENTER))
        runner = sorted(scores.values(), reverse=True)[1] if len(scores) > 1 else 0.0
        ok = label == pose and value >= 0.55
        print(f"  {'PASS' if ok else 'FAIL'}  {pose:<12} -> {label:<12} {value:.2f}  (next {runner:.2f})")
        if not ok:
            failures.append(f"canonical {pose} -> {label} {value:.2f}")

    print("\ntricky hands (the reported misclassifications)")
    for desc, pose, tip, expected in TRICKY:
        label, value, scores = classify(with_thumb(pose, tip))
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:3]
        ok = label == expected and value >= 0.55
        detail = "  ".join(f"{k}={v:.2f}" for k, v in ranked)
        print(f"  {'PASS' if ok else 'FAIL'}  {desc:<28} -> {label:<12} {value:.2f}   [{detail}]")
        if not ok:
            failures.append(f"{desc} -> {label} {value:.2f} (wanted {expected})")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S):")
        for item in failures:
            print(f"  - {item}")
        return 1
    print("all cases pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
