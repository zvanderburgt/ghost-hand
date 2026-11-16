"""Gesture -> action binding editor, plus volume-dial tuning."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QInputDialog,
                               QLabel, QMessageBox, QPushButton, QScrollArea,
                               QSlider, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from ..app_audio import AppAudio, AppAudioError
from ..config import (APP_AUDIO_ACTIONS, GESTURES, Settings, available_actions,
                      available_gestures)
from . import theme
from .audio_dialog import AudioDialog
from .custom_dialog import CustomGesturesDialog
from .diagnostics_dialog import DiagnosticsDialog
from .macros_dialog import MacrosDialog
from .profiles_dialog import ProfilesDialog
from .sounds_dialog import SoundsDialog
from .tuning_dialog import TuningDialog

CATEGORY_ORDER = ["Media", "Audio", "System", "Apps", "Macros", "Sounds", "General"]
UNIMPLEMENTED: set[str] = set()


class BindingsDialog(QDialog):
    changed = Signal()

    def __init__(self, settings: Settings, parent=None,
                 descriptor_provider=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._gestures = available_gestures(settings)
        self._descriptor_provider = descriptor_provider
        self._editing_profile = "default"
        self.setWindowTitle("Bindings")
        self.setModal(True)
        self.resize(940, 680)
        self._gesture = next(iter(GESTURES))
        self._build()
        self._refresh_profiles()
        self._refresh_table()
        self._load_gesture(self._gesture)

    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        left = QVBoxLayout()
        left.setSpacing(8)
        title = QLabel("Bindings")
        title.setProperty("role", "h1")
        sub = QLabel("Pick a gesture, then choose what it should do.")
        sub.setProperty("role", "sub")
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"font-size: 11px; color: {theme.TEXT_DIM};")
        left.addWidget(title)
        left.addWidget(sub)
        left.addWidget(self.count_label)

        profile_row = QHBoxLayout()
        profile_row.setSpacing(8)
        profile_label = QLabel("Profile")
        profile_label.setProperty("role", "sub")
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        profile_row.addWidget(profile_label)
        profile_row.addWidget(self.profile_combo, 1)
        left.addLayout(profile_row)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Gesture", "Action"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._on_select)
        left.addWidget(self.table, 1)

        holder = QWidget()
        holder.setLayout(left)
        holder.setFixedWidth(392)
        root.addWidget(holder)

        right = QVBoxLayout()
        right.setSpacing(10)

        self.title = QLabel()
        self.title.setProperty("role", "h1")
        self.hint = QLabel()
        self.hint.setProperty("role", "sub")
        self.hint.setWordWrap(True)
        right.addWidget(self.title)
        right.addWidget(self.hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        right.addWidget(self.scroll, 1)

        right.addWidget(self._dial_controls())

        bottom = QHBoxLayout()
        self.clear_btn = QPushButton("Clear binding")
        self.clear_btn.clicked.connect(self._clear)
        macros_btn = QPushButton("Macros…")
        macros_btn.setToolTip("Record a macro, then bind it to this or any gesture")
        macros_btn.clicked.connect(self._open_macros)
        sounds_btn = QPushButton("Sounds…")
        sounds_btn.setToolTip("Add sound bites and route them to your mic")
        sounds_btn.clicked.connect(self._open_sounds)
        custom_btn = QPushButton("Custom…")
        custom_btn.setToolTip("Teach a new hand shape from a recording")
        custom_btn.clicked.connect(self._open_custom)
        profiles_btn = QPushButton("Profiles…")
        profiles_btn.setToolTip("Override bindings per application")
        profiles_btn.clicked.connect(self._open_profiles)
        check_btn = QPushButton("Check")
        check_btn.setToolTip("Look for conflicting or dangling bindings")
        check_btn.clicked.connect(self._open_check)
        tuning_btn = QPushButton("Tuning…")
        tuning_btn.setToolTip("Thresholds and per-gesture switches")
        tuning_btn.clicked.connect(self._open_tuning)
        done = QPushButton("Done")
        done.setProperty("variant", "accent")
        done.clicked.connect(self.accept)
        bottom.addWidget(self.clear_btn)
        bottom.addWidget(macros_btn)
        bottom.addWidget(sounds_btn)
        bottom.addWidget(custom_btn)
        bottom.addWidget(profiles_btn)
        bottom.addWidget(check_btn)
        bottom.addWidget(tuning_btn)
        bottom.addStretch(1)
        bottom.addWidget(done)
        right.addLayout(bottom)

        root.addLayout(right, 1)

    def _dial_controls(self) -> QWidget:
        box = QFrame()
        box.setObjectName("CardAlt")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        head = QHBoxLayout()
        label = QLabel("Volume dial")
        label.setProperty("role", "h2")
        mixer = QPushButton("Mixer…")
        mixer.setToolTip("Live app volumes and the dial target")
        mixer.clicked.connect(self._open_audio)
        self.dial_enabled = QCheckBox("Enable")
        self.dial_enabled.setChecked(bool(self.settings.get("engine.dial_enabled", True)))
        self.dial_enabled.toggled.connect(self._on_dial_check)
        head.addWidget(label)
        head.addWidget(mixer)
        head.addStretch(1)
        head.addWidget(self.dial_enabled)
        lay.addLayout(head)

        hint = QLabel(
            "Pinch thumb and index together like grabbing a knob, then rotate your "
            "wrist. Smaller values give finer control. Point it at one app to change "
            "that app's Windows volume instead of the system volume."
        )
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        target_row = QHBoxLayout()
        target_row.setSpacing(10)
        target_label = QLabel("Controls")
        target_label.setProperty("role", "sub")
        self.dial_target = QComboBox()
        self.dial_target.currentIndexChanged.connect(self._on_dial_target)
        target_row.addWidget(target_label)
        target_row.addWidget(self.dial_target, 1)
        lay.addLayout(target_row)

        row = QHBoxLayout()
        row.setSpacing(10)
        coarse = QLabel("Coarseness")
        coarse.setProperty("role", "sub")
        self.dial_slider = QSlider(Qt.Horizontal)
        self.dial_slider.setRange(2, 20)
        self.dial_slider.setValue(int(self.settings.get("engine.dial_degrees_per_step", 6)))
        self.dial_slider.valueChanged.connect(self._on_dial_value)
        self.dial_slider.sliderReleased.connect(self._save)
        self.dial_value = QLabel(f"{self.dial_slider.value()}° / step")
        self.dial_value.setFixedWidth(84)
        self.dial_value.setStyleSheet(
            f"font-family: {theme.MONO_FAMILY}; font-size: 11px; color: {theme.TEXT_MUTED};"
        )
        self.invert = QCheckBox("Invert")
        self.invert.setChecked(bool(self.settings.get("engine.dial_invert", False)))
        self.invert.toggled.connect(self._on_dial_check)
        row.addWidget(coarse)
        row.addWidget(self.dial_slider, 1)
        row.addWidget(self.dial_value)
        row.addWidget(self.invert)
        lay.addLayout(row)
        self._populate_dial_targets()
        return box

    # ------------------------------------------------------------------ #

    def _refresh_table(self) -> None:
        self._gestures = available_gestures(self.settings)
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._gestures))
        for row, (gid, meta) in enumerate(self._gestures.items()):
            gesture_item = QTableWidgetItem(meta["name"])
            gesture_item.setData(Qt.UserRole, gid)
            action = self.settings.binding_for(gid, self._editing_profile)
            target = self.settings.binding_target(gid, self._editing_profile)
            label = self.settings.action_label(action, target) if action else "— unbound —"
            self.table.setItem(row, 0, gesture_item)
            self.table.setItem(row, 1, QTableWidgetItem(label))
        self.table.blockSignals(False)
        bound = sum(
            1 for gid in self._gestures
            if self.settings.binding_for(gid, self._editing_profile)
        )
        scope = "this profile" if self._editing_profile != "default" else "gestures"
        self.count_label.setText(
            f"{bound} of {len(self._gestures)} {scope} bound"
            + ("" if bound else " — nothing will fire until you assign an action")
        )
        self._select_row_for(self._gesture)

    def _select_row_for(self, gesture: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == gesture:
                self.table.blockSignals(True)
                self.table.selectRow(row)
                self.table.blockSignals(False)
                return

    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return
        gesture = item.data(Qt.UserRole)
        if gesture and gesture != self._gesture:
            self._gesture = gesture
            self._load_gesture(gesture)

    def _load_gesture(self, gesture: str) -> None:
        meta = self._gestures.get(gesture) or GESTURES.get(gesture, {"name": gesture, "hint": ""})
        self.title.setText(meta["name"])
        self.hint.setText(meta.get("hint", ""))

        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        current = self.settings.binding_for(gesture, self._editing_profile)
        current_target = self.settings.binding_target(gesture, self._editing_profile)
        actions = available_actions(self.settings)
        for category in CATEGORY_ORDER:
            items = [(aid, ameta) for aid, ameta in actions.items()
                     if ameta.get("category") == category]
            if not items:
                continue
            head = QLabel(category.upper())
            head.setStyleSheet(
                f"font-size: 10px; font-weight: 600; color: {theme.TEXT_DIM}; "
                f"letter-spacing: 1px; margin-top: 4px;"
            )
            layout.addWidget(head)

            grid = QGridLayout()
            grid.setSpacing(6)
            for index, (aid, ameta) in enumerate(items):
                button = QPushButton(ameta["name"])
                button.setCheckable(True)
                chosen = current == aid
                button.setChecked(chosen)
                if chosen:
                    button.setProperty("variant", "accent")
                if aid in UNIMPLEMENTED:
                    button.setEnabled(False)
                    button.setText(f"{ameta['name']} (soon)")
                button.clicked.connect(lambda _=False, a=aid: self._choose(a))
                grid.addWidget(button, index // 2, index % 2)
            layout.addLayout(grid)

        if current in APP_AUDIO_ACTIONS:
            note = QLabel(
                f"Controlling: {current_target}" if current_target
                else "No app chosen yet — pick one of the App Volume actions above."
            )
            note.setProperty("role", "sub")
            note.setWordWrap(True)
            layout.addWidget(note)

        layout.addStretch(1)
        self.scroll.setWidget(host)

    # ------------------------------------------------------------------ #

    def _choose(self, action_id: str) -> None:
        target = None
        if action_id == "app.launch":
            path, _ = QFileDialog.getOpenFileName(
                self, "Choose an application", "",
                "Programs (*.exe *.lnk *.bat *.cmd);;All files (*.*)",
            )
            if not path:
                return
            target = path
        elif action_id in APP_AUDIO_ACTIONS:
            current = self.settings.binding_target(
                self._gesture, self._editing_profile
            ) or ""
            target = self._pick_audio_app("App volume", current)
            if target is None:
                return
        self.settings.set_binding(self._gesture, action_id, target,
                                   profile_id=self._editing_profile)
        self._save()
        self._refresh_table()
        self._load_gesture(self._gesture)
        self.changed.emit()

    def _clear(self) -> None:
        self.settings.set_binding(self._gesture, None, profile_id=self._editing_profile)
        self._save()
        self._refresh_table()
        self._load_gesture(self._gesture)
        self.changed.emit()

    def _open_macros(self) -> None:
        dialog = MacrosDialog(self.settings, self)
        dialog.exec()
        self._refresh_table()
        self._load_gesture(self._gesture)

    def _open_sounds(self) -> None:
        dialog = SoundsDialog(self.settings, self)
        dialog.exec()
        self._refresh_table()
        self._load_gesture(self._gesture)

    def _open_custom(self) -> None:
        dialog = CustomGesturesDialog(self.settings, self._descriptor_provider, self)
        dialog.exec()
        self._refresh_table()
        self._load_gesture(self._gesture)

    def _open_check(self) -> None:
        dialog = DiagnosticsDialog(self.settings, self)
        dialog.changed.connect(self._reload)
        dialog.exec()
        self._reload()

    def _open_tuning(self) -> None:
        dialog = TuningDialog(self.settings, self)
        dialog.exec()
        self._refresh_table()
        self._load_gesture(self._gesture)

    def _reload(self) -> None:
        self._refresh_table()
        self._load_gesture(self._gesture)

    # -- profiles --------------------------------------------------------- #

    def _refresh_profiles(self) -> None:
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem("Default (all apps)", "default")
        for profile in self.settings.profiles:
            rule = profile.get("match") or "no rule"
            self.profile_combo.addItem(f"{profile.get('name', 'profile')} · {rule}",
                                       profile.get("id"))
        index = max(0, self.profile_combo.findData(self._editing_profile))
        self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)

    def _on_profile_changed(self, _index: int) -> None:
        self._editing_profile = self.profile_combo.currentData() or "default"
        self._refresh_table()
        self._load_gesture(self._gesture)

    def _open_profiles(self) -> None:
        dialog = ProfilesDialog(self.settings, self)
        dialog.exec()
        self._refresh_profiles()
        self._refresh_table()
        self._load_gesture(self._gesture)

    def _open_audio(self) -> None:
        dialog = AudioDialog(self.settings, self)
        dialog.changed.connect(self._populate_dial_targets)
        dialog.exec()
        self._populate_dial_targets()

    # -- app volume ------------------------------------------------------- #

    def _pick_audio_app(self, title: str, current: str = "") -> str | None:
        try:
            apps = [app.process for app in AppAudio().apps()]
        except AppAudioError as exc:
            QMessageBox.warning(self, title, str(exc))
            return None

        items = sorted({*apps, current.strip()} - {""}, key=str.lower)
        if not items:
            items = ["spotify.exe"]
        index = next(
            (i for i, item in enumerate(items) if item.lower() == current.lower()),
            0,
        )
        choice, ok = QInputDialog.getItem(
            self, title, "App process (for example spotify.exe):",
            items, index, True,
        )
        if not ok:
            return None
        choice = choice.strip()
        return choice or None

    def _populate_dial_targets(self) -> None:
        current = str(self.settings.get("engine.dial_target", "system") or "system")
        try:
            apps = [app.process for app in AppAudio().apps()]
        except AppAudioError:
            apps = []

        running = {app.lower() for app in apps}
        if (
            current.lower() not in ("", "system", "foreground")
            and current.lower() not in running
        ):
            apps.insert(0, current)

        self.dial_target.blockSignals(True)
        self.dial_target.clear()
        self.dial_target.addItem("System volume", "system")
        self.dial_target.addItem("Focused app", "foreground")
        for app in sorted(apps, key=str.lower):
            suffix = "" if app.lower() in running else " (not running)"
            self.dial_target.addItem(f"{app}{suffix}", app)
        self.dial_target.addItem("Choose app…", "__choose__")

        index = next(
            (
                i for i in range(self.dial_target.count())
                if str(self.dial_target.itemData(i)).lower() == current.lower()
            ),
            0,
        )
        self.dial_target.setCurrentIndex(index)
        self.dial_target.blockSignals(False)

    def _on_dial_target(self, _index: int) -> None:
        value = self.dial_target.currentData()
        if value == "__choose__":
            current = str(self.settings.get("engine.dial_target", "") or "")
            target = self._pick_audio_app("Volume dial target", current)
            if target:
                self.settings.set("engine.dial_target", target)
                self._save()
            self._populate_dial_targets()
            return
        if value:
            self.settings.set("engine.dial_target", value)
            self._save()

    def _on_dial_value(self, value: int) -> None:
        self.settings.set("engine.dial_degrees_per_step", float(value))
        self.dial_value.setText(f"{value}° / step")

    def _on_dial_check(self, _checked: bool) -> None:
        self.settings.set("engine.dial_enabled", self.dial_enabled.isChecked())
        self.settings.set("engine.dial_invert", self.invert.isChecked())
        self._save()

    def _save(self) -> None:
        try:
            self.settings.save()
        except OSError:
            pass
