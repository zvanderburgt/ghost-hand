"""Soundboard library + mic routing controls."""

from __future__ import annotations

import uuid
from pathlib import Path

import soundfile as sf
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QFileDialog, QFrame,
                               QHBoxLayout, QHeaderView, QLabel, QMessageBox,
                               QPushButton, QSlider, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ..config import Settings
from ..soundboard import SoundBoard
from . import theme

AUDIO_FILTER = "Audio (*.wav *.mp3 *.ogg *.flac *.aif *.aiff *.au);;All files (*.*)"


class SoundsDialog(QDialog):
    changed = Signal()

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.board = SoundBoard(settings)

        self.setWindowTitle("Soundboard")
        self.setModal(True)
        self.resize(820, 620)

        self._build()
        self._refresh()

    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Soundboard")
        title.setProperty("role", "h1")
        layout.addWidget(title)

        hint = QLabel(
            "Add sound bites, then bind them to gestures in Bindings. With mic routing "
            "on, sounds play into the virtual cable so call apps hear them — pick "
            "\u201cCABLE Output\u201d as your microphone in Discord/Zoom."
        )
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Length", "File"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.doubleClicked.connect(lambda _: self._play())
        layout.addWidget(self.table, 1)

        layout.addWidget(self._routing_box())

        self.status = QLabel("Idle")
        self.status.setProperty("role", "sub")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        add_btn = QPushButton("Add sounds…")
        add_btn.setProperty("variant", "accent")
        add_btn.clicked.connect(self._add)
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self._play)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete)
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self.accept)

        buttons.addWidget(add_btn)
        buttons.addWidget(self.play_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addStretch(1)
        buttons.addWidget(done_btn)
        layout.addLayout(buttons)

    def _routing_box(self) -> QFrame:
        box = QFrame()
        box.setObjectName("CardAlt")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        head = QLabel("Routing")
        head.setProperty("role", "h2")
        lay.addWidget(head)

        self.mic_check = QCheckBox("Play into the mic (virtual cable)")
        self.mic_check.setChecked(bool(self.settings.get("soundboard.mic_route", True)))
        self.mic_check.toggled.connect(self._on_routing)
        lay.addWidget(self.mic_check)

        self.monitor_check = QCheckBox("Also hear it on my speakers")
        self.monitor_check.setChecked(bool(self.settings.get("soundboard.monitor", True)))
        self.monitor_check.toggled.connect(self._on_routing)
        lay.addWidget(self.monitor_check)

        volume_row = QHBoxLayout()
        volume_row.setSpacing(10)
        label = QLabel("Volume")
        label.setProperty("role", "sub")
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(float(self.settings.get("soundboard.volume", 0.8)) * 100))
        self.volume.valueChanged.connect(self._on_volume)
        self.volume.sliderReleased.connect(self._save)
        self.volume_value = QLabel(f"{self.volume.value()}%")
        self.volume_value.setFixedWidth(44)
        self.volume_value.setStyleSheet(
            f"font-family: {theme.MONO_FAMILY}; font-size: 11px; color: {theme.TEXT_MUTED};"
        )
        volume_row.addWidget(label)
        volume_row.addWidget(self.volume, 1)
        volume_row.addWidget(self.volume_value)
        lay.addLayout(volume_row)

        self.cable_label = QLabel()
        self.cable_label.setProperty("role", "sub")
        lay.addWidget(self.cable_label)
        return box

    # ------------------------------------------------------------------ #

    def _refresh(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.settings.sounds))
        for row, sound in enumerate(self.settings.sounds):
            name = QTableWidgetItem(sound.get("name", "sound"))
            name.setData(Qt.UserRole, sound.get("id"))
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(f"{sound.get('duration', 0.0):.1f} s"))
            self.table.setItem(row, 2, QTableWidgetItem(Path(sound.get("path", "")).name))
        self.table.blockSignals(False)

        if self.table.rowCount() and not self.table.selectionModel().selectedRows():
            self.table.selectRow(0)
        self._update_buttons()
        self._refresh_cable_label()

    def _refresh_cable_label(self) -> None:
        cable = self.board.cable_device()
        if cable is None:
            self.cable_label.setText(
                "Virtual mic: no \u201cCABLE Input\u201d device found — install VB-Audio Cable "
                "or set soundboard.cable_device in settings.json"
            )
            self.cable_label.setStyleSheet(f"font-size: 11px; color: {theme.BAD};")
        else:
            self.cable_label.setText(
                "Virtual mic: CABLE Input detected — select \u201cCABLE Output\u201d as your mic in the call app"
            )
            self.cable_label.setStyleSheet(f"font-size: 11px; color: {theme.GOOD};")

    def _selected(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        return self.settings.sound(item.data(Qt.UserRole))

    def _update_buttons(self) -> None:
        has = self._selected() is not None
        self.play_btn.setEnabled(has)
        self.delete_btn.setEnabled(has)

    # ------------------------------------------------------------------ #

    def _add(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add sounds", "", AUDIO_FILTER)
        if not paths:
            return
        added = 0
        for path in paths:
            try:
                info = sf.info(path)
                duration = float(info.duration)
                rate = int(info.samplerate)
            except Exception:  # noqa: BLE001 - unsupported file
                self.status.setText(f"Skipped {Path(path).name}: unsupported audio")
                continue
            self.settings.add_sound({
                "id": uuid.uuid4().hex[:10],
                "name": Path(path).stem,
                "path": path,
                "volume": 1.0,
                "duration": round(duration, 2),
                "samplerate": rate,
            })
            added += 1
        if added:
            self._save()
            self._refresh()
            self.status.setText(f"Added {added} sound(s).")
            self.changed.emit()

    def _play(self) -> None:
        sound = self._selected()
        if sound is None:
            return
        ok = self.board.play(sound)
        if ok:
            targets = self.board.targets()
            where = "mic + speakers" if len(targets) > 1 else (
                "mic only" if targets and targets[0] is not None else "speakers"
            )
            self.status.setText(f"Playing «{sound.get('name')}» to {where}")
        else:
            self.status.setText("Could not play — check the routing settings.")

    def _delete(self) -> None:
        sound = self._selected()
        if sound is None:
            return
        confirm = QMessageBox.question(
            self, "Delete sound",
            f"Remove «{sound.get('name')}»?\nBindings pointing at it will be cleared.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.settings.remove_sound(sound["id"])
        self._save()
        self._refresh()
        self.status.setText("Deleted.")
        self.changed.emit()

    # ------------------------------------------------------------------ #

    def _on_routing(self, _checked: bool) -> None:
        self.settings.set("soundboard.mic_route", self.mic_check.isChecked())
        self.settings.set("soundboard.monitor", self.monitor_check.isChecked())
        self._save()

    def _on_volume(self, value: int) -> None:
        self.settings.set("soundboard.volume", round(value / 100.0, 2))
        self.volume_value.setText(f"{value}%")

    def _save(self) -> None:
        try:
            self.settings.save()
        except OSError:
            pass

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.board.close()
        super().closeEvent(event)
