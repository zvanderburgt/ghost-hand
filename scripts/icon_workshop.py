"""Icon workshop: render candidate 'Ghost Hand' icons to a contact sheet.

    python scripts/icon_workshop.py

Writes debug/icon-variants.png (large previews) and debug/icon-sizes.png
(16/24/32/48 px strips, because tray icons are judged at 16 px).
"""

from __future__ import annotations

import sys
from pathlib import Path

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QImage, QLinearGradient, QPainter,
                           QPainterPath, QPen, QRadialGradient)
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import DEBUG_DIR  # noqa: E402
from gr.hands import HAND_CONNECTIONS  # noqa: E402
from gr.synthetic import make_hand  # noqa: E402

ACCENT = QColor("#4CC2FF")
JOINT = QColor("#EAF9FF")
BONE_SOFT = QColor("#9FD8F0")

VARIANTS = ["thin", "glow", "bones", "minimal", "halo", "wisp"]


def landmarks(size: int = 256):
    """Normalised 21 landmarks laid out like an upright open hand."""
    hand = make_hand("open_palm", 256, 256, size_px=118.0, center=(128.0, 140.0))
    xs = [p[0] for p in hand.px]
    ys = [p[1] for p in hand.px]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    span = max(x1 - x0, y1 - y0)
    pad = size * 0.16
    scale = (size - 2 * pad) / span
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return [
        (size / 2 + (x - cx) * scale, size / 2 + (y - cy) * scale + size * 0.02)
        for x, y in hand.px
    ]


def _background(p: QPainter, size: int, halo: bool) -> None:
    rect = QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, QColor("#1B2C36"))
    grad.setColorAt(1.0, QColor("#0A1015"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(rect, size * 0.22, size * 0.22)

    if halo:
        radial = QRadialGradient(QPointF(size * 0.5, size * 0.46), size * 0.46)
        radial.setColorAt(0.0, QColor(76, 194, 255, 70))
        radial.setColorAt(1.0, QColor(76, 194, 255, 0))
        p.setBrush(QBrush(radial))
        p.drawEllipse(QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92))


def _wisp(p: QPainter, size: int, pts) -> None:
    """A faint ghost tail curling under the wrist."""
    wrist_x, wrist_y = pts[0]
    for offset, alpha in ((-0.06, 120), (0.0, 90), (0.06, 60)):
        path = QPainterPath(QPointF(wrist_x + size * offset, wrist_y + size * 0.04))
        path.cubicTo(
            QPointF(wrist_x + size * (offset + 0.10), wrist_y + size * 0.16),
            QPointF(wrist_x + size * (offset - 0.10), wrist_y + size * 0.24),
            QPointF(wrist_x + size * (offset + 0.02), wrist_y + size * 0.32),
        )
        pen = QPen(QColor(76, 194, 255, alpha), max(1.2, size * 0.012))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)


def draw(p: QPainter, variant: str, size: int) -> None:
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    pts = landmarks(size)
    halo = variant in ("glow", "halo", "wisp")
    _background(p, size, halo)

    if variant == "wisp":
        _wisp(p, size, pts)

    if variant == "minimal":
        # Only the finger chains plus the palm arc: survives 16 px.
        chains = [(0, 5), (5, 6), (6, 7), (7, 8),
                  (0, 9), (9, 10), (10, 11), (11, 12),
                  (0, 13), (13, 14), (14, 15), (15, 16),
                  (0, 17), (17, 18), (18, 19), (19, 20),
                  (0, 1), (1, 2), (2, 3), (3, 4)]
        pen = QPen(ACCENT, max(1.4, size * 0.045))
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        for a, b in chains:
            p.drawLine(QPointF(*pts[a]), QPointF(*pts[b]))
        return

    width = size * (0.05 if variant == "bones" else 0.028)
    joint = size * (0.030 if variant == "bones" else 0.020)

    if variant in ("glow", "halo", "wisp"):
        glow = QPen(QColor(76, 194, 255, 60), width * 2.6)
        glow.setCapStyle(Qt.RoundCap)
        p.setPen(glow)
        for a, b in HAND_CONNECTIONS:
            p.drawLine(QPointF(*pts[a]), QPointF(*pts[b]))

    pen = QPen(ACCENT if variant != "bones" else BONE_SOFT, width)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    for a, b in HAND_CONNECTIONS:
        p.drawLine(QPointF(*pts[a]), QPointF(*pts[b]))

    if variant != "minimal":
        p.setPen(Qt.NoPen)
        for index, (x, y) in enumerate(pts):
            radius = joint * (1.25 if index in (0, 4, 8, 12, 16, 20) else 0.85)
            p.setBrush(QBrush(JOINT if variant == "bones" else ACCENT.lighter(150)))
            p.drawEllipse(QPointF(x, y), radius, radius)


def render(variant: str, size: int) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    draw(painter, variant, size)
    painter.end()
    return image


def main() -> int:
    app = QApplication(sys.argv)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    cell = 208
    cols = 3
    rows = math.ceil(len(VARIANTS) / cols)
    sheet = QImage(cols * cell, rows * (cell + 34), QImage.Format_ARGB32)
    sheet.fill(QColor("#141416"))
    painter = QPainter(sheet)
    for index, variant in enumerate(VARIANTS):
        col, row = index % cols, index // cols
        x, y = col * cell, row * (cell + 34)
        painter.drawImage(QPointF(x + 8, y + 8), render(variant, cell - 16))
        painter.setPen(QColor("#C8C8CE"))
        font = painter.font()
        font.setPointSizeF(10)
        painter.setFont(font)
        painter.drawText(QRectF(x, y + cell - 8, cell, 22), Qt.AlignCenter, variant)
    painter.end()
    sheet.save(str(DEBUG_DIR / "icon-variants.png"))

    strip = QImage(4 * 74, len(VARIANTS) * 74, QImage.Format_ARGB32)
    strip.fill(QColor("#141416"))
    painter = QPainter(strip)
    for row, variant in enumerate(VARIANTS):
        for col, size in enumerate((16, 24, 32, 48)):
            painter.drawImage(QPointF(col * 74 + 12, row * 74 + 12), render(variant, size))
    painter.end()
    strip.save(str(DEBUG_DIR / "icon-sizes.png"))

    app.quit()
    print("saved debug/icon-variants.png and debug/icon-sizes.png")
    print("columns:", ", ".join(VARIANTS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
