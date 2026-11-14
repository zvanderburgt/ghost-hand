"""Reusable Qt widgets: cards, switch, confidence bars, video view, log."""

from __future__ import annotations

import html
from dataclasses import dataclass

from PySide6.QtCore import (QEasingCurve, QPropertyAnimation, QRectF, QSize,
                            QTimer, Property, Qt, Signal)
from PySide6.QtGui import (QColor, QImage, QPainter, QPainterPath, QPen)
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

from . import theme


# --------------------------------------------------------------------- #
# Layout primitives
# --------------------------------------------------------------------- #


class Card(QFrame):
    def __init__(self, title: str | None = None, parent=None, spacing: int = 10) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 14)
        self.body.setSpacing(spacing)
        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        if title:
            lbl = QLabel(title)
            lbl.setProperty("role", "h2")
            self.header.addWidget(lbl)
            self.header.addStretch(1)
            self.body.addLayout(self.header)
        self.title_label = self.header.itemAt(0).widget() if title else None

    def add(self, widget) -> None:
        self.body.addWidget(widget)


class Divider(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Divider")
        self.setFixedHeight(1)


def hline() -> Divider:
    return Divider()


# --------------------------------------------------------------------- #
# Status pill
# --------------------------------------------------------------------- #


class StatusPill(QWidget):
    STATES = {
        "disarmed": ("Disarmed", theme.TEXT_MUTED, "#34343A"),
        "arming": ("Arming", theme.WARN, "#3A3524"),
        "armed": ("Armed", theme.ACCENT, "#14384A"),
        "error": ("Camera error", theme.BAD, "#3A2429"),
        "demo": ("Demo", theme.GOOD, "#22351F"),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._state = "disarmed"
        self.setFixedHeight(26)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(11, 0, 13, 0)
        lay.setSpacing(7)
        self.dot = QLabel()
        self.dot.setFixedSize(7, 7)
        self.text = QLabel()
        self.text.setStyleSheet("font-size: 11px; font-weight: 600;")
        lay.addWidget(self.dot, 0, Qt.AlignVCenter)
        lay.addWidget(self.text, 0, Qt.AlignVCenter)
        self.set_state("disarmed")

    def set_state(self, state: str) -> None:
        if state not in self.STATES:
            state = "disarmed"
        self._state = state
        label, color, bg = self.STATES[state]
        self.text.setText(label)
        self.text.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {color};")
        self.dot.setStyleSheet(f"background: {color}; border-radius: 3px;")
        self.setStyleSheet(f"background: {bg}; border-radius: 13px;")


# --------------------------------------------------------------------- #
# Toggle switch
# --------------------------------------------------------------------- #


class Switch(QAbstractButton):
    def __init__(self, checked: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = 1.0 if checked else 0.0
        self.setChecked(checked)
        self.anim = QPropertyAnimation(self, b"position", self)
        self.anim.setDuration(140)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def get_position(self) -> float:
        return self._pos

    def set_position(self, value: float) -> None:
        self._pos = float(value)
        self.update()

    position = Property(float, get_position, set_position)

    def _animate(self, on: bool) -> None:
        self.anim.stop()
        self.anim.setStartValue(self._pos)
        self.anim.setEndValue(1.0 if on else 0.0)
        self.anim.start()

    def sizeHint(self) -> QSize:
        return QSize(42, 24)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        track = QRectF(1, 3, self.width() - 2, self.height() - 6)
        on = QColor(theme.ACCENT)
        off = QColor("#45454B")
        col = QColor(
            int(off.red() + (on.red() - off.red()) * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue() + (on.blue() - off.blue()) * self._pos),
        )
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(track, track.height() / 2, track.height() / 2)

        knob = self.height() - 10
        x = 5 + self._pos * (self.width() - knob - 10)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, 5, knob, knob))
        p.end()


# --------------------------------------------------------------------- #
# Confidence bars
# --------------------------------------------------------------------- #


class Bar(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._active = False
        self.setMinimumHeight(6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value: float, active: bool = False) -> None:
        self._value = max(0.0, min(1.0, value))
        self._active = active
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#34343A"))
        p.drawRoundedRect(QRectF(0, 0, self.width(), 6), 3, 3)
        if self._value > 0.005:
            color = QColor(theme.ACCENT if self._active else "#3E7C94")
            p.setBrush(color)
            p.drawRoundedRect(QRectF(0, 0, max(3.0, self.width() * self._value), 6), 3, 3)
        p.end()


@dataclass
class ScoreRow:
    key: str
    name: str
    container: QWidget
    bar: Bar
    value: QLabel


class ScoreBoard(QWidget):
    def __init__(self, max_visible: int = 6, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(7)
        self.rows: dict[str, ScoreRow] = {}
        self.order: list[str] = []
        self.max_visible = max_visible
        self._visible: list[str] = []
        self._lay = lay

    def ensure_rows(self, names: dict[str, str]) -> None:
        for key, name in names.items():
            if key in self.rows:
                continue
            container = QWidget()
            row = QHBoxLayout(container)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            label = QLabel(name)
            label.setFixedWidth(96)
            label.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")
            bar = Bar()
            value = QLabel("0%")
            value.setFixedWidth(36)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value.setStyleSheet(f"font-family: {theme.MONO_FAMILY}; font-size: 10px; color: {theme.TEXT_DIM};")
            row.addWidget(label)
            row.addWidget(bar, 1)
            row.addWidget(value)
            self._lay.addWidget(container)
            self.rows[key] = ScoreRow(key, name, container, bar, value)
            self.order.append(key)

        top = self.order[: self.max_visible]
        for key in self.order:
            self.rows[key].container.setVisible(key in top)
        self._visible = top

    def update_scores(self, scores: dict[str, float], winner: str | None) -> None:
        if not scores:
            # No hand: keep a stable default set of rows at zero rather than
            # collapsing the card and leaving a blank panel.
            self._apply_order(self.order[: self.max_visible])
            for row in self.rows.values():
                row.bar.set_value(0.0, False)
                row.value.setText("0%")
                row.value.setStyleSheet(
                    f"font-family: {theme.MONO_FAMILY}; font-size: 10px; color: {theme.TEXT_DIM};"
                )
            return

        ranked = [k for k, _ in sorted(scores.items(), key=lambda kv: -kv[1])]
        self._apply_order(ranked[: self.max_visible])

        for key, row in self.rows.items():
            value = scores.get(key, 0.0)
            active = key == winner
            row.bar.set_value(value, active)
            row.value.setText(f"{value * 100:.0f}%")
            color = theme.ACCENT if active else theme.TEXT_DIM
            row.value.setStyleSheet(
                f"font-family: {theme.MONO_FAMILY}; font-size: 10px; color: {color};"
            )

    def _apply_order(self, top: list[str]) -> None:
        if set(top) == set(self._visible):
            return
        for key in self.rows:
            self._lay.removeWidget(self.rows[key].container)
        for index, key in enumerate(top):
            self._lay.insertWidget(index, self.rows[key].container)
        for key in self.rows:
            self.rows[key].container.setVisible(key in top)
        self._visible = list(top)

    def reset(self) -> None:
        for row in self.rows.values():
            row.bar.set_value(0.0, False)
            row.value.setText("0%")


# --------------------------------------------------------------------- #
# Metric rows
# --------------------------------------------------------------------- #


class MetricRow(QWidget):
    def __init__(self, label: str, value: str = "—", parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.key = QLabel(label)
        self.key.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_MUTED};")
        self.val = QLabel(value)
        self.val.setProperty("role", "value")
        self.val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.key)
        lay.addStretch(1)
        lay.addWidget(self.val)

    def set_value(self, text: str) -> None:
        self.val.setText(text)


# --------------------------------------------------------------------- #
# Video view
# --------------------------------------------------------------------- #


class VideoView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._message = "Waiting for camera…"
        self._detail = ""
        self.setMinimumSize(320, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, image: QImage | None) -> None:
        self._image = image
        self.update()

    def show_message(self, message: str, detail: str = "") -> None:
        self._image = None
        self._message = message
        self._detail = detail
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        p.setClipPath(path)

        p.fillRect(rect, QColor("#141416"))

        if self._image is not None and not self._image.isNull():
            size = self._image.size()
            scale = min(rect.width() / size.width(), rect.height() / size.height())
            w, h = size.width() * scale, size.height() * scale
            target = QRectF(
                rect.x() + (rect.width() - w) / 2,
                rect.y() + (rect.height() - h) / 2,
                w, h,
            )
            p.drawImage(target, self._image)
        else:
            p.setPen(QColor(theme.TEXT_MUTED))
            f = p.font()
            f.setPointSizeF(11.0)
            p.setFont(f)
            p.drawText(
                rect.adjusted(24, 0, -24, -14),
                Qt.AlignCenter | Qt.TextWordWrap,
                self._message,
            )
            if self._detail:
                p.setPen(QColor(theme.TEXT_DIM))
                f.setPointSizeF(9.5)
                p.setFont(f)
                p.drawText(
                    rect.adjusted(24, 26, -24, 0),
                    Qt.AlignCenter | Qt.TextWordWrap,
                    self._detail,
                )
        p.end()


# --------------------------------------------------------------------- #
# Event log
# --------------------------------------------------------------------- #


class EventLog(QPlainTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.document().setMaximumBlockCount(500)
        self.setPlaceholderText("Gesture events will appear here…")

    def add_line(self, text: str) -> None:
        low = text.lower()
        if "fired" in low:
            color = theme.ACCENT
        elif "fail" in low or "error" in low:
            color = theme.BAD
        elif "volume" in low:
            color = theme.GOOD
        elif "practice" in low:
            color = theme.TEXT_DIM
        else:
            color = theme.TEXT_MUTED
        self.appendHtml(
            f'<span style="color:{color};">{html.escape(text)}</span>'
        )
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


# --------------------------------------------------------------------- #
# Segmented control
# --------------------------------------------------------------------- #


class Segmented(QWidget):
    changed = Signal(int)

    def __init__(self, options: list[str], parent=None) -> None:
        super().__init__(parent)
        self.setStyleSheet("background: #232326; border-radius: 7px;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.buttons: list[QPushButton] = []
        for i, text in enumerate(options):
            btn = QPushButton(text)
            btn.setObjectName("Segment")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setChecked(i == 0)
            btn.clicked.connect(lambda _=False, idx=i: self._select(idx))
            lay.addWidget(btn)
            self.buttons.append(btn)
        self._index = 0

    def _select(self, index: int) -> None:
        for i, btn in enumerate(self.buttons):
            btn.setChecked(i == index)
        if index != self._index:
            self._index = index
            self.changed.emit(index)

    def set_index(self, index: int) -> None:
        self._select(index)

    @property
    def index(self) -> int:
        return self._index


class FlashLabel(QLabel):
    """Transient banner used for 'FIRED' feedback."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            f"color: {theme.ACCENT}; font-size: 11px; font-weight: 600;"
        )
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self.setText(""))

    def flash(self, text: str, ms: int = 1400) -> None:
        self.setText(text)
        self._timer.start(ms)
