"""Prototype the claw-pose icon.

    python scripts/claw_workshop.py

Renders three curl strengths at full size plus 16/24/32/48 strips, and prints the
chosen normalised landmark set for pasting into src/gr/ui/icon.py.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter,
                           QPen)
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import DEBUG_DIR  # noqa: E402
from gr.hands import HAND_CONNECTIONS  # noqa: E402
from gr.synthetic import make_hand  # noqa: E402

BONE_TOP = QColor("#EDFCFF")
BONE_BOTTOM = QColor("#59C9F3")
JOINT = QColor("#F6FEFF")


def _offset(point, angle_deg, distance):
    rad = math.radians(angle_deg)
    return (point[0] + math.cos(rad) * distance, point[1] + math.sin(rad) * distance)


def _rotate(point, pivot, angle_rad):
    dx, dy = point[0] - pivot[0], point[1] - pivot[1]
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    return (pivot[0] + dx * cos_a - dy * sin_a,
            pivot[1] + dx * sin_a + dy * cos_a)


def claw_points(curl: float = 0.7):
    """Open-hand skeleton with the distal joints rotated inward.

    Starting from the pose that already reads as a hand at 16 px and only
    curling the tips keeps the silhouette; building palm-out lines from scratch
    produced something that looked like antlers.
    """
    base = make_hand("open_palm", 256, 256, size_px=132.0, center=(128.0, 150.0))
    pts = [tuple(p) for p in base.px]

    palm = (
        sum(pts[i][0] for i in (5, 9, 13, 17)) / 4.0,
        sum(pts[i][1] for i in (5, 9, 13, 17)) / 4.0,
    )

    for chain in ((5, 6, 7, 8), (9, 10, 11, 12), (13, 14, 15, 16), (17, 18, 19, 20)):
        pivot = pts[chain[1]]
        # Every finger hooks the same way - toward the thumb (screen left) - so
        # the hand reads as one sweeping claw instead of a symmetric fan.
        bend = math.radians(-36.0 * curl)
        for joint in chain[2:]:
            pts[joint] = _rotate(pts[joint], pivot, bend)

    # Thumb follows the same sweep.
    pivot = pts[2]
    pts[3] = _rotate(pts[3], pivot, math.radians(-12.0 * curl))
    pts[4] = _rotate(pts[4], pivot, math.radians(-20.0 * curl))
    return pts


def normalise(points, size: int):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0)
    pad = size * 0.10
    scale = (size - 2 * pad) / span
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return [((x - cx) * scale + size / 2, (y - cy) * scale + size / 2) for x, y in points]


def draw(painter: QPainter, points, size: int) -> None:
    painter.setRenderHint(QPainter.Antialiasing, True)
    tile = QRectF(size * 0.03, size * 0.03, size * 0.94, size * 0.94)
    grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
    grad.setColorAt(0.0, QColor("#162832"))
    grad.setColorAt(1.0, QColor("#070C10"))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(grad))
    painter.drawRoundedRect(tile, size * 0.24, size * 0.24)

    pts = normalise(points, size)
    detailed = size >= 32
    if size >= 64:
        width = size * 0.050
    elif size >= 32:
        width = size * 0.062
    else:
        width = size * 0.085
    width = max(1.0, width)

    if size >= 40:
        glow = QPen(QColor(76, 194, 255, 46), width * 2.2)
        glow.setCapStyle(Qt.RoundCap)
        painter.setPen(glow)
        for a, b in HAND_CONNECTIONS:
            painter.drawLine(QPointF(*pts[a]), QPointF(*pts[b]))

    bone = QLinearGradient(QPointF(0, size * 0.10), QPointF(0, size * 0.90))
    bone.setColorAt(0.0, BONE_TOP)
    bone.setColorAt(1.0, BONE_BOTTOM)
    pen = QPen(QBrush(bone), width)
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    for a, b in HAND_CONNECTIONS:
        painter.drawLine(QPointF(*pts[a]), QPointF(*pts[b]))

    if detailed:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(JOINT))
        for index, (x, y) in enumerate(pts):
            radius = max(1.0, size * (0.022 if index in (4, 8, 12, 16, 20) else 0.013))
            painter.drawEllipse(QPointF(x, y), radius, radius)


def render(points, size: int) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    p = QPainter(image)
    draw(p, points, size)
    p.end()
    return image


def main() -> int:
    app = QApplication(sys.argv)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    curls = [0.75, 1.0, 1.25]

    cell = 220
    sheet = QImage(cell * 3, cell + 30, QImage.Format_ARGB32)
    sheet.fill(QColor("#141416"))
    p = QPainter(sheet)
    for col, curl in enumerate(curls):
        p.drawImage(QPointF(col * cell + 8, 8), render(claw_points(curl), cell - 16))
        p.setPen(QColor("#C8C8CE"))
        p.drawText(QRectF(col * cell, cell - 6, cell, 20), Qt.AlignCenter, f"curl {curl}")
    p.end()
    sheet.save(str(DEBUG_DIR / "claw-variants.png"))

    strip = QImage(4 * 74, 3 * 74, QImage.Format_ARGB32)
    strip.fill(QColor("#141416"))
    p = QPainter(strip)
    for row, curl in enumerate(curls):
        for col, size in enumerate((16, 24, 32, 48)):
            p.drawImage(QPointF(col * 74 + 12, row * 74 + 12), render(claw_points(curl), size))
    p.end()
    strip.save(str(DEBUG_DIR / "claw-sizes.png"))

    best = claw_points(1.0)
    xs = [q[0] for q in best]
    ys = [q[1] for q in best]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    span = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    norm = [((x - cx) / span + 0.5, (y - cy) / span + 0.5) for x, y in best]
    print("LANDMARKS (curl 1.0) = (")
    for i in range(0, 21, 3):
        print("    " + ", ".join(f"({x:.4f}, {y:.4f})" for x, y in norm[i:i + 3]) + ",")
    print(")")
    print("height fraction:", round((y1 - y0) / span, 3))

    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
