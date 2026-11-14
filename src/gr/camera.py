"""RealSense capture: mirrored color + depth aligned to the color stream."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np

try:
    import pyrealsense2 as rs
except ImportError:  # pragma: no cover - reported nicely at start-up
    rs = None


class CameraError(RuntimeError):
    pass


@dataclass
class Frame:
    color: np.ndarray                     # BGR uint8, already mirrored
    depth: np.ndarray | None             # uint16 millimetres, color-aligned
    timestamp_ms: int
    index: int
    shape: tuple[int, int] = field(init=False)

    def __post_init__(self) -> None:
        self.shape = (self.color.shape[1], self.color.shape[0])  # (w, h)

    def depth_at(self, x: float, y: float, radius: int = 4) -> float | None:
        """Median depth in metres around a pixel, ignoring holes."""
        if self.depth is None:
            return None
        h, w = self.depth.shape[:2]
        x0 = max(0, int(x) - radius)
        x1 = min(w, int(x) + radius + 1)
        y0 = max(0, int(y) - radius)
        y1 = min(h, int(y) + radius + 1)
        if x1 <= x0 or y1 <= y0:
            return None
        patch = self.depth[y0:y1, x0:x1]
        valid = patch[patch > 0]
        if valid.size == 0:
            return None
        return float(np.median(valid)) / 1000.0


class RealSenseCamera:
    def __init__(
        self,
        color_size: tuple[int, int] = (1280, 720),
        depth_size: tuple[int, int] = (848, 480),
        fps: int = 30,
        mirror: bool = True,
    ) -> None:
        if rs is None:
            raise CameraError(
                "pyrealsense2 is not installed. Run: pip install pyrealsense2"
            )
        self.color_size = color_size
        self.depth_size = depth_size
        self.fps = fps
        self.mirror = mirror
        self._pipeline: "rs.pipeline | None" = None
        self._align = None
        self._depth_scale = 0.001
        self._index = 0
        self._t0 = time.perf_counter()
        self.serial: str | None = None
        self.firmware: str | None = None

    # ------------------------------------------------------------------ #

    def start(self) -> None:
        ctx = rs.context()
        devices = list(ctx.query_devices())
        if not devices:
            raise CameraError("No RealSense device found. Is the camera plugged in?")

        cfg = rs.config()
        cw, ch = self.color_size
        dw, dh = self.depth_size
        cfg.enable_stream(rs.stream.color, cw, ch, rs.format.bgr8, self.fps)
        cfg.enable_stream(rs.stream.depth, dw, dh, rs.format.z16, self.fps)

        self._pipeline = rs.pipeline()
        try:
            profile = self._pipeline.start(cfg)
        except RuntimeError as exc:
            self._pipeline = None
            raise CameraError(
                f"Could not start the camera streams ({cw}x{ch}@{self.fps}). "
                f"Is another app using it? Details: {exc}"
            ) from exc

        device = profile.get_device()
        self.serial = device.get_info(rs.camera_info.serial_number)
        try:
            self.firmware = device.get_info(rs.camera_info.firmware_version)
        except RuntimeError:
            self.firmware = None

        depth_sensor = device.first_depth_sensor()
        self._depth_scale = depth_sensor.get_depth_scale()
        self._align = rs.align(rs.stream.color)

        # Let auto-exposure settle so the first frames aren't black.
        for _ in range(8):
            self._pipeline.wait_for_frames(1000)

    def poll(self, timeout_ms: int = 1500) -> Frame | None:
        if self._pipeline is None:
            return None
        try:
            frames = self._pipeline.wait_for_frames(timeout_ms)
        except RuntimeError:
            return None

        aligned = self._align.process(frames)
        color_frame = aligned.get_color_frame()
        depth_frame = aligned.get_depth_frame()
        if not color_frame:
            return None

        color = np.asanyarray(color_frame.get_data())
        if self.mirror:
            color = cv2.flip(color, 1)

        depth = None
        if depth_frame:
            raw = np.asanyarray(depth_frame.get_data())
            if self.mirror:
                raw = cv2.flip(raw, 1)
            # RealSense returns depth units in metres; store millimetres.
            depth = np.clip(raw * self._depth_scale * 1000.0, 0, 65535).astype(np.uint16)

        self._index += 1
        ts = int((time.perf_counter() - self._t0) * 1000)
        return Frame(color=color, depth=depth, timestamp_ms=ts, index=self._index)

    def stop(self) -> None:
        if self._pipeline is not None:
            try:
                self._pipeline.stop()
            except RuntimeError:
                pass
            self._pipeline = None

    @property
    def intrinsics_note(self) -> str:
        cw, ch = self.color_size
        return f"D435 · {cw}x{ch}@{self.fps} · depth aligned"
