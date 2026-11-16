"""Live per-application volume mixer and dial-target picker."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QSlider, QVBoxLayout,
                               QWidget)

from ..app_audio import AppAudio, AppAudioError, AudioApp
from ..config import Settings, app_name
from . import theme


class AudioDialog(QDialog):
    """The Windows Volume Mixer, plus the gesture dial's target."""

    changed = Signal()

    def __init__(self, settings: Settings, parent=None,
                 audio: AppAudio | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.audio = audio or AppAudio()
        self._dial_buttons: dict[str, QPushButton] = {}
        self.setWindowTitle("App volume")
        self.setModal(True)
        self.resize(700, 520)
        self._build()
        self._refresh()

    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        title = QLabel("App volume")
        title.setProperty("role", "h1")
        hint = QLabel(
            "These are the same sliders as the Windows Volume Mixer; changes apply "
            "immediately. «Use for dial» points the gesture dial at that app instead "
            "of the system volume."
        )
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(hint)

        head = QHBoxLayout()
        self.dial_label = QLabel()
        self.dial_label.setProperty("role", "sub")
        refresh = QPushButton("Refresh")
        refresh.setToolTip("Re-scan for apps that started or stopped playing audio")
        refresh.clicked.connect(self._refresh)
        head.addWidget(self.dial_label)
        head.addStretch(1)
        head.addWidget(refresh)
        root.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.list_host = QWidget()
        self.rows = QVBoxLayout(self.list_host)
        self.rows.setContentsMargins(0, 0, 6, 0)
        self.rows.setSpacing(10)
        self.scroll.setWidget(self.list_host)
        root.addWidget(self.scroll, 1)

        self.status = QLabel()
        self.status.setProperty("role", "sub")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        bottom = QHBoxLayout()
        system = QPushButton("System volume")
        system.setToolTip("Point the dial back at the master volume")
        system.clicked.connect(lambda: self._set_dial_target("system"))
        focused = QPushButton("Focused app")
        focused.setToolTip("Follow whichever app is focused when the dial engages")
        focused.clicked.connect(lambda: self._set_dial_target("foreground"))
        done = QPushButton("Done")
        done.setProperty("variant", "accent")
        done.clicked.connect(self.accept)
        bottom.addWidget(system)
        bottom.addWidget(focused)
        bottom.addStretch(1)
        bottom.addWidget(done)
        root.addLayout(bottom)

    # ------------------------------------------------------------------ #

    def _refresh(self) -> None:
        self._status("")
        while self.rows.count():
            item = self.rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._dial_buttons.clear()

        self.audio.refresh()
        try:
            apps = self.audio.apps()
        except AppAudioError as exc:
            self._note(str(exc))
            self._refresh_dial_label()
            return

        self._refresh_dial_label()
        if not apps:
            self._note("No apps are playing audio right now. Start something, then Refresh.")
            return

        for app in apps:
            self._add_row(app)
        self._update_dial_buttons()
        self.rows.addStretch(1)

    def _note(self, text: str) -> None:
        note = QLabel(text)
        note.setProperty("role", "sub")
        note.setWordWrap(True)
        self.rows.addWidget(note)
        self.rows.addStretch(1)

    def _add_row(self, app: AudioApp) -> None:
        row = QWidget()
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(10)

        name = QLabel(app.process)
        name.setMinimumWidth(170)
        name.setToolTip(f"PID {app.pid} · {app.sessions} session(s)")
        line.addWidget(name)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, 100)
        slider.setMinimumWidth(180)
        slider.setValue(round(app.volume * 100))
        line.addWidget(slider, 1)

        value = QLabel(f"{slider.value()}%")
        value.setFixedWidth(40)
        value.setStyleSheet(
            f"font-family: {theme.MONO_FAMILY}; font-size: 11px; color: {theme.TEXT_MUTED};"
        )
        line.addWidget(value)

        mute = QCheckBox("Mute")
        mute.setChecked(app.muted)
        line.addWidget(mute)

        dial = QPushButton()
        line.addWidget(dial)
        self._dial_buttons[app.process] = dial

        slider.valueChanged.connect(
            lambda v, p=app.process, lab=value: self._on_volume(p, v, lab)
        )
        mute.toggled.connect(
            lambda on, p=app.process, cb=mute: self._on_mute(p, on, cb)
        )
        dial.clicked.connect(lambda _=False, p=app.process: self._use_for_dial(p))

        self.rows.addWidget(row)

    # -- actions ---------------------------------------------------------- #

    def _on_volume(self, process: str, value: int, label: QLabel) -> None:
        label.setText(f"{value}%")
        try:
            self.audio.set_volume(process, value / 100.0)
            self._status("")
        except AppAudioError as exc:
            self._status(str(exc), bad=True)

    def _on_mute(self, process: str, muted: bool, checkbox: QCheckBox) -> None:
        try:
            self.audio.set_mute(process, muted)
            self._status("")
        except AppAudioError as exc:
            self._status(str(exc), bad=True)
            checkbox.blockSignals(True)
            checkbox.setChecked(not muted)
            checkbox.blockSignals(False)

    def _use_for_dial(self, process: str) -> None:
        self._set_dial_target(process)

    def _set_dial_target(self, target: str) -> None:
        self._status("")
        self.settings.set("engine.dial_target", target)
        self._save()
        self._refresh_dial_label()
        self._update_dial_buttons()
        self.changed.emit()

    def _refresh_dial_label(self) -> None:
        current = str(self.settings.get("engine.dial_target", "system") or "system")
        if current == "system":
            text = "Dial controls: System volume"
        elif current == "foreground":
            text = "Dial controls: Focused app"
        else:
            text = f"Dial controls: {app_name(current)}"
        self.dial_label.setText(text)

    def _update_dial_buttons(self) -> None:
        current = str(self.settings.get("engine.dial_target", "system") or "system")
        for process, button in self._dial_buttons.items():
            active = process.lower() == current.lower()
            button.setText("On the dial" if active else "Use for dial")
            button.setProperty("variant", "accent" if active else "")
            button.style().unpolish(button)
            button.style().polish(button)

    def _status(self, text: str, bad: bool = False) -> None:
        self.status.setText(text)
        color = theme.BAD if bad else theme.TEXT_DIM
        self.status.setStyleSheet(f"font-size: 11px; color: {color};")

    def _save(self) -> None:
        try:
            self.settings.save()
        except OSError as exc:
            self._status(f"Could not save settings: {exc}", bad=True)
