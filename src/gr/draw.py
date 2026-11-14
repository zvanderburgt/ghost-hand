"""Frame annotation helpers (shared by the preview window and clip recorder)."""

from __future__ import annotations

import cv2
import numpy as np

from .hands import FINGERTIPS, HAND_CONNECTIONS, Hand

ACCENT = (255, 194, 76)        # BGR for #4CC2FF
ACCENT_DIM = (150, 110, 45)
WHITE = (245, 245, 245)
MUTED = (150, 150, 150)
GREEN = (120, 220, 130)
AMBER = (70, 190, 250)
RED = (90, 90, 235)


def draw_hand(img: np.ndarray, hand: Hand, label: str | None, accent=ACCENT) -> None:
    pts = [(int(x), int(y)) for x, y in hand.px]
    overlay = img.copy()

    for a, b in HAND_CONNECTIONS:
        cv2.line(overlay, pts[a], pts[b], accent, 2, cv2.LINE_AA)
    for tip in FINGERTIPS:
        cv2.circle(overlay, pts[tip], 6, accent, -1, cv2.LINE_AA)
    for i, p in enumerate(pts):
        if i in FINGERTIPS:
            continue
        cv2.circle(overlay, p, 3, WHITE, -1, cv2.LINE_AA)

    cv2.addWeighted(overlay, 0.85, img, 0.15, 0, img)

    x0, y0, x1, y1 = hand.bbox
    cv2.rectangle(img, (x0, y0), (x1, y1), ACCENT_DIM, 1, cv2.LINE_AA)

    if label:
        text = f"{label}  {hand.handedness[0]}" if hand.handedness else label
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        bx, by = x0, max(th + 10, y0)
        cv2.rectangle(img, (bx, by - th - 8), (bx + tw + 10, by), (32, 32, 32), -1)
        cv2.putText(img, text, (bx + 5, by - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    WHITE, 1, cv2.LINE_AA)


def draw_hud(img: np.ndarray, lines: list[str], accent=ACCENT) -> None:
    if not lines:
        return
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.5
    pad = 8
    widths = [cv2.getTextSize(t, font, scale, 1)[0][0] for t in lines]
    box_w = max(widths) + pad * 2
    box_h = len(lines) * 20 + pad * 2
    x = 12
    y = 12

    roi = img[y:y + box_h, x:x + box_w]
    if roi.size:
        dark = np.zeros_like(roi)
        cv2.addWeighted(dark, 0.55, roi, 0.45, 0, roi)

    for i, text in enumerate(lines):
        cv2.putText(img, text, (x + pad, y + pad + 14 + i * 20), font, scale,
                    accent if i == 0 else WHITE, 1, cv2.LINE_AA)


def draw_depth_preview(depth_mm: np.ndarray, max_m: float = 3.0) -> np.ndarray:
    """Colorised depth for the preview tab."""
    d = depth_mm.astype(np.float32) / 1000.0
    d = np.clip(d, 0, max_m)
    norm = (d / max_m * 255).astype(np.uint8)
    norm[depth_mm == 0] = 0
    colored = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)
    colored[depth_mm == 0] = (28, 28, 28)
    return colored
