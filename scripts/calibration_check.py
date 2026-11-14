"""Calibration maths checks.

    python scripts/calibration_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.calibration import distance_range, median_point, region_from_corners  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


def main() -> int:
    # ---- cursor region --------------------------------------------------- #
    corners = [(0.30, 0.25), (0.70, 0.26), (0.72, 0.75), (0.29, 0.74)]
    region = region_from_corners(corners, margin=0.02)
    check("region spans the corners",
          abs(region["x0"] - 0.27) < 1e-6 and abs(region["x1"] - 0.74) < 1e-6
          and abs(region["y0"] - 0.23) < 1e-6 and abs(region["y1"] - 0.77) < 1e-6,
          str(region))

    edge = region_from_corners([(0.02, 0.02), (0.98, 0.98)])
    check("region clamps to 0..1",
          0.0 <= edge["x0"] <= 0.0 + 1e-6 and 1.0 - 1e-6 <= edge["x1"] <= 1.0,
          str(edge))

    try:
        region_from_corners([(0.5, 0.5), (0.51, 0.51)])
        check("tiny spread is rejected", False, "no error raised")
    except ValueError:
        check("tiny spread is rejected", True)

    try:
        region_from_corners([(0.5, 0.5)])
        check("single point is rejected", False, "no error raised")
    except ValueError:
        check("single point is rejected", True)

    # ---- median point ---------------------------------------------------- #
    check("median ignores missing frames", median_point([None, (0.2, 0.3), None, (0.2, 0.3)] * 3) == (0.2, 0.3),
          str(median_point([None, (0.2, 0.3)] * 3)))
    check("too few samples yields none", median_point([(0.2, 0.3)] * 3) is None)

    jitter = [(0.50 + 0.02 * i, 0.40) for i in range(-3, 4)]
    point = median_point(jitter)
    check("median rejects jitter", point is not None and abs(point[0] - 0.50) < 1e-6, str(point))

    # ---- depth window ---------------------------------------------------- #
    samples = [0.45, 0.50, 0.62, 0.80, 1.05, 1.20, 0.70]
    low, high = distance_range(samples, padding=0.10)
    check("depth window pads the observed range",
          abs(low - 0.35) < 1e-6 and abs(high - 1.30) < 1e-6, f"{low}..{high}")

    low, high = distance_range([0.05, 0.10, 0.15, 0.22, 0.30], padding=0.10)
    check("depth window clamps to the minimum", abs(low - 0.15) < 1e-6, f"{low}..{high}")

    try:
        distance_range([0.60, 0.60, 0.60, 0.61], padding=0.01)
        check("narrow depth range is rejected", False, "no error raised")
    except ValueError:
        check("narrow depth range is rejected", True)

    try:
        distance_range([None, None, 0.5, None])
        check("insufficient depth samples rejected", False, "no error raised")
    except ValueError:
        check("insufficient depth samples rejected", True)

    failures = 0
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail and not ok else ''}")
        if not ok:
            failures += 1
    print()
    print("all checks pass" if not failures else f"{failures} FAILURE(S)")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
