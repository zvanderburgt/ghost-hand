"""Tuning panel: thresholds and per-gesture switches, applied live."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QGridLayout, QHBoxLayout,
                               QLabel, QPushButton, QScrollArea, QSlider,
                               QVBoxLayout, QWidget)

from ..config import DEFAULT_SETTINGS, Settings, available_gestures
from . import theme


class TuningDialog(QDialog):
    changed = Signal()

    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._sliders: list[tuple[QSlider, str, float, callable]] = []
        self.setWindowTitle("Tuning")
        self.setModal(True)
        self.resize(720, 640)
        self._build()
        self._rebuild()

    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)

        title = QLabel("Tuning")
        title.setProperty("role", "h1")
        root.addWidget(title)

        hint = QLabel(
            "Detection thresholds and per-gesture switches. Changes apply immediately; "
            "values are saved when you let go of a slider."
        )
        hint.setProperty("role", "sub")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        root.addWidget(self.scroll, 1)

        bottom = QHBoxLayout()
        reset_btn = QPushButton("Restore defaults")
        reset_btn.clicked.connect(self._reset)
        done = QPushButton("Done")
        done.setProperty("variant", "accent")
        done.clicked.connect(self.accept)
        bottom.addWidget(reset_btn)
        bottom.addStretch(1)
        bottom.addWidget(done)
        root.addLayout(bottom)

    # ------------------------------------------------------------------ #

    def _rebuild(self) -> None:
        self._sliders = []
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(8)

        self._section(layout, "Detection")
        self._slider(layout, "Pose confidence", "engine.pose_threshold",
                     30, 95, 1, 0.01, lambda v: f"{v:.2f}")
        self._slider(layout, "Stability frames", "engine.stability_frames",
                     3, 10, 1, 1, lambda v: f"{int(v)}")
        self._slider(layout, "Hold to fire", "engine.fire_hold_ms",
                     200, 1200, 50, 1, lambda v: f"{int(v)} ms")
        self._slider(layout, "Action cooldown", "engine.cooldown_ms",
                     200, 1500, 50, 1, lambda v: f"{int(v)} ms")
        self._slider(layout, "Auto-disarm", "engine.auto_disarm_ms",
                     2000, 15000, 500, 1, lambda v: f"{int(v) / 1000:.1f} s")

        self._section(layout, "Depth")
        self._slider(layout, "Nearest hand", "detection.min_distance_m",
                     10, 150, 1, 0.01, lambda v: f"{v:.2f} m")
        self._slider(layout, "Furthest hand", "detection.max_distance_m",
                     50, 300, 1, 0.01, lambda v: f"{v:.2f} m")

        self._section(layout, "Swipes")
        enabled = QCheckBox("Enable swipe gestures")
        enabled.setChecked(bool(self.settings.get("engine.swipe_enabled", True)))
        enabled.toggled.connect(self._on_swipe_enabled)
        layout.addWidget(enabled)
        self._slider(layout, "Minimum travel", "engine.swipe_min_distance",
                     5, 30, 1, 0.1, lambda v: f"{v:.1f} hands")
        self._slider(layout, "Swipe cooldown", "engine.swipe_cooldown_ms",
                     200, 1500, 50, 1, lambda v: f"{int(v)} ms")

        self._section(layout, "Gestures")
        arm_pose = self.settings.get("engine.arm_pose", "rock")
        note = QLabel(
            f"Off gestures are ignored completely — they cannot fire or form a chord. "
            f"«{self.settings.gesture_label(arm_pose)}» is the arming pose, so it stays on."
        )
        note.setProperty("role", "sub")
        note.setWordWrap(True)
        layout.addWidget(note)

        grid = QGridLayout()
        grid.setSpacing(6)
        gestures = available_gestures(self.settings)
        for index, (gesture_id, meta) in enumerate(gestures.items()):
            box = QCheckBox(meta.get("name", gesture_id))
            box.setChecked(self.settings.is_gesture_enabled(gesture_id))
            if gesture_id == arm_pose:
                box.setEnabled(False)
                box.setToolTip("This is the arming pose")
            box.toggled.connect(
                lambda state, gid=gesture_id: self._on_gesture(gid, state)
            )
            grid.addWidget(box, index // 2, index % 2)
        layout.addLayout(grid)

        layout.addStretch(1)
        self.scroll.setWidget(host)

    def _section(self, layout: QVBoxLayout, title: str) -> None:
        label = QLabel(title.upper())
        label.setStyleSheet(
            f"font-size: 10px; font-weight: 600; color: {theme.TEXT_DIM}; "
            f"letter-spacing: 1px; margin-top: 10px;"
        )
        layout.addWidget(label)

    def _slider(self, layout: QVBoxLayout, label: str, key: str,
                lo: int, hi: int, step: int, scale: float, fmt) -> None:
        row = QHBoxLayout()
        row.setSpacing(10)

        name = QLabel(label)
        name.setFixedWidth(150)
        name.setProperty("role", "sub")

        slider = QSlider(Qt.Horizontal)
        slider.setRange(lo, hi)
        slider.setSingleStep(step)
        slider.setPageStep(step * 4)

        current = float(self.settings.get(key, DEFAULT_SETTINGS.get(key.split('.')[0], {}).get(key.split('.')[1], lo)))
        slider.setValue(int(round(current / scale)))

        value = QLabel(fmt(current))
        value.setFixedWidth(86)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        value.setStyleSheet(
            f"font-family: {theme.MONO_FAMILY}; font-size: 11px; color: {theme.TEXT_MUTED};"
        )

        def on_change(raw: int) -> None:
            number = raw * scale
            self.settings.set(key, round(number, 3) if scale < 1 else int(number))
            value.setText(fmt(number))
            self.changed.emit()

        slider.valueChanged.connect(on_change)
        slider.sliderReleased.connect(self._save)
        self._sliders.append((slider, key, scale, fmt))

        row.addWidget(name)
        row.addWidget(slider, 1)
        row.addWidget(value)
        layout.addLayout(row)

    # ------------------------------------------------------------------ #

    def _on_swipe_enabled(self, on: bool) -> None:
        self.settings.set("engine.swipe_enabled", on)
        self._save()

    def _on_gesture(self, gesture_id: str, enabled: bool) -> None:
        self.settings.set_gesture_enabled(gesture_id, enabled)
        self._save()
        self.changed.emit()

    def _reset(self) -> None:
        for key, value in (
            ("engine.pose_threshold", 0.55),
            ("engine.stability_frames", 5),
            ("engine.fire_hold_ms", 400),
            ("engine.cooldown_ms", 450),
            ("engine.auto_disarm_ms", 6000),
            ("detection.min_distance_m", 0.2),
            ("detection.max_distance_m", 2.0),
            ("engine.swipe_enabled", True),
            ("engine.swipe_min_distance", 1.3),
            ("engine.swipe_cooldown_ms", 600),
        ):
            self.settings.set(key, value)
        self.settings.data["disabled_gestures"] = []
        self._save()
        self._rebuild()
        self.changed.emit()

    def _save(self) -> None:
        try:
            self.settings.save()
        except OSError:
            pass
