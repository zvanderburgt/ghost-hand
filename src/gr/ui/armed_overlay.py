"""A small pill that appears at the bottom of the screen while armed.

It is a click-through, never-focused tool window so it can sit over any app
without stealing input. Colour follows the Windows accent setting.
"""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

FALLBACK_ACCENT = QColor("#4CC2FF")
MIN_LUMINANCE = 0.45


def accent_from_abgr(value: int) -> QColor:
    """Windows stores the accent as 0xAABBGGRR."""
    red = value & 0xFF
    green = (value >> 8) & 0xFF
    blue = (value >> 16) & 0xFF
    return QColor(red, green, blue)


def luminance(color: QColor) -> float:
    return 0.2126 * color.redF() + 0.7152 * color.greenF() + 0.0722 * color.blueF()


def ensure_contrast(color: QColor, minimum: float = MIN_LUMINANCE) -> QColor:
    """Lift very dark accents so the pill stays readable on dark backgrounds."""
    if luminance(color) >= minimum:
        return QColor(color)
    white = QColor(255, 255, 255)
    blend = 0.0
    result = QColor(color)
    while blend < 1.0:
        blend += 0.08
        result = QColor(
            round(color.red() + (white.red() - color.red()) * blend),
            round(color.green() + (white.green() - color.green()) * blend),
            round(color.blue() + (white.blue() - color.blue()) * blend),
        )
        if luminance(result) >= minimum:
            break
    return result


def system_accent_color() -> QColor:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as key:
            value, _ = winreg.QueryValueEx(key, "AccentColor")
        return ensure_contrast(accent_from_abgr(int(value)))
    except Exception:  # noqa: BLE001 - missing key, non-Windows
        return QColor(FALLBACK_ACCENT)


def pill_rect(screen: QRect, size: QSize, margin: int = 72) -> QRect:
    """Centred horizontally, sitting above the bottom edge of `screen`."""
    x = screen.x() + (screen.width() - size.width()) // 2
    y = screen.y() + screen.height() - size.height() - margin
    return QRect(x, y, size.width(), size.height())


class ArmedOverlay(QWidget):
    WIDTH = 132
    HEIGHT = 36

    def __init__(self, parent=None) -> None:
        flags = (Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                 | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        super().__init__(parent, flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self._accent = system_accent_color()
        self._fading_out = False

        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.finished.connect(self._on_anim_finished)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)

    # ------------------------------------------------------------------ #

    def show_armed(self, hold_ms: int = 2600) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(pill_rect(screen.availableGeometry(), self.size()))
        self._accent = system_accent_color()
        self._fading_out = False
        self.setWindowOpacity(0.0)
        self.show()
        self._anim.stop()
        self._anim.setDuration(150)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._hide_timer.start(hold_ms)

    def _fade_out(self) -> None:
        if not self.isVisible():
            return
        self._fading_out = True
        self._anim.stop()
        self._anim.setDuration(320)
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_anim_finished(self) -> None:
        if self._fading_out:
            self.hide()

    # ------------------------------------------------------------------ #

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        pill = QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
        painter.setPen(QPen(QColor(self._accent.red(), self._accent.green(),
                                   self._accent.blue(), 170), 1.0))
        painter.setBrush(QColor(22, 24, 28, 235))
        painter.drawRoundedRect(pill, self.height() / 2.0, self.height() / 2.0)

        painter.setPen(Qt.NoPen)
        painter.setBrush(self._accent)
        painter.drawEllipse(QRectF(18.0, self.height() / 2.0 - 4.0, 8.0, 8.0))

        font = painter.font()
        font.setPointSizeF(9.0)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(240, 245, 250))
        painter.drawText(
            QRectF(34.0, 0.0, self.width() - 42.0, float(self.height())),
            int(Qt.AlignVCenter | Qt.AlignLeft),
            "ARMED",
        )
        painter.end()
