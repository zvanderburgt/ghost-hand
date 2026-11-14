"""MediaPipe hand tracking wrapper.

Frames arrive already mirrored from the camera, which means MediaPipe's
handedness labels match the user's real hands and screen-space x is
"left of the image = left of the monitor".
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from .config import HAND_MODEL_PATH

HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)

FINGERTIPS = (4, 8, 12, 16, 20)
WRIST, THUMB_MCP, INDEX_MCP, PINKY_MCP, MIDDLE_MCP = 0, 2, 5, 17, 9


class HandTrackerError(RuntimeError):
    pass


@dataclass
class Hand:
    landmarks: list[tuple[float, float, float]]   # normalised 0..1
    px: list[tuple[float, float]]                 # pixel coords
    handedness: str                               # "Left" / "Right"
    score: float
    scale_px: float                               # wrist -> middle MCP
    bbox: tuple[int, int, int, int]
    palm_depth_m: float | None = None

    @property
    def center(self) -> tuple[float, float]:
        x0, y0, x1, y1 = self.bbox
        return (x0 + x1) / 2.0, (y0 + y1) / 2.0


class HandTracker:
    def __init__(
        self,
        model_path=HAND_MODEL_PATH,
        max_hands: int = 2,
        min_detection: float = 0.5,
        min_presence: float = 0.5,
        min_tracking: float = 0.45,
        depth_probe=None,
    ) -> None:
        if not model_path.exists():
            raise HandTrackerError(
                f"Missing hand model at {model_path}. Re-download hand_landmarker.task."
            )
        options = vision.HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max_hands,
            min_hand_detection_confidence=min_detection,
            min_hand_presence_confidence=min_presence,
            min_tracking_confidence=min_tracking,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._last_ts = -1
        self._timings: list[float] = []
        self.depth_probe = depth_probe

    # ------------------------------------------------------------------ #

    def process(self, bgr: np.ndarray, timestamp_ms: int) -> list[Hand]:
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        ts = max(int(timestamp_ms), self._last_ts + 1)
        self._last_ts = ts

        t0 = time.perf_counter()
        result = self._landmarker.detect_for_video(image, ts)
        self._timings.append((time.perf_counter() - t0) * 1000.0)
        if len(self._timings) > 30:
            self._timings.pop(0)

        hands: list[Hand] = []
        if not result.hand_landmarks:
            return hands

        for i, lms in enumerate(result.hand_landmarks):
            pts = [(lm.x * w, lm.y * h) for lm in lms]
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            pad = 10
            bbox = (
                int(max(0, min(xs) - pad)),
                int(max(0, min(ys) - pad)),
                int(min(w - 1, max(xs) + pad)),
                int(min(h - 1, max(ys) + pad)),
            )
            scale = float(np.hypot(
                pts[MIDDLE_MCP][0] - pts[WRIST][0],
                pts[MIDDLE_MCP][1] - pts[WRIST][1],
            ))

            label = "Unknown"
            score = 0.0
            if i < len(result.handedness) and result.handedness[i]:
                label = result.handedness[i][0].category_name or "Unknown"
                score = float(result.handedness[i][0].score)

            depth = None
            if self.depth_probe is not None:
                cx, cy = np.mean(xs), np.mean(ys)
                depth = self.depth_probe(cx, cy)

            hands.append(
                Hand(
                    landmarks=[(lm.x, lm.y, lm.z) for lm in lms],
                    px=pts,
                    handedness=label,
                    score=score,
                    scale_px=scale,
                    bbox=bbox,
                    palm_depth_m=depth,
                )
            )
        return hands

    @property
    def inference_ms(self) -> float:
        if not self._timings:
            return 0.0
        return float(sum(self._timings) / len(self._timings))

    def close(self) -> None:
        try:
            self._landmarker.close()
        except Exception:
            pass
