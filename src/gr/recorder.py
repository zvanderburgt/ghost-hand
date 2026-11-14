"""Debug clip recording: keeps a short annotated pre-roll ring buffer."""

from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

from .config import DEBUG_DIR

RING_SECONDS = 1.5
RING_SIZE = (640, 360)
RING_FPS = 15


class ClipRecorder:
    def __init__(self) -> None:
        self.ring: deque[np.ndarray] = deque(maxlen=int(RING_SECONDS * RING_FPS))
        self._tick = 0

    def add(self, frame: np.ndarray) -> None:
        # Store at ~15fps to keep memory small.
        self._tick += 1
        if self._tick % 2:
            return
        self.ring.append(cv2.resize(frame, RING_SIZE, interpolation=cv2.INTER_AREA))

    def save(self, events: list[str] | None = None, tag: str = "clip") -> Path | None:
        if not self.ring:
            return None
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = DEBUG_DIR / f"{tag}-{stamp}.mp4"
        writer = cv2.VideoWriter(
            str(path), cv2.VideoWriter_fourcc(*"mp4v"), RING_FPS, RING_SIZE
        )
        for frame in self.ring:
            writer.write(frame)
        writer.release()

        meta = DEBUG_DIR / f"{tag}-{stamp}.json"
        meta.write_text(
            json.dumps({"saved": stamp, "events": events or []}, indent=2), encoding="utf-8"
        )
        return path
