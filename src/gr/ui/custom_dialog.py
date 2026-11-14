"""Teach custom hand shapes from a short recording."""

from __future__ import annotations

import time
import uuid
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QHeaderView, QInputDialog,
                               QLabel, QMessageBox, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from ..config import Settings
from ..custom import template_from
from . import theme

RECORD_SECONDS = 2.0


class CustomGesturesDialog(QDialog):
    changed = Signal()

    def __init__(self, settings: Settings,
                 descriptor_provider: Callable[[], object] | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._provider = descriptor_provider or (lambda: None)
        self._samples: list = []
        self._deadline = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._sample)

        self.setWindowTitle("Custom gestures")
        self.setModal(True)
        self.resize(640, 480)

        self._build()
        self._refresh()

    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Custom gestures")
        title.setProperty("role", "h1")
        layout.addWidget(title)

        hint = QLabel(
            "Record a hand shape you make up yourself. Shape is matched regardless of "
            "position, distance or wrist roll, then it behaves like any other gesture: "
            "bind it in the Bindings list."
        )
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Samples"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self.table, 1)

        self.status = QLabel("Hold a shape in front of the camera, then press Record.")
        self.status.setProperty("role", "sub")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.record_btn = QPushButton("Record")
        self.record_btn.setProperty("variant", "accent")
        self.record_btn.clicked.connect(self._record)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete)
        done = QPushButton("Done")
        done.clicked.connect(self.accept)
        buttons.addWidget(self.record_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addStretch(1)
        buttons.addWidget(done)
        layout.addLayout(buttons)

    # ------------------------------------------------------------------ #

    def _refresh(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.settings.custom_gestures))
        for row, gesture in enumerate(self.settings.custom_gestures):
            name = QTableWidgetItem(gesture.get("name", "gesture"))
            name.setData(Qt.UserRole, gesture.get("id"))
            self.table.setItem(row, 0, name)
            self.table.setItem(row, 1, QTableWidgetItem(str(gesture.get("samples", 0))))
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
        return self.settings.custom_gesture(item.data(Qt.UserRole))

    def _update_buttons(self) -> None:
        self.delete_btn.setEnabled(self._selected() is not None and not self._timer.isActive())

    # ------------------------------------------------------------------ #

    def _record(self) -> None:
        if self._timer.isActive():
            return
        if self._provider() is None:
            self.status.setText("No hand detected — hold a hand in view and try again.")
            return
        self._samples = []
        self._deadline = time.perf_counter() + RECORD_SECONDS
        self.record_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        self.status.setText("Recording… hold the shape steady.")
        self._timer.start()

    def _sample(self) -> None:
        self._samples.append(self._provider())
        remaining = self._deadline - time.perf_counter()
        if remaining > 0:
            self.status.setText(f"Recording… {remaining:.1f}s")
            return
        self._timer.stop()
        self.record_btn.setEnabled(True)
        self._finish()

    def _finish(self) -> None:
        template = template_from(self._samples)
        if template is None:
            usable = sum(1 for s in self._samples if s is not None)
            self.status.setText(f"Not enough hand data ({usable} frames). Try again.")
            self._update_buttons()
            return

        default = f"Gesture {len(self.settings.custom_gestures) + 1}"
        name, ok = QInputDialog.getText(self, "Name gesture", "Name:", text=default)
        if not ok or not name.strip():
            self.status.setText("Discarded.")
            self._update_buttons()
            return

        gesture = {
            "id": uuid.uuid4().hex[:10],
            "name": name.strip(),
            "template": template,
            "samples": len(self._samples),
            "created": time.strftime("%Y-%m-%d %H:%M"),
        }
        self.settings.add_custom_gesture(gesture)
        try:
            self.settings.save()
        except OSError as exc:
            self.status.setText(f"Could not save: {exc}")
            return
        self._refresh()
        self.status.setText(f"Saved «{gesture['name']}» — bind it in the gesture list.")
        self.changed.emit()

    def _delete(self) -> None:
        gesture = self._selected()
        if gesture is None:
            return
        confirm = QMessageBox.question(
            self, "Delete gesture",
            f"Delete «{gesture.get('name')}»?\nAny binding using it will be cleared.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.settings.remove_custom_gesture(gesture["id"])
        try:
            self.settings.save()
        except OSError:
            pass
        self._refresh()
        self.status.setText("Deleted.")
        self.changed.emit()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._timer.stop()
        super().closeEvent(event)
