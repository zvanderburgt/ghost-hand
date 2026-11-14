"""Create and edit per-application binding profiles."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox,
                               QPushButton, QVBoxLayout, QWidget)

from ..config import Settings
from . import theme


class ProfilesDialog(QDialog):
    changed = Signal()

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Profiles")
        self.setModal(True)
        self.resize(720, 480)
        self._build()
        self._refresh()

    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)
        title = QLabel("Profiles")
        title.setProperty("role", "h1")
        hint = QLabel(
            "A profile overrides bindings while its app is focused. Anything it doesn't "
            "define falls back to the default bindings."
        )
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        left.addWidget(title)
        left.addWidget(hint)

        self.list = QListWidget()
        self.list.setMaximumWidth(320)
        self.list.itemSelectionChanged.connect(self._on_select)
        left.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        add_btn = QPushButton("Add profile")
        add_btn.setProperty("variant", "accent")
        add_btn.clicked.connect(self._add)
        done = QPushButton("Done")
        done.clicked.connect(self.accept)
        buttons.addWidget(add_btn)
        buttons.addStretch(1)
        buttons.addWidget(done)
        left.addLayout(buttons)

        root.addLayout(left)

        form_host = QWidget()
        form = QVBoxLayout(form_host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)

        form.addWidget(self._label("Name"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Media")
        form.addWidget(self.name_edit)

        form.addWidget(self._label("Match apps"))
        self.match_edit = QLineEdit()
        self.match_edit.setPlaceholderText("e.g. spotify.exe, vlc.exe  (comma separated, substring)")
        form.addWidget(self.match_edit)

        note = QLabel(
            "Matching is case-insensitive substring on the focused window's process name. "
            "Leave a profile selected here to edit its bindings in the Bindings window."
        )
        note.setProperty("role", "sub")
        note.setWordWrap(True)
        form.addWidget(note)
        form.addStretch(1)

        row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self._save)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete)
        row.addWidget(self.save_btn)
        row.addWidget(self.delete_btn)
        row.addStretch(1)
        form.addLayout(row)

        root.addWidget(form_host, 1)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {theme.TEXT_DIM}; letter-spacing: 1px;"
        )
        return label

    # ------------------------------------------------------------------ #

    def _refresh(self) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        item = QListWidgetItem("Default (all apps)")
        item.setData(Qt.UserRole, "default")
        self.list.addItem(item)
        for profile in self.settings.profiles:
            label = f"{profile.get('name', 'profile')}"
            text = f"{label}  ·  {profile.get('match') or 'no rule'}"
            entry = QListWidgetItem(text)
            entry.setData(Qt.UserRole, profile.get("id"))
            self.list.addItem(entry)
        self.list.blockSignals(False)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _current(self) -> dict | None:
        item = self.list.currentItem()
        if item is None:
            return None
        profile_id = item.data(Qt.UserRole)
        if profile_id == "default":
            return None
        return self.settings.profile_by_id(profile_id)

    def _on_select(self) -> None:
        item = self.list.currentItem()
        profile = self._current()
        is_default = item is None or item.data(Qt.UserRole) == "default"
        for widget in (self.name_edit, self.match_edit, self.save_btn):
            widget.setEnabled(not is_default)
        self.delete_btn.setEnabled(not is_default)
        if profile is None:
            self.name_edit.setText("Default (all apps)")
            self.match_edit.setText("always active")
        else:
            self.name_edit.setText(profile.get("name", ""))
            self.match_edit.setText(profile.get("match", ""))

    def _add(self) -> None:
        profile = self.settings.add_profile("New profile", "")
        self._save_settings()
        self._refresh()
        self._select(profile["id"])
        self.name_edit.setFocus()
        self.changed.emit()

    def _save(self) -> None:
        profile = self._current()
        if profile is None:
            return
        profile["name"] = self.name_edit.text().strip() or "Profile"
        profile["match"] = self.match_edit.text().strip()
        self._save_settings()
        current = profile.get("id")
        self._refresh()
        self._select(current)
        self.changed.emit()

    def _delete(self) -> None:
        profile = self._current()
        if profile is None:
            return
        confirm = QMessageBox.question(
            self, "Delete profile",
            f"Delete «{profile.get('name')}»? Its bindings are removed too.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        self.settings.remove_profile(profile["id"])
        self._save_settings()
        self._refresh()
        self.changed.emit()

    def _select(self, profile_id: str | None) -> None:
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.data(Qt.UserRole) == profile_id:
                self.list.setCurrentRow(row)
                return

    def _save_settings(self) -> None:
        try:
            self.settings.save()
        except OSError:
            pass
