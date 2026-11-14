"""Render the real app icon at several sizes for review.

    python scripts/icon_preview.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import DEBUG_DIR  # noqa: E402
from gr.ui.icon import app_icon  # noqa: E402

SIZES = [16, 24, 32, 48, 64, 128, 256]


def main() -> int:
    app = QApplication(sys.argv)
    icon = app_icon()

    width = sum(s + 24 for s in SIZES)
    height = max(SIZES) + 48
    image = QImage(width, height, QImage.Format_ARGB32)
    image.fill(QColor("#141416"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    x = 12
    for size in SIZES:
        pixmap = icon.pixmap(size, size)
        painter.drawPixmap(QPointF(x, (height - size) / 2), pixmap)
        painter.setPen(QColor("#9A9AA2"))
        painter.drawText(QRectF(x, height - 30, size, 20), Qt.AlignCenter, f"{size}")
        x += size + 24
    painter.end()

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    image.save(str(DEBUG_DIR / "icon-final.png"))
    app.quit()
    print("saved debug/icon-final.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
