"""Binding conflict report."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ..config import Settings
from ..diagnostics import ERROR, INFO, WARNING, fix_duplicates, run_all
from . import theme

LEVEL_COLOR = {ERROR: theme.BAD, WARNING: theme.WARN, INFO: theme.TEXT_MUTED}
LEVEL_LABEL = {ERROR: "Error", WARNING: "Warning", INFO: "Note"}


class DiagnosticsDialog(QDialog):
    changed = Signal()

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Binding check")
        self.setModal(True)
        self.resize(720, 480)
        self._build()
        self._refresh()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Binding check")
        title.setProperty("role", "h1")
        layout.addWidget(title)

        hint = QLabel(
            "Looks for settings that would behave unexpectedly: one gesture wired to two "
            "actions, the same action on several gestures, deleted macros or sounds, and "
            "learned gestures that are too similar to tell apart."
        )
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.host = QWidget()
        self.rows = QVBoxLayout(self.host)
        self.rows.setContentsMargins(0, 0, 8, 0)
        self.rows.setSpacing(8)
        self.scroll.setWidget(self.host)
        layout.addWidget(self.scroll, 1)

        self.summary = QLabel()
        self.summary.setProperty("role", "sub")
        layout.addWidget(self.summary)

        bottom = QHBoxLayout()
        self.fix_btn = QPushButton("Remove duplicate bindings")
        self.fix_btn.clicked.connect(self._fix)
        done = QPushButton("Close")
        done.setProperty("variant", "accent")
        done.clicked.connect(self.accept)
        bottom.addWidget(self.fix_btn)
        bottom.addStretch(1)
        bottom.addWidget(done)
        layout.addLayout(bottom)

    # ------------------------------------------------------------------ #

    def _refresh(self) -> None:
        while self.rows.count():
            item = self.rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        issues = run_all(self.settings)
        if not issues:
            label = QLabel("No conflicts found — every binding is unambiguous.")
            label.setStyleSheet(f"font-size: 13px; color: {theme.GOOD};")
            self.rows.addWidget(label)
        else:
            for issue in issues:
                self.rows.addWidget(self._row(issue.level, issue.message))
        self.rows.addStretch(1)

        duplicates = any("different actions" in issue.message for issue in issues)
        self.fix_btn.setEnabled(duplicates)
        errors = sum(1 for issue in issues if issue.level == ERROR)
        warnings = sum(1 for issue in issues if issue.level == WARNING)
        self.summary.setText(
            f"{len(issues)} finding(s): {errors} error(s), {warnings} warning(s)"
            if issues else "Nothing to fix."
        )

    @staticmethod
    def _row(level: str, message: str) -> QWidget:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        badge = QLabel(LEVEL_LABEL.get(level, level.title()))
        badge.setFixedWidth(64)
        badge.setAlignment(badge.alignment() | 0x0004)  # centre
        badge.setStyleSheet(
            f"color: {LEVEL_COLOR.get(level, theme.TEXT_MUTED)}; font-size: 10px; "
            f"font-weight: 600; letter-spacing: 1px;"
        )
        text = QLabel(message)
        text.setWordWrap(True)
        text.setStyleSheet(f"font-size: 12px; color: {theme.TEXT};")
        layout.addWidget(badge)
        layout.addWidget(text, 1)
        return host

    def _fix(self) -> None:
        removed = fix_duplicates(self.settings)
        try:
            self.settings.save()
        except OSError:
            pass
        self._refresh()
        if removed:
            self.summary.setText(f"Removed {removed} duplicate binding(s).")
            self.changed.emit()
