"""Custom gesture templates.

A template is a *shape descriptor*: the 21 landmarks translated to the wrist,
rotated so the wrist->middle-knuckle axis points up, and scaled by hand size.
That makes matching invariant to where the hand is, how big it looks, and how
the wrist is rolled - so a learned shape works anywhere in frame.

Recognition is nearest-template: the engine turns the distance into a 0..1 score
and feeds it through the same stability/arming/hold machinery as built-in poses.
"""

from __future__ import annotations

import math

import numpy as np

from .hands import Hand

# Mean per-landmark distance (in hand lengths) at which a template stops scoring.
CUSTOM_CUTOFF = 0.22


def descriptor(hand: Hand) -> np.ndarray | None:
    """Rotation/scale/translation-invariant shape vector for one hand."""
    points = np.asarray(hand.px, dtype=np.float32)
    if points.shape != (21, 2):
        return None
    wrist = points[0]
    scale = float(np.hypot(*(points[9] - wrist)))
    if scale < 1e-3:
        return None

    centred = (points - wrist) / scale
    axis = centred[9]
    angle = math.atan2(float(axis[1]), float(axis[0]))
    cos_a, sin_a = math.cos(-angle), math.sin(-angle)
    rotation = np.array([[cos_a, -sin_a], [sin_a, cos_a]], dtype=np.float32)
    return (centred @ rotation.T).reshape(-1)


def template_from(samples: list[np.ndarray | None]) -> list[float] | None:
    usable = [s for s in samples if s is not None]
    if len(usable) < 5:
        return None
    stacked = np.stack(usable)
    return np.mean(stacked, axis=0).astype(np.float32).tolist()


def distance(template, sample) -> float:
    if template is None or sample is None:
        return 9.9
    a = np.asarray(template, dtype=np.float32)
    b = np.asarray(sample, dtype=np.float32)
    if a.size == 0 or a.size != b.size:
        return 9.9
    per_point = np.linalg.norm(a.reshape(-1, 2) - b.reshape(-1, 2), axis=1)
    return float(np.mean(per_point))


def match_score(template, sample: np.ndarray | None,
                cutoff: float = CUSTOM_CUTOFF) -> float:
    if sample is None or template is None:
        return 0.0
    value = 1.0 - distance(template, sample) / max(1e-6, cutoff)
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)
