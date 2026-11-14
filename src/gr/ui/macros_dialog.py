"""Record, preview and delete input macros."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QInputDialog,
                               QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ..config import Settings
from ..macros import (STOP_HOTKEY, MacroPlayer, MacroRecorder, macro_duration,
                      new_macro)
from . import theme


class MacrosDialog(QDialog):
    changed = Signal()

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.recorder = MacroRecorder(self)
        self.player = MacroPlayer()

        self.setWindowTitle("Macros")
        self.setModal(True)
        self.resize(780, 520)

        self._build()
        self.recorder.changed.connect(self._on_record_count)
        self.recorder.stopped.connect(self._on_record_stopped)
        self._refresh()

    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Macros")
        title.setProperty("role", "h1")
        layout.addWidget(title)

        hint = QLabel(
            "Record a sequence of keystrokes and clicks, then bind it to a gesture in "
            "Bindings. Playback sends real input to the focused window."
        )
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Events", "Length"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.doubleClicked.connect(lambda _: self._play())
        layout.addWidget(self.table, 1)

        self.status = QLabel("Idle")
        self.status.setProperty("role", "sub")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.record_btn = QPushButton("Record")
        self.record_btn.setProperty("variant", "accent")
        self.record_btn.clicked.connect(self._record)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.recorder.stop)

        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self._play)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete)

        close_btn = QPushButton("Done")
        close_btn.clicked.connect(self.accept)

        buttons.addWidget(self.record_btn)
        buttons.addWidget(self.stop_btn)
        buttons.addWidget(self.play_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addStretch(1)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------ #

    def _refresh(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.settings.macros))
        for row, macro in enumerate(self.settings.macros):
            name = QTableWidgetItem(macro.get("name", "macro"))
            name.setData(Qt.UserRole, macro.get("id"))
            count = len(macro.get("events") or [])
            length = macro_duration(macro)
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(str(count)))
            self.table.setItem(row, 2, QTableWidgetItem(f"{length:.1f} s"))
        self.table.blockSignals(False)
        if self.table.rowCount() and not self.table.selectionModel().selectedRows():
            self.table.selectRow(0)
        self._update_buttons()

    def _selected(self) -> dict | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        return self.settings.macro(item.data(Qt.UserRole))

    def _update_buttons(self) -> None:
        has_selection = self._selected() is not None
        self.play_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    # ------------------------------------------------------------------ #

    def _record(self) -> None:
        if self.recorder.recording:
            return
        self.record_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.play_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status.setText(f"Recording… press {STOP_HOTKEY} (or Stop) to finish.")
        self.recorder.start()

    def _on_record_count(self, count: int) -> None:
        self.status.setText(f"Recording… {count} events")

    def _on_record_stopped(self) -> None:
        self.record_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        events = list(self.recorder.events)
        if not events:
            self.status.setText("Nothing recorded.")
            self._update_buttons()
            return

        default = f"Macro {len(self.settings.macros) + 1}"
        name, ok = QInputDialog.getText(self, "Save macro", "Macro name:", text=default)
        if not ok or not name.strip():
            self.status.setText(f"Discarded {len(events)} events.")
            self._update_buttons()
            return

        macro = new_macro(name, events)
        self.settings.add_macro(macro)
        try:
            self.settings.save()
        except OSError as exc:
            self.status.setText(f"Could not save: {exc}")
            return
        self._refresh()
        self.status.setText(f"Saved «{macro['name']}» — {len(events)} events.")
        self.changed.emit()

    def _play(self) -> None:
        macro = self._selected()
        if macro is None:
            return
        if not self.player.play(macro):
            self.status.setText("A macro is already playing.")
            return
        self.status.setText(f"Playing «{macro['name']}» — focus the target window.")

    def _delete(self) -> None:
        macro = self._selected()
        if macro is None:
            return
        confirm = QMessageBox.question(
            self,
            "Delete macro",
            f"Delete «{macro.get('name')}»?\nBindings pointing at it will be cleared.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.settings.remove_macro(macro["id"])
        try:
            self.settings.save()
        except OSError:
            pass
        self._refresh()
        self.status.setText("Deleted.")
        self.changed.emit()

    # ------------------------------------------------------------------ #

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self.recorder.recording:
            self.recorder.stop()
        self.player.stop()
        super().closeEvent(event)
