"""System tray integration."""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .. import autostart
from ..config import APP_NAME
from .icon import app_icon
from .main_window import MainWindow


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window: MainWindow) -> None:
        super().__init__(app_icon(), window)
        self.window = window
        self.setToolTip(f"{APP_NAME} · practice mode")

        menu = QMenu()

        open_action = QAction("Open window", menu)
        open_action.triggered.connect(self.show_window)
        menu.addAction(open_action)

        guide_action = QAction("How it works…", menu)
        guide_action.triggered.connect(self.window.show_guide)
        menu.addAction(guide_action)

        menu.addSeparator()

        self.practice_action = QAction("Practice mode (no keys sent)", menu)
        self.practice_action.setCheckable(True)
        self.practice_action.setChecked(window.practice_on)
        self.practice_action.toggled.connect(self._on_practice)
        menu.addAction(self.practice_action)

        arm_action = QAction("Arm / disarm", menu)
        arm_action.triggered.connect(self.window.toggle_arm)
        menu.addAction(arm_action)

        menu.addSeparator()

        record_action = QAction("Save debug clip", menu)
        record_action.triggered.connect(self.window._on_record)
        menu.addAction(record_action)

        reconnect_action = QAction("Reconnect camera", menu)
        reconnect_action.triggered.connect(self.window.restart_capture)
        menu.addAction(reconnect_action)

        self.autostart_action = QAction("Start with Windows", menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart.is_enabled())
        self.autostart_action.toggled.connect(self._on_autostart)
        menu.addAction(self.autostart_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.window.quit_app)
        menu.addAction(quit_action)

        self._menu = menu
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        self.window.practice_switch.toggled.connect(self._sync_practice)
        self.show()

    # ------------------------------------------------------------------ #

    def show_window(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.window.isVisible():
                self.window.hide()
            else:
                self.show_window()

    def _on_practice(self, on: bool) -> None:
        self.window.set_practice(on)
        self.setToolTip(f"{APP_NAME} · {'practice mode' if on else 'live mode'}")

    def _sync_practice(self, on: bool) -> None:
        self.practice_action.blockSignals(True)
        self.practice_action.setChecked(on)
        self.practice_action.blockSignals(False)
        self.setToolTip(f"{APP_NAME} · {'practice mode' if on else 'live mode'}")

    def _on_autostart(self, on: bool) -> None:
        ok = autostart.set_enabled(on)
        if not ok:
            self.window.log.add_line("Could not update the Windows autostart entry")
