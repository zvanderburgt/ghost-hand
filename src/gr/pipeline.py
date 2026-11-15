"""The vision pipeline: camera -> tracker -> gesture engine -> annotated frame.

Runs on a worker thread; the UI only ever sees immutable snapshots through Qt
signals.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np

from .actions import ActionBus
from .camera import Frame, RealSenseCamera
from .config import Settings
from .cursor import CursorController
from .custom import descriptor as shape_descriptor
from .draw import draw_depth_preview, draw_hand, draw_hud
from .gestures import EngineState, GestureEngine
from .hands import HandTracker
from .profiles import foreground_process_name, profile_for
from .recorder import ClipRecorder
from .synthetic import demo_frame


@dataclass
class StepResult:
    display: np.ndarray                    # annotated colour frame
    depth_view: np.ndarray | None
    state: EngineState
    fps: float
    inference_ms: float
    events: list[str] = field(default_factory=list)
    fired: list[tuple[str, str]] = field(default_factory=list)  # (gesture, action)


class VisionPipeline:
    def __init__(self, settings: Settings, demo: bool = False) -> None:
        self.s = settings
        self.demo = demo
        self.camera: RealSenseCamera | None = None
        self.tracker: HandTracker | None = None
        self.engine = GestureEngine(settings)
        self.recorder = ClipRecorder()
        self.events: list[str] = []
        self._fps_samples: list[float] = []
        self._last_ts = 0.0
        self._demo_t0 = 0.0
        self._log_cursor = 0
        self._was_armed = False
        self._had_hand = False
        self._was_dial = False
        self._last_dial_log = 0.0
        self._last_ramp_log = 0.0
        self._was_ramp = False
        self._was_dragging = False
        self.bus = ActionBus(settings, log=self._log)
        self.bus.dry_run = demo
        self.cursor = CursorController(settings)
        self.latest_descriptor = None
        self.latest_pointer = None
        self.latest_distance = None
        self._last_profile_poll = 0.0

    # ------------------------------------------------------------------ #

    def _log(self, message: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.events.append(f"{stamp}  {message}")
        if len(self.events) > 300:
            del self.events[:-300]

    def open(self) -> None:
        if self.demo:
            self._demo_t0 = time.perf_counter() * 1000.0
            self._log("Demo source active - synthetic hands, no camera")
            self._log(
                "Practice mode ON - gestures are logged but no keys are sent"
                if self.bus.practice
                else "Live mode - gestures will send keyboard input"
            )
            return

        cam = RealSenseCamera(
            color_size=(self.s.get("camera.color_width"), self.s.get("camera.color_height")),
            depth_size=(self.s.get("camera.depth_width"), self.s.get("camera.depth_height")),
            fps=self.s.get("camera.fps"),
            mirror=self.s.get("camera.mirror"),
        )
        cam.start()
        self.camera = cam

        self.tracker = HandTracker(
            max_hands=self.s.get("detection.max_hands"),
            min_detection=self.s.get("detection.min_hand_detection_confidence"),
            min_presence=self.s.get("detection.min_hand_presence_confidence"),
            min_tracking=self.s.get("detection.min_tracking_confidence"),
        )
        self._log(f"Camera ready · serial {cam.serial}")
        self._log(
            "Practice mode ON - gestures are logged but no keys are sent"
            if self.bus.practice
            else "Live mode - gestures will send keyboard input"
        )

    def close(self) -> None:
        if self.camera is not None:
            self.camera.stop()
            self.camera = None
        if self.tracker is not None:
            self.tracker.close()
            self.tracker = None
        try:
            self.bus.soundboard.close()
        except Exception:  # noqa: BLE001 - teardown must not raise
            pass

    # ------------------------------------------------------------------ #

    def step(self) -> StepResult | None:
        if not self.demo and (self.camera is None or self.tracker is None):
            return None

        now_ms = time.perf_counter() * 1000.0
        if self.demo:
            frame, hands = demo_frame(self.s, now_ms - self._demo_t0)
        else:
            frame = self.camera.poll()
            if frame is None:
                return None
            # Palm depth has to come from the frame we just captured, so the
            # probe is rebound per frame (this also enables depth gating).
            if frame.depth is not None:
                self.tracker.depth_probe = (
                    lambda x, y, f=frame: f.depth_at(x, y, radius=6)
                )
            hands = self.tracker.process(frame.color, frame.timestamp_ms)

        state = self.engine.update(hands, now_ms)
        self.latest_descriptor = (
            shape_descriptor(state.primary) if state.primary is not None else None
        )
        self.latest_pointer = state.pointer
        self.latest_distance = state.distance_m

        # Switch binding sets when the focused application changes.
        if self.s.profiles and (now_ms - self._last_profile_poll) >= 500.0:
            self._last_profile_poll = now_ms
            self._update_profile()

        events: list[str] = []
        fired: list[tuple[str, str]] = []

        # Arming and presence transitions are the two things you want to see
        # while tuning, so they go straight into the event log.
        if state.armed != self._was_armed:
            events.append("Armed - gestures are live" if state.armed else "Disarmed")
            self._was_armed = state.armed
        has_hand = state.primary is not None
        if has_hand != self._had_hand:
            if has_hand:
                dist = state.distance_m
                events.append(
                    f"Hand detected{f' at {dist:.2f} m' if dist is not None else ''}"
                )
            else:
                events.append("Hand lost")
            self._had_hand = has_hand

        # ---- pointer ------------------------------------------------- #
        if state.pointer is not None or state.pointer_scroll_mode:
            pointer_x = state.pointer[0] if state.pointer else 0.5
            pointer_y = state.pointer[1] if state.pointer else state.pointer_scroll_y
            info = self.cursor.update(
                pointer_x, pointer_y, state.pointer_pinch_ratio, now_ms,
                middle_pinch_ratio=state.pointer_middle_pinch,
                scroll_mode=state.pointer_scroll_mode,
            )
            if info["clicked"]:
                events.append("Cursor dwell click" if info.get("dwell") else "Cursor click")
            if info.get("right_clicked"):
                events.append("Cursor right-click")
            if info["dragging"] and not self._was_dragging:
                events.append("Cursor drag started")
            self._was_dragging = info["dragging"]
        else:
            self.cursor.reset()
            self._was_dragging = False

        for gesture in state.fired:
            action = self.s.binding_for(gesture)
            result = self.bus.fire(action or "none", self.s.binding_target(gesture))
            fired.append((gesture, action or "none"))
            events.append(
                f"FIRED {self.s.gesture_label(gesture)} → {self.s.action_label(action)}"
            )
            if result.message:
                events.append(result.message)

        ticks = self.engine.take_ramp_ticks()
        if ticks:
            gesture = state.stable_label
            action = self.s.binding_for(gesture) if gesture else None
            if action:
                for _ in range(min(ticks, 5)):
                    self.bus.fire(action, self.s.binding_target(gesture))
                now_s = time.perf_counter()
                if now_s - self._last_ramp_log >= 0.3:
                    self._last_ramp_log = now_s
                    events.append(f"Ramp → {self.s.action_label(action)}")
        self._was_ramp = state.ramp_active

        if state.dial_active != self._was_dial:
            events.append("Dial engaged - turn your wrist" if state.dial_active else "Dial released")
            self._was_dial = state.dial_active

        if state.ramp_active != self._was_ramp:
            events.append("Ramp started" if state.ramp_active else "Ramp stopped")
            self._was_ramp = state.ramp_active

        dial_ticks = self.engine.take_dial_ticks()
        if dial_ticks:
            action = "media.volume_up" if dial_ticks > 0 else "media.volume_down"
            for _ in range(min(abs(dial_ticks), 5)):
                self.bus.fire(action)
            now_s = time.perf_counter()
            if now_s - self._last_dial_log >= 0.25:
                self._last_dial_log = now_s
                events.append(f"Dial → volume {'up' if dial_ticks > 0 else 'down'}")

        # Surface genuine failures (but not the practice-mode echo of every tick).
        pending = self.events[self._log_cursor:]
        self._log_cursor = len(self.events)
        events.extend(line for line in pending if "failed" in line.lower())

        # ---- annotate ------------------------------------------------ #
        display = frame.color.copy()
        for hand in _hands_by_size(hands):
            draw_hand(display, hand, None if hand is not state.primary else (state.stable_label or state.label))
        if state.gated:
            cv2.putText(display, "hand ignored: out of range", (16, display.shape[0] - 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (90, 190, 250), 1, cv2.LINE_AA)

        hud = [f"{(state.stable_label or state.label or 'no gesture').upper()}"]
        if state.distance_m is not None:
            hud.append(f"{state.distance_m:.2f} m")
        hud.append("ARMED" if state.armed else "disarmed")
        draw_hud(display, hud)

        # ---- fps ----------------------------------------------------- #
        dt = time.perf_counter() - self._last_ts
        self._last_ts = time.perf_counter()
        if 0 < dt < 1.0:
            self._fps_samples.append(1.0 / dt)
            if len(self._fps_samples) > 45:
                self._fps_samples.pop(0)
        fps = float(np.mean(self._fps_samples)) if self._fps_samples else 0.0

        depth_view = None
        if frame.depth is not None:
            small = cv2.resize(frame.depth, (480, 270), interpolation=cv2.INTER_NEAREST)
            depth_view = draw_depth_preview(small)

        self.recorder.add(display)

        return StepResult(
            display=display,
            depth_view=depth_view,
            state=state,
            fps=fps,
            inference_ms=0.0 if self.demo else self.tracker.inference_ms,
            events=events,
            fired=fired,
        )

    # ------------------------------------------------------------------ #

    def _update_profile(self) -> None:
        process = foreground_process_name()
        matched = profile_for(self.s.profiles, process)
        if matched == (self.s.active_profile or "default"):
            return
        self.s.active_profile = matched
        if matched == "default":
            self._log(f"Profile: default (focused: {process or 'unknown'})")
        else:
            profile = self.s.profile_by_id(matched) or {}
            self._log(f"Profile: {profile.get('name', matched)} (focused: {process})")

    def save_clip(self) -> str:
        path = self.recorder.save(events=self.events[-40:])
        msg = f"Saved debug clip {path.name}" if path else "Nothing to save yet"
        self._log(msg)
        return msg


def _hands_by_size(hands):
    """Draw the secondary hand first so the primary hand ends up on top."""
    return sorted(hands, key=lambda h: h.scale_px)
