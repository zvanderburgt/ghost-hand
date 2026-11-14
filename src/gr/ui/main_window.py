"""Main window: live preview, gesture readout, scores, session metrics, log."""

from __future__ import annotations

import threading

import cv2
import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QMainWindow, QProgressBar,
                               QPushButton, QSlider, QVBoxLayout, QWidget)

from ..config import GESTURES, APP_NAME, Settings
from ..diagnostics import run_all
from ..pipeline import StepResult, VisionPipeline
from . import theme
from .bindings_dialog import BindingsDialog
from .calibration_dialog import CalibrationDialog
from .diagnostics_dialog import DiagnosticsDialog
from .guide_dialog import GuideDialog
from .icon import app_icon
from .macros_dialog import MacrosDialog
from .sounds_dialog import SoundsDialog
from .widgets import (Card, EventLog, FlashLabel, MetricRow, ScoreBoard,
                      Segmented, StatusPill, Switch, VideoView)


def to_qimage(bgr: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


class CaptureWorker(QThread):
    frameReady = Signal(QImage)
    depthReady = Signal(QImage)
    stateReady = Signal(object)
    eventsReady = Signal(list)
    failed = Signal(str)
    opened = Signal()

    def __init__(self, settings: Settings, demo: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.demo = demo
        self._stop = threading.Event()
        self._want_depth = False
        self._clip_request = False
        self.pipeline: VisionPipeline | None = None

    def set_depth(self, on: bool) -> None:
        self._want_depth = on

    def request_clip(self) -> None:
        self._clip_request = True

    def run(self) -> None:  # noqa: D102 - QThread entry point
        pipeline = VisionPipeline(self.settings, demo=self.demo)
        self.pipeline = pipeline
        try:
            pipeline.open()
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI
            self.failed.emit(str(exc))
            return

        self.opened.emit()
        if pipeline.events:
            self.eventsReady.emit(list(pipeline.events))
        while not self._stop.is_set():
            try:
                result = pipeline.step()
            except Exception as exc:  # noqa: BLE001
                self.failed.emit(f"{type(exc).__name__}: {exc}")
                break
            if result is None:
                self.msleep(6)
                continue

            self.frameReady.emit(to_qimage(result.display))
            if self._want_depth and result.depth_view is not None:
                self.depthReady.emit(to_qimage(result.depth_view))
            self.stateReady.emit(result)
            if result.events:
                self.eventsReady.emit(result.events)

            if self._clip_request:
                self._clip_request = False
                message = pipeline.save_clip()
                self.eventsReady.emit([message])

            self.msleep(1)

        pipeline.close()

    def stop(self) -> None:
        self._stop.set()
        self.wait(3000)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, demo: bool = False) -> None:
        super().__init__()
        self.settings = settings
        self.demo = demo
        self.worker: CaptureWorker | None = None
        self._camera_ok = False
        self._quitting = False
        self.tray = None

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1260, 840)
        self.setMinimumSize(1020, 700)

        self._build()
        self._report_issues()
        self._start_worker()

    def _report_issues(self) -> None:
        issues = run_all(self.settings)
        if not issues:
            return
        self.log.add_line(
            f"Settings check: {len(issues)} finding(s) — see Bindings → Check"
        )
        for issue in issues[:4]:
            self.log.add_line(f"  {issue.level.upper()}: {issue.message}")

    def show_guide(self) -> None:
        dialog = GuideDialog(self.settings, self)
        dialog.exec()

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 16, 18, 12)
        outer.setSpacing(14)

        outer.addLayout(self._build_header())
        outer.addLayout(self._build_body(), 1)
        outer.addLayout(self._build_footer())

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        icon = QLabel()
        icon.setPixmap(app_icon().pixmap(36, 36))
        icon.setFixedSize(36, 36)
        row.addWidget(icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title = QLabel(APP_NAME)
        title.setProperty("role", "h1")
        camera = self.settings.get("camera.color_width"), self.settings.get("camera.color_height")
        subtitle = QLabel(f"Intel RealSense · {camera[0]}×{camera[1]} · depth aligned")
        subtitle.setProperty("role", "sub")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        row.addLayout(title_col)

        row.addStretch(1)

        self.pill = StatusPill()
        row.addWidget(self.pill, 0, Qt.AlignVCenter)

        practice_label = QLabel("Practice")
        practice_label.setProperty("role", "sub")
        row.addSpacing(6)
        row.addWidget(practice_label, 0, Qt.AlignVCenter)

        self.practice_switch = Switch(bool(self.settings.get("safety.practice_mode", True)))
        self.practice_switch.setToolTip(
            "Practice mode logs gestures without sending any keyboard input"
        )
        self.practice_switch.toggled.connect(self._on_practice_toggled)
        row.addWidget(self.practice_switch, 0, Qt.AlignVCenter)

        self.cursor_btn = QPushButton("Cursor")
        self.cursor_btn.setCheckable(True)
        self.cursor_btn.setChecked(bool(self.settings.get("cursor.enabled", False)))
        self.cursor_btn.setToolTip(
            "Point with your index finger to move the Windows pointer; pinch to click"
        )
        self.cursor_btn.toggled.connect(self._on_cursor_toggled)
        row.addWidget(self.cursor_btn)

        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.setProperty("variant", "ghost")
        self.calibrate_btn.setToolTip(
            "Walk through pointing at the four corners to set your cursor region"
        )
        self.calibrate_btn.clicked.connect(self._open_calibration)
        self.calibrate_btn.setVisible(self.cursor_btn.isChecked())
        row.addWidget(self.calibrate_btn)

        self.record_btn = QPushButton("Record clip")
        self.record_btn.setToolTip("Save the last 1.5 s of video plus recent events to debug/")
        self.record_btn.clicked.connect(self._on_record)
        row.addWidget(self.record_btn)

        self.retry_btn = QPushButton("Reconnect camera")
        self.retry_btn.setProperty("variant", "accent")
        self.retry_btn.clicked.connect(self.restart_capture)
        self.retry_btn.hide()
        row.addWidget(self.retry_btn)

        self.sounds_btn = QPushButton("Sounds")
        self.sounds_btn.setToolTip("Soundboard: add sound bites and route them to your mic")
        self.sounds_btn.clicked.connect(self._open_sounds)
        row.addWidget(self.sounds_btn)

        settings_btn = self.bindings_btn = QPushButton("Bindings")
        self.bindings_btn.setToolTip("Choose what each gesture does")
        self.bindings_btn.clicked.connect(self._open_bindings)
        row.addWidget(self.bindings_btn)

        self.macros_btn = QPushButton("Macros")
        self.macros_btn.setToolTip("Record and manage input macros")
        self.macros_btn.clicked.connect(self._open_macros)
        row.addWidget(self.macros_btn)

        help_btn = QPushButton("?")
        help_btn.setProperty("variant", "ghost")
        help_btn.setFixedWidth(30)
        help_btn.setToolTip("How Ghost Hand works")
        help_btn.clicked.connect(self.show_guide)
        row.addWidget(help_btn)

        return row

    def _build_body(self) -> QHBoxLayout:
        body = QHBoxLayout()
        body.setSpacing(14)

        left = QVBoxLayout()
        left.setSpacing(14)
        left.addWidget(self._build_video_card(), 1)
        left.addWidget(self._build_gesture_card())
        body.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(self._build_scores_card())
        right.addWidget(self._build_session_card())
        right.addWidget(self._build_log_card(), 1)

        right_holder = QWidget()
        right_holder.setLayout(right)
        right_holder.setFixedWidth(372)
        body.addWidget(right_holder)
        return body

    def _build_video_card(self) -> Card:
        card = self.video_card = Card()
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel("Camera")
        title.setProperty("role", "h2")
        head.addWidget(title)
        head.addStretch(1)

        self.video_tabs = Segmented(["Camera", "Depth"])
        self.video_tabs.changed.connect(self._on_tab)
        head.addWidget(self.video_tabs)
        card.body.addLayout(head)

        self.video = VideoView()
        self.video.setMinimumHeight(360)
        card.body.addWidget(self.video, 1)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.chip_fps = self._chip("0 fps")
        self.chip_latency = self._chip("0.0 ms")
        self.chip_res = self._chip(
            f"{self.settings.get('camera.color_width')}×{self.settings.get('camera.color_height')}"
        )
        chips.addWidget(self.chip_fps)
        chips.addWidget(self.chip_latency)
        chips.addWidget(self.chip_res)
        chips.addStretch(1)
        card.body.addLayout(chips)
        return card

    @staticmethod
    def _chip(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"background: #232326; border-radius: 5px; padding: 3px 8px;"
            f"color: {theme.TEXT_MUTED}; font-family: {theme.MONO_FAMILY}; font-size: 10px;"
        )
        return lbl

    def _build_gesture_card(self) -> Card:
        card = Card()
        card.body.setContentsMargins(16, 12, 16, 12)

        row = QHBoxLayout()
        row.setSpacing(12)

        col = QVBoxLayout()
        col.setSpacing(2)
        self.gesture_name = QLabel("No gesture")
        self.gesture_name.setProperty("role", "big")
        self.gesture_name.setMinimumWidth(220)
        self.gesture_action = QLabel(self._arm_hint())
        self.gesture_action.setProperty("role", "sub")
        col.addWidget(self.gesture_name)
        col.addWidget(self.gesture_action)
        row.addLayout(col)
        row.addStretch(1)

        self.flash = FlashLabel()
        row.addWidget(self.flash, 0, Qt.AlignVCenter)

        card.body.addLayout(row)

        self.hold_bar = QProgressBar()
        self.hold_bar.setTextVisible(False)
        self.hold_bar.setFixedHeight(4)
        self.hold_bar.setStyleSheet(
            f"QProgressBar {{ background: #34343A; border: none; border-radius: 2px; }}"
            f"QProgressBar::chunk {{ background: {theme.ACCENT}; border-radius: 2px; }}"
        )
        card.body.addWidget(self.hold_bar)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        hold_label = QLabel("Hold to fire")
        hold_label.setProperty("role", "sub")
        controls.addWidget(hold_label, 0, Qt.AlignVCenter)

        self.hold_slider = QSlider(Qt.Horizontal)
        self.hold_slider.setRange(200, 1200)
        self.hold_slider.setSingleStep(50)
        self.hold_slider.setPageStep(100)
        self.hold_slider.setValue(int(self.settings.get("engine.fire_hold_ms", 400)))
        self.hold_slider.setFixedWidth(260)
        self.hold_slider.setToolTip(
            "How long a gesture must be held before it fires. Applies immediately."
        )
        self.hold_slider.valueChanged.connect(self._on_hold_changed)
        self.hold_slider.sliderReleased.connect(self._save_tuning)
        controls.addWidget(self.hold_slider, 0, Qt.AlignVCenter)

        self.hold_value = QLabel(f"{self.hold_slider.value()} ms")
        self.hold_value.setFixedWidth(58)
        self.hold_value.setStyleSheet(
            f"font-family: {theme.MONO_FAMILY}; font-size: 11px; color: {theme.TEXT_MUTED};"
        )
        controls.addWidget(self.hold_value, 0, Qt.AlignVCenter)
        controls.addStretch(1)
        card.body.addLayout(controls)
        return card

    def _on_hold_changed(self, value: int) -> None:
        self.settings.set("engine.fire_hold_ms", int(value))
        self.hold_value.setText(f"{value} ms")

    def _save_tuning(self) -> None:
        try:
            self.settings.save()
        except OSError as exc:
            self.log.add_line(f"Could not save settings: {exc}")

    def _build_scores_card(self) -> Card:
        card = Card("Live scores")
        self.scores = ScoreBoard()
        self.scores.ensure_rows({k: v["name"] for k, v in GESTURES.items()})
        card.add(self.scores)
        return card

    def _build_session_card(self) -> Card:
        card = Card("Session")
        self.m_hands = MetricRow("Hands")
        self.m_distance = MetricRow("Hand distance")
        self.m_state = MetricRow("State")
        self.m_thumb = MetricRow("Thumb")
        self.m_dial = MetricRow("Dial")
        self.m_cursor = MetricRow("Cursor")
        for widget in (self.m_hands, self.m_distance, self.m_state, self.m_thumb,
                       self.m_dial, self.m_cursor):
            card.add(widget)
        return card

    def _build_log_card(self) -> Card:
        card = Card("Event log")
        self.log = EventLog()
        card.add(self.log)
        return card

    def _build_footer(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        self.footer_left = QLabel("Starting camera…")
        self.footer_left.setProperty("role", "sub")
        self.footer_right = QLabel()
        self.footer_right.setProperty("role", "sub")
        row.addWidget(self.footer_left)
        row.addStretch(1)
        row.addWidget(self.footer_right)
        self._refresh_footer()
        return row

    # ------------------------------------------------------------------ #
    # Worker lifecycle
    # ------------------------------------------------------------------ #

    def _start_worker(self) -> None:
        self.worker = CaptureWorker(self.settings, demo=self.demo)
        self.worker.frameReady.connect(self.video.set_image)
        self.worker.depthReady.connect(self.video.set_image)
        self.worker.stateReady.connect(self._on_state)
        self.worker.eventsReady.connect(self._on_events)
        self.worker.failed.connect(self._on_failed)
        self.worker.opened.connect(self._on_opened)
        self.worker.set_depth(self.video_tabs.index == 1)
        self.worker.start()

    def restart_capture(self) -> None:
        self.retry_btn.hide()
        self._camera_ok = False
        self.video.show_message("Reconnecting…", "")
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self._start_worker()

    def stop_capture(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.worker = None

    # ------------------------------------------------------------------ #
    # Slots
    # ------------------------------------------------------------------ #

    def _on_opened(self) -> None:
        self._camera_ok = True
        self.retry_btn.hide()
        self.pill.set_state("demo" if self.demo else "disarmed")
        self.footer_left.setText(
            "Demo source · synthetic hands" if self.demo else "RealSense D435 streaming"
        )

    def _on_failed(self, message: str) -> None:
        self._camera_ok = False
        self.pill.set_state("error")
        self.video.show_message("Camera unavailable", message)
        self.retry_btn.show()
        self.log.add_line(f"Camera error: {message}")
        self.footer_left.setText("Camera unavailable")

    def _on_tab(self, index: int) -> None:
        if self.worker is not None:
            self.worker.set_depth(index == 1)
        if index == 1 and self._camera_ok:
            self.video.show_message("Waiting for depth frames…", "")

    def _on_record(self) -> None:
        if self.worker is not None:
            self.worker.request_clip()
        self.flash.flash("Saving clip…", 900)

    def _open_bindings(self) -> None:
        changed = {"any": False}
        dialog = BindingsDialog(self.settings, self, self._live_descriptor)
        dialog.changed.connect(lambda: changed.__setitem__("any", True))
        dialog.exec()
        if changed["any"]:
            self.log.add_line("Bindings updated")

    def _live_descriptor(self):
        worker = self.worker
        pipeline = getattr(worker, "pipeline", None) if worker is not None else None
        return getattr(pipeline, "latest_descriptor", None) if pipeline is not None else None

    def _open_macros(self) -> None:
        dialog = MacrosDialog(self.settings, self)
        dialog.changed.connect(lambda: self.log.add_line("Macros updated"))
        dialog.exec()

    def _open_sounds(self) -> None:
        dialog = SoundsDialog(self.settings, self)
        dialog.changed.connect(lambda: self.log.add_line("Soundboard updated"))
        dialog.exec()

    def _on_cursor_toggled(self, on: bool) -> None:
        self.settings.set("cursor.enabled", on)
        self._save_tuning()
        self.calibrate_btn.setVisible(on)
        self.log.add_line(
            "Cursor mode ON - point with your index finger, pinch to click"
            if on
            else "Cursor mode OFF"
        )

    def _open_calibration(self) -> None:
        worker = self.worker
        pipeline = getattr(worker, "pipeline", None) if worker is not None else None
        if pipeline is None:
            self.log.add_line("Calibration needs the camera to be running")
            return

        def provider() -> dict:
            return {
                "pointer": getattr(pipeline, "latest_pointer", None),
                "distance": getattr(pipeline, "latest_distance", None),
            }

        dialog = CalibrationDialog(self.settings, provider, self)
        dialog.changed.connect(lambda: self.log.add_line("Cursor region calibrated"))
        dialog.exec()

    def _on_practice_toggled(self, on: bool) -> None:
        self.settings.set("safety.practice_mode", on)
        try:
            self.settings.save()
        except OSError as exc:
            self.log.add_line(f"Could not save settings: {exc}")
        self._refresh_footer()
        self.log.add_line(
            "Practice mode ON - nothing is sent to Windows"
            if on
            else "Live mode - gestures now send real key presses"
        )

    def _on_events(self, lines: list[str]) -> None:
        for line in lines:
            self.log.add_line(line)

    def _on_state(self, result: StepResult) -> None:
        state = result.state
        if self._camera_ok:
            if self.demo:
                self.pill.set_state("demo")
            elif state.armed:
                self.pill.set_state("armed")
            elif state.arm_progress > 0.0:
                self.pill.set_state("arming")
            else:
                self.pill.set_state("disarmed")

        # Armed state gets a visible cue on the preview card itself.
        armed = bool(state.armed)
        if bool(self.video_card.property("armed")) != armed:
            self.video_card.setProperty("armed", armed)
            self.video_card.style().unpolish(self.video_card)
            self.video_card.style().polish(self.video_card)

        label = state.stable_label or state.label
        stable = state.stable_label is not None
        if state.dial_active:
            self.gesture_name.setText("Dial")
            self.gesture_name.setStyleSheet(
                f"font-size: 30px; font-weight: 600; color: {theme.GOOD};"
            )
            self.gesture_action.setText(f"{state.dial_degrees:+.0f}° · volume")
            self.hold_bar.setValue(0)
        else:
            self.gesture_name.setText(
                self.settings.gesture_label(label) if label else "No gesture"
            )
            color = theme.ACCENT if stable else (theme.TEXT if label else theme.TEXT_DIM)
            self.gesture_name.setStyleSheet(
                f"font-size: 30px; font-weight: 600; color: {color};"
            )

            if label:
                action = self.settings.binding_for(label)
                self.gesture_action.setText(f"→ {self.settings.action_label(action)}")
            elif state.armed:
                self.gesture_action.setText("Listening for gestures")
            else:
                self.gesture_action.setText(self._arm_hint())

            if state.arm_progress > 0.0 and not state.armed:
                self.hold_bar.setValue(int(state.arm_progress * 100))
            elif stable:
                fire_hold = max(1.0, float(self.settings.get("engine.fire_hold_ms", 400)))
                self.hold_bar.setValue(min(100, int(state.hold_ms / fire_hold * 100)))
            else:
                self.hold_bar.setValue(0)

        self.scores.update_scores(state.scores, label)
        self.m_hands.set_value(str(len(state.hands)))
        self.m_distance.set_value(
            f"{state.distance_m:.2f} m" if state.distance_m is not None else "—"
        )
        self.m_state.set_value("Armed" if state.armed else "Disarmed")
        if state.features is not None:
            f = state.features
            self.m_thumb.set_value(
                f"{f.thumb_angle:+.0f}°  L{f.thumb_out_left:+.2f} R{f.thumb_out_right:+.2f}"
            )
        else:
            self.m_thumb.set_value("—")
        self.m_dial.set_value(
            f"engaged {state.dial_degrees:+.0f}°" if state.dial_active else "—"
        )
        if not bool(self.settings.get("cursor.enabled", False)):
            self.m_cursor.set_value("off")
        elif state.pointer is not None:
            self.m_cursor.set_value(
                f"pointing · {'pinch' if state.pointer_pinch else 'move'}"
            )
        else:
            self.m_cursor.set_value("on")
        self.chip_latency.setText(f"{result.inference_ms:.1f} ms")
        self.chip_fps.setText(f"{result.fps:.0f} fps")
        self.chip_latency.setText(f"{result.inference_ms:.1f} ms")

        for gesture, action in result.fired:
            self.flash.flash(
                f"{self.settings.gesture_label(gesture)} → {self.settings.action_label(action)}"
            )

    def _arm_hint(self) -> str:
        pose = self.settings.gesture_label(self.settings.get("engine.arm_pose", "rock"))
        if self.settings.get("engine.arm_mode", "pose") != "pose":
            return "Always listening"
        return f"Hold {pose} to arm"

    def _refresh_footer(self) -> None:
        practice = bool(self.settings.get("safety.practice_mode", True))
        self.footer_right.setText(
            "Practice mode · no keystrokes are sent" if practice
            else "Live mode · keystrokes are sent to the focused app"
        )
        color = theme.TEXT_DIM if practice else theme.WARN
        self.footer_right.setStyleSheet(f"font-size: 11px; color: {color};")

    # ------------------------------------------------------------------ #

    def set_practice(self, on: bool) -> None:
        self.practice_switch.setChecked(on)

    def toggle_arm(self) -> None:
        """Arm / disarm from the tray. The engine flag is a plain bool assignment,
        so this is safe to poke from the UI thread."""
        worker = self.worker
        if worker is None or worker.pipeline is None:
            return
        engine = worker.pipeline.engine
        engine.set_armed(not engine.armed)
        self.log.add_line("Armed manually" if engine.armed else "Disarmed manually")

    @property
    def practice_on(self) -> bool:
        return bool(self.settings.get("safety.practice_mode", True))

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt naming
        if self.tray is not None and not self._quitting:
            event.ignore()
            self.hide()
            return
        self.stop_capture()
        super().closeEvent(event)

    def quit_app(self) -> None:
        self._quitting = True
        self._save_tuning()
        self.stop_capture()
        self.close()
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.quit()
