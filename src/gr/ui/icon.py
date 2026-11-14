"""Ghost Hand icon: a 21-landmark hand skeleton with a cold glow.

Drawn as vectors at every size rather than downscaled from one bitmap, because
the tray icon has to stay legible at 16 px. Thick pale bones win there - the
faint-glow variants smear into a smudge below 24 px.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QRadialGradient)

ACCENT = QColor("#4CC2FF")
BONE_TOP = QColor("#EDFCFF")
BONE_BOTTOM = QColor("#59C9F3")
JOINT = QColor("#F6FEFF")

# 21 MediaPipe landmark positions for a claw sweeping toward the thumb,
# normalised into a unit box. Every finger's distal joints rotate the same way,
# so the hand reads as one raking claw rather than a symmetric fan.
LANDMARKS: tuple[tuple[float, float], ...] = (
    (0.6246, 0.9073), (0.4224, 0.8062), (0.3887, 0.8062),
    (0.1951, 0.7870), (0.0000, 0.8221), (0.4392, 0.6208),
    (0.4067, 0.3896), (0.2908, 0.2696), (0.1827, 0.1576),
    (0.6077, 0.5871), (0.6077, 0.3536), (0.5097, 0.2187),
    (0.4181, 0.0927), (0.7762, 0.6208), (0.8087, 0.3896),
    (0.7304, 0.2423), (0.6573, 0.1048), (0.9278, 0.6882),
    (1.0000, 0.4661), (0.9485, 0.3075), (0.9003, 0.1594),
)

BONES: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)

FINGERTIPS = (4, 8, 12, 16, 20)
CONTENT_WIDTH = 1.0
CONTENT_HEIGHT = 0.815


def _points(size: int) -> list[tuple[float, float]]:
    pad = size * 0.105
    scale = (size - 2 * pad) / CONTENT_WIDTH
    top = (size - CONTENT_HEIGHT * scale) / 2.0 - 0.092 * scale
    return [(pad + x * scale, top + y * scale) for x, y in LANDMARKS]


def _pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)

    # -- tile --------------------------------------------------------- #
    pad = size * 0.03
    tile = QRectF(pad, pad, size - 2 * pad, size - 2 * pad)
    radius = size * 0.24
    grad = QLinearGradient(tile.topLeft(), tile.bottomRight())
    grad.setColorAt(0.0, QColor("#162832"))
    grad.setColorAt(1.0, QColor("#070C10"))
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(tile, radius, radius)

    # -- cold halo behind the hand ------------------------------------ #
    halo = QRadialGradient(QPointF(size * 0.5, size * 0.46), size * 0.44)
    halo.setColorAt(0.0, QColor(76, 194, 255, 58))
    halo.setColorAt(1.0, QColor(76, 194, 255, 0))
    p.setBrush(QBrush(halo))
    p.drawEllipse(tile)

    pts = _points(size)

    # Detail drops away as the icon shrinks: at 16 px joints and glow turn the
    # hand into a smudge, so only slightly thicker bones survive.
    detailed = size >= 32
    show_glow = size >= 40
    if size >= 64:
        bone_width = size * 0.050
    elif size >= 32:
        bone_width = size * 0.062
    else:
        bone_width = size * 0.085
    bone_width = max(1.0, bone_width)

    if show_glow:
        glow = QPen(QColor(76, 194, 255, 46), bone_width * 2.2)
        glow.setCapStyle(Qt.RoundCap)
        p.setPen(glow)
        for a, b in BONES:
            p.drawLine(QPointF(*pts[a]), QPointF(*pts[b]))

    # -- bones --------------------------------------------------------- #
    bone_grad = QLinearGradient(QPointF(0, size * 0.10), QPointF(0, size * 0.90))
    bone_grad.setColorAt(0.0, BONE_TOP)
    bone_grad.setColorAt(1.0, BONE_BOTTOM)
    bone_pen = QPen(QBrush(bone_grad), bone_width)
    bone_pen.setCapStyle(Qt.RoundCap)
    p.setPen(bone_pen)
    for a, b in BONES:
        p.drawLine(QPointF(*pts[a]), QPointF(*pts[b]))

    # -- joints (knuckles, not bulbs) ---------------------------------- #
    if detailed:
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(JOINT))
        for index, (x, y) in enumerate(pts):
            radius = max(1.0, size * (0.022 if index in FINGERTIPS else 0.013))
            p.drawEllipse(QPointF(x, y), radius, radius)

    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256):
        icon.addPixmap(_pixmap(size))
    return icon


def status_dot(color: str, size: int = 10) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(0, 0, size, size)
    p.end()
    return pm
