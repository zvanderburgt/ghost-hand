"""Render the demo source to docs/demo.gif for the README.

    python scripts/make_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import APP_NAME, GESTURES, Settings  # noqa: E402
from gr.draw import ACCENT, GREEN, draw_hand, draw_hud  # noqa: E402
from gr.gestures import GestureEngine  # noqa: E402
from gr.synthetic import demo_frame  # noqa: E402

POSES = ["rock", "peace", "thumbs_up", "thumb_left", "point_up", "fist"]
FPS = 8
SECONDS = 14
OUT = ROOT / "docs" / "demo.gif"


def _flash(img: np.ndarray, text: str) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.7
    (tw, th), _ = cv2.getTextSize(text, font, scale, 2)
    h, w = img.shape[:2]
    x = (w - tw) // 2
    y = h - 34
    cv2.rectangle(img, (x - 14, y - th - 12), (x + tw + 14, y + 10), (32, 32, 34), -1)
    cv2.putText(img, text, (x, y), font, scale, ACCENT, 2, cv2.LINE_AA)


def main() -> int:
    settings = Settings()
    settings.set("safety.practice_mode", True)
    engine = GestureEngine(settings)

    frames: list[Image.Image] = []
    flash_text = ""
    flash_until = 0.0
    t0 = 1000.0

    for index in range(FPS * SECONDS):
        now = t0 + index * (1000.0 / FPS)
        # Synthetic clock runs 2x so each pose lasts ~2 s.
        frame, hands = demo_frame(settings, (now - t0) * 2.0, poses=POSES)
        state = engine.update(hands, now)

        img = frame.color.copy()
        label = state.stable_label or state.label
        for hand in hands:
            draw_hand(img, hand, label)

        if state.fired:
            gesture = state.fired[0]
            action = settings.binding_for(gesture)
            flash_text = f"{settings.gesture_label(gesture)}  ->  {settings.action_label(action)}"
            flash_until = now + 1100

        hud = [
            (label or "no gesture").upper(),
            "ARMED" if state.armed else "disarmed",
            "practice mode",
        ]
        draw_hud(img, hud, accent=GREEN if state.armed else ACCENT)

        cv2.putText(img, APP_NAME, (img.shape[1] - 168, img.shape[0] - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, ACCENT, 1, cv2.LINE_AA)
        if now < flash_until and flash_text:
            _flash(img, flash_text)

        small = cv2.resize(img, (480, 270), interpolation=cv2.INTER_AREA)
        frames.append(Image.fromarray(cv2.cvtColor(small, cv2.COLOR_BGR2RGB)))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / FPS),
        loop=0,
        optimize=True,
    )
    size = OUT.stat().st_size / (1024 * 1024)
    print(f"wrote {OUT}  ({len(frames)} frames, {size:.1f} MB)")
    return 0 if size < 5.5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
