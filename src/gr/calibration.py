"""Calibration maths for the cursor region and depth gating.

Kept separate from the dialog so it can be tested without a camera.
"""

from __future__ import annotations

import statistics


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if value < lo else hi if value > hi else value


def region_from_corners(points: list[tuple[float, float]], margin: float = 0.02) -> dict:
    """Cursor mapping box from fingertip positions at the four screen corners."""
    if len(points) < 2:
        raise ValueError("need at least two corners")
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0 = _clamp(min(xs) - margin)
    x1 = _clamp(max(xs) + margin)
    y0 = _clamp(min(ys) - margin)
    y1 = _clamp(max(ys) + margin)
    if (x1 - x0) < 0.08 or (y1 - y0) < 0.08:
        raise ValueError("corners are too close together")
    return {"x0": round(x0, 4), "x1": round(x1, 4), "y0": round(y0, 4), "y1": round(y1, 4)}


def median_point(samples: list[tuple[float, float] | None]) -> tuple[float, float] | None:
    usable = [s for s in samples if s is not None]
    if len(usable) < 5:
        return None
    xs = [p[0] for p in usable]
    ys = [p[1] for p in usable]
    return statistics.median(xs), statistics.median(ys)


def distance_range(samples: list[float | None], padding: float = 0.10,
                   lo: float = 0.15, hi: float = 3.0) -> tuple[float, float]:
    """Accepted distance window from the nearest and furthest hand readings."""
    usable = [s for s in samples if s is not None and s > 0]
    if len(usable) < 5:
        raise ValueError("not enough depth readings")
    low = max(lo, min(usable) - padding)
    high = min(hi, max(usable) + padding)
    if (high - low) < 0.10:
        raise ValueError("hand barely moved - too narrow to calibrate")
    return round(low, 2), round(high, 2)
