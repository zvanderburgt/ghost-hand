"""Click-through calibration wizard: cursor corners + depth range."""

from __future__ import annotations

import time
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QProgressBar,
                               QPushButton, QVBoxLayout)

from ..calibration import distance_range, median_point, region_from_corners
from ..config import Settings
from . import theme

CORNER_STEPS = [
    ("Point at the TOP-LEFT corner of your comfortable reach", 1.2),
    ("Point at the TOP-RIGHT corner", 1.2),
    ("Point at the BOTTOM-RIGHT corner", 1.2),
    ("Point at the BOTTOM-LEFT corner", 1.2),
]
DISTANCE_STEP_SECONDS = 3.0


class CalibrationDialog(QDialog):
    """`provider` returns {'pointer': (x, y) | None, 'distance': float | None}."""

    changed = Signal()

    def __init__(self, settings: Settings,
                 provider: Callable[[], dict] | None = None, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self._provider = provider or (lambda: {})
        self._step = 0
        self._corners: list[tuple[float, float]] = []
        self._samples: list = []
        self._deadline = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._sample)

        self.setWindowTitle("Calibrate cursor")
        self.setModal(True)
        self.resize(620, 380)
        self._build()
        self._render_step()

    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("Calibrate cursor")
        title.setProperty("role", "h1")
        layout.addWidget(title)

        self.step_label = QLabel()
        self.step_label.setProperty("role", "sub")
        self.step_label.setWordWrap(True)
        layout.addWidget(self.step_label)

        self.instruction = QLabel()
        self.instruction.setWordWrap(True)
        self.instruction.setStyleSheet(
            f"font-size: 17px; font-weight: 600; color: {theme.TEXT};"
        )
        layout.addWidget(self.instruction)

        self.live = QLabel("—")
        self.live.setStyleSheet(
            f"font-family: {theme.MONO_FAMILY}; font-size: 12px; color: {theme.TEXT_MUTED};"
        )
        layout.addWidget(self.live)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        layout.addWidget(self.progress)

        layout.addStretch(1)

        self.status = QLabel()
        self.status.setProperty("role", "sub")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.capture_btn = QPushButton("Capture")
        self.capture_btn.setProperty("variant", "accent")
        self.capture_btn.clicked.connect(self._capture)
        self.skip_btn = QPushButton("Skip")
        self.skip_btn.clicked.connect(self._skip)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        row.addWidget(self.capture_btn)
        row.addWidget(self.skip_btn)
        row.addStretch(1)
        row.addWidget(cancel)
        layout.addLayout(row)

    # ------------------------------------------------------------------ #

    def _render_step(self) -> None:
        total = len(CORNER_STEPS) + 1
        self.progress.setRange(0, total)
        self.progress.setValue(self._step)
        self.step_label.setText(f"Step {min(self._step + 1, total)} of {total}")

        if self._step < len(CORNER_STEPS):
            text, _ = CORNER_STEPS[self._step]
            self.instruction.setText(text)
            self.live.setText("waiting for your fingertips…")
            self.skip_btn.setText("Skip corner")
        else:
            self.instruction.setText(
                "Move your hand slowly toward the camera, then back away"
            )
            self.live.setText("measuring distance…")
            self.skip_btn.setText("Skip distance")
        self.capture_btn.setEnabled(True)

    def _capture(self) -> None:
        if self._timer.isActive():
            return
        if self._step < len(CORNER_STEPS):
            seconds = CORNER_STEPS[self._step][1]
        else:
            seconds = DISTANCE_STEP_SECONDS
        self._samples = []
        self._deadline = time.perf_counter() + seconds
        self.capture_btn.setEnabled(False)
        self.status.setText("Hold still…" if self._step < len(CORNER_STEPS) else "Move your hand…")
        self._timer.start()

    def _sample(self) -> None:
        data = self._provider() or {}
        if self._step < len(CORNER_STEPS):
            self._samples.append(data.get("pointer"))
            point = data.get("pointer")
            if point:
                self.live.setText(f"x {point[0]:.2f}   y {point[1]:.2f}")
        else:
            self._samples.append(data.get("distance"))
            dist = data.get("distance")
            if dist:
                self.live.setText(f"{dist:.2f} m")

        remaining = self._deadline - time.perf_counter()
        if remaining > 0:
            return
        self._timer.stop()
        self.capture_btn.setEnabled(True)
        self._finish_step()

    def _finish_step(self) -> None:
        if self._step < len(CORNER_STEPS):
            point = median_point(self._samples)  # type: ignore[arg-type]
            if point is None:
                self.status.setText("No hand detected — try again.")
                return
            self._corners.append(point)
            self._step += 1
            if self._step == len(CORNER_STEPS):
                try:
                    region = region_from_corners(self._corners)
                except ValueError as exc:
                    self.status.setText(f"Corners too close ({exc}). Start again.")
                    self._corners = []
                    self._step = 0
                else:
                    self.settings.set("cursor.region_x0", region["x0"])
                    self.settings.set("cursor.region_x1", region["x1"])
                    self.settings.set("cursor.region_y0", region["y0"])
                    self.settings.set("cursor.region_y1", region["y1"])
                    self.status.setText(
                        f"Region saved: x {region['x0']:.2f}–{region['x1']:.2f}, "
                        f"y {region['y0']:.2f}–{region['y1']:.2f}"
                    )
            self._render_step()
            return

        # distance step
        try:
            low, high = distance_range(self._samples)  # type: ignore[arg-type]
        except ValueError as exc:
            self.status.setText(f"Distance not calibrated ({exc}) — skipped.")
        else:
            self.settings.set("detection.min_distance_m", low)
            self.settings.set("detection.max_distance_m", high)
            self.status.setText(f"Depth window set to {low:.2f}–{high:.2f} m")
        self._finish()

    def _skip(self) -> None:
        if self._step < len(CORNER_STEPS):
            self._step += 1
            if self._step == len(CORNER_STEPS):
                if self._corners:
                    try:
                        region = region_from_corners(self._corners)
                    except ValueError:
                        pass
                    else:
                        for key, value in (
                            ("cursor.region_x0", region["x0"]),
                            ("cursor.region_x1", region["x1"]),
                            ("cursor.region_y0", region["y0"]),
                            ("cursor.region_y1", region["y1"]),
                        ):
                            self.settings.set(key, value)
            self._render_step()
            return
        self._finish()

    def _finish(self) -> None:
        try:
            self.settings.save()
        except OSError:
            pass
        self.changed.emit()
        self.accept()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self._timer.stop()
        super().closeEvent(event)
