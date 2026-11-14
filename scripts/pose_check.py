"""Sanity-check the synthetic hand geometry + pose classifier.

    python scripts/pose_check.py

Writes debug/pose-grid.png with every pose drawn, and prints the top scores.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import DEBUG_DIR, GESTURES  # noqa: E402
from gr.draw import draw_hand  # noqa: E402
from gr.gestures import extract_features, score_poses  # noqa: E402
from gr.synthetic import POSE_SPECS, make_hand  # noqa: E402

W, H = 640, 480
POSES = list(POSE_SPECS.keys())


def main() -> int:
    cols = 4
    rows = (len(POSES) + cols - 1) // cols
    tiles = []

    for pose in POSES:
        img = np.full((H, W, 3), 24, np.uint8)
        hand = make_hand(pose, W, H, size_px=H * 0.62, center=(W * 0.5, H * 0.55))
        feats = extract_features(hand)
        scores = score_poses(feats) if feats else {}
        top = max(scores.items(), key=lambda kv: kv[1]) if scores else ("-", 0)
        draw_hand(img, hand, None)

        label = f"{pose}  -> {top[0]} {top[1]:.2f}"
        cv2.putText(img, label, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (120, 220, 120) if top[0] == pose else (90, 120, 240), 1, cv2.LINE_AA)
        if feats:
            ext = " ".join(f"{k[0]}:{v:.1f}" for k, v in feats.ext.items())
            cv2.putText(img, f"{ext}  ang={feats.thumb_angle:.0f}",
                        (10, H - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)
        tiles.append(cv2.resize(img, (W // 2, H // 2)))

        print(f"\n{pose}")
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:4]
        print("   " + "  ".join(f"{k}={v:.2f}" for k, v in ranked))

    while len(tiles) % cols:
        tiles.append(np.full_like(tiles[0], 24))

    grid_rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    grid = np.vstack(grid_rows)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    out = DEBUG_DIR / "pose-grid.png"
    cv2.imwrite(str(out), grid)
    print(f"\nwrote {out}  ({grid.shape[1]}x{grid.shape[0]})")

    misses = []
    for pose in POSES:
        hand = make_hand(pose, W, H, size_px=H * 0.62, center=(W * 0.5, H * 0.55))
        feats = extract_features(hand)
        scores = score_poses(feats) if feats else {}
        if not scores:
            misses.append(pose)
            continue
        best, value = max(scores.items(), key=lambda kv: kv[1])
        if best != pose or value < 0.55:
            misses.append(f"{pose}(->{best} {value:.2f})")
    print("\nMISMATCHES:", ", ".join(misses) if misses else "none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
