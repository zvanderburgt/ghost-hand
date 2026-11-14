"""Synthetic hand + frame generator.

Used by ``VisionPipeline(demo=True)`` so the whole UI and the classifier can be
exercised without a camera.  Also handy as a classifier smoke test.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from .camera import Frame
from .hands import Hand

# --------------------------------------------------------------------- #
# Canonical hand geometry in "hand units". Palm is ~0.59 wide, 0.38 tall.
# --------------------------------------------------------------------- #

WRIST_U = (0.00, 0.62)
MCPS = {
    "index": (-0.22, 0.28),
    "middle": (-0.02, 0.24),
    "ring": (0.18, 0.28),
    "pinky": (0.36, 0.36),
}
THUMB_CMC_U = (-0.24, 0.50)
THUMB_MCP_U = (-0.28, 0.50)
SPREAD_DEG = {"index": -8.0, "middle": 0.0, "ring": 8.0, "pinky": 18.0}
FINGER_LANDMARKS = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
SEGMENTS = (0.30, 0.20, 0.16)

# tip position of the thumb per pose (in hand units)
THUMB_TIPS = {
    "open_palm": (-0.72, 0.36),
    "thumbs_up": (-0.26, -0.06),
    "thumbs_down": (-0.26, 1.04),
    "thumb_left": (-0.84, 0.46),
    "thumb_right": (0.66, 0.44),
    "point_up": (-0.20, 0.40),   # tucked beside the index finger
    "rock": (-0.08, 0.34),       # thumb curled over the folded fingers
    "peace": (-0.16, 0.42),
    "fist": (-0.12, 0.32),
    "three": (-0.16, 0.42),
    "ok_sign": None,             # computed from the curled index tip
}

POSE_SPECS: dict[str, str] = {
    "open_palm": "1111",
    "fist": "0000",
    "peace": "1100",
    "three": "1110",
    "point_up": "1000",
    "rock": "1001",
    "thumbs_up": "0000",
    "thumbs_down": "0000",
    "thumb_left": "0000",
    "thumb_right": "0000",
    "ok_sign": "0111",
}


def _deg_dir(angle_deg: float) -> tuple[float, float]:
    rad = math.radians(angle_deg)
    return math.cos(rad), math.sin(rad)


def make_hand(
    pose: str,
    width: int,
    height: int,
    size_px: float = 420.0,
    center: tuple[float, float] | None = None,
    rotation_deg: float = 0.0,
) -> Hand:
    """Build a plausible 21-point hand for the requested pose."""
    spec = POSE_SPECS.get(pose, "1111")
    cx, cy = center or (width * 0.5, height * 0.52)

    def project(ux: float, uy: float) -> tuple[float, float]:
        # hand units -> pixels, with optional roll around the wrist
        x, y = ux * size_px, uy * size_px
        th = math.radians(rotation_deg)
        cos_t, sin_t = math.cos(th), math.sin(th)
        rx, ry = x * cos_t - y * sin_t, x * sin_t + y * cos_t
        return cx + rx, cy + ry

    pts: list[tuple[float, float]] = [(0.0, 0.0)] * 21
    pts[0] = project(*WRIST_U)

    for cycle, finger in enumerate(("index", "middle", "ring", "pinky")):
        extended = spec[cycle] == "1"
        mcp_u = MCPS[finger]
        base = FINGER_LANDMARKS[finger]
        pts[base[0]] = project(*mcp_u)

        if extended:
            ang = -90.0 + SPREAD_DEG[finger]
            tip_u = (mcp_u[0] + math.cos(math.radians(ang)) * 0.66,
                     mcp_u[1] + math.sin(math.radians(ang)) * 0.66)
            a = np.array(pts[base[0]])
            b = np.array(project(*tip_u))
            pts[base[3]] = (float(b[0]), float(b[1]))
            pts[base[1]] = tuple(a + (b - a) * 0.42)
            pts[base[2]] = tuple(a + (b - a) * 0.72)
        else:
            # folded back onto the palm
            dx = 0.06 if finger in ("index", "middle") else 0.10
            pts[base[1]] = project(mcp_u[0] - 0.01, mcp_u[1] - 0.26)
            pts[base[2]] = project(mcp_u[0] + dx * 0.6, mcp_u[1] + 0.01)
            pts[base[3]] = project(mcp_u[0] + dx, mcp_u[1] + 0.07)

    # thumb
    pts[1] = project(*THUMB_CMC_U)
    pts[2] = project(*THUMB_MCP_U)
    thumb_tip = THUMB_TIPS.get(pose)
    if pose == "ok_sign":
        thumb_tip = (pts[8][0], pts[8][1])
    elif thumb_tip is None:
        thumb_tip = THUMB_TIPS["fist"]
    pts[4] = project(*thumb_tip) if pose != "ok_sign" else thumb_tip
    pts[3] = (
        (pts[2][0] + pts[4][0]) * 0.5,
        (pts[2][1] + pts[4][1]) * 0.5,
    )

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    scale = math.dist(pts[0], pts[9]) or 1.0
    bbox = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))

    return Hand(
        landmarks=[(x / width, y / height, 0.0) for x, y in pts],
        px=pts,
        handedness="Right",
        score=0.98,
        scale_px=scale,
        bbox=bbox,
        palm_depth_m=0.62,
    )


# --------------------------------------------------------------------- #


def _background(width: int, height: int, t: float) -> np.ndarray:
    """A soft studio-ish backdrop that reads like a camera feed."""
    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    base = 30 + 26 * (1 - y) + 8 * np.sin(x * 3.1 + t * 0.6)
    img = np.dstack([base * 0.72 + 12, base * 0.85 + 10, base * 1.0 + 6]).astype(np.uint8)
    img = np.ascontiguousarray(img)

    step = 48
    for gx in range(0, width, step):
        cv2.line(img, (gx, 0), (gx, height), (48, 54, 60), 1)
    for gy in range(0, height, step):
        cv2.line(img, (0, gy), (width, gy), (48, 54, 60), 1)
    return img


def demo_frame(settings, now_ms: float, poses: list[str] | None = None) -> tuple[Frame, list[Hand]]:
    width = int(settings.get("camera.color_width", 1280))
    height = int(settings.get("camera.color_height", 720))
    t = now_ms / 1000.0

    cycle = poses or ["rock", "peace", "thumbs_up", "thumb_left", "thumb_right", "point_up", "fist"]
    slot = int(t // 4.0)
    pose = cycle[slot % len(cycle)]

    sway_x = math.sin(t * 0.9) * width * 0.035
    sway_y = math.cos(t * 0.7) * height * 0.02
    img = _background(width, height, t)

    hand = make_hand(pose, width, height, size_px=height * 0.58,
                     center=(width * 0.5 + sway_x, height * 0.55 + sway_y),
                     rotation_deg=math.sin(t * 0.5) * 4.0)

    cv2.putText(img, "DEMO SOURCE", (width - 210, 34), cv2.FONT_HERSHEY_SIMPLEX,
                0.6, (110, 190, 235), 1, cv2.LINE_AA)
    cv2.putText(img, pose.upper(), (width - 210, 58), cv2.FONT_HERSHEY_SIMPLEX,
                0.45, (120, 120, 128), 1, cv2.LINE_AA)

    depth = np.full((height, width), 0, dtype=np.uint16)
    frame = Frame(color=img, depth=depth, timestamp_ms=int(now_ms), index=slot)
    return frame, [hand]
