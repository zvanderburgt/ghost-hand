"""Armed-toast geometry and colour helpers (no window shown).

    python scripts/overlay_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QRect, QSize  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402

from gr.ui.armed_overlay import (accent_from_abgr, ensure_contrast,  # noqa: E402
                                 luminance, pill_rect)

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


def main() -> int:
    # ---- accent parsing --------------------------------------------------- #
    colour = accent_from_abgr(0x00332211)          # AABBGGRR -> R=0x11 G=0x22 B=0x33
    check("accent parses ABGR", (colour.red(), colour.green(), colour.blue()) == (0x11, 0x22, 0x33),
          f"{colour.red()},{colour.green()},{colour.blue()}")
    check("white accent survives",
          accent_from_abgr(0x00FFFFFF).name().lower() == "#ffffff",
          accent_from_abgr(0x00FFFFFF).name())

    # ---- contrast --------------------------------------------------------- #
    dark = QColor(12, 12, 14)
    lifted = ensure_contrast(dark)
    check("dark accent is lifted for readability",
          luminance(lifted) >= 0.45 and luminance(lifted) > luminance(dark),
          f"{luminance(dark):.2f} -> {luminance(lifted):.2f}")
    bright = QColor(76, 194, 255)
    check("bright accent is untouched",
          ensure_contrast(bright).name().lower() == bright.name().lower(),
          ensure_contrast(bright).name())
    check("pure black becomes visible", luminance(ensure_contrast(QColor(0, 0, 0))) >= 0.45)

    # ---- pill placement ---------------------------------------------------- #
    primary = QRect(0, 0, 1000, 800)
    rect = pill_rect(primary, QSize(132, 36), margin=72)
    check("pill is horizontally centred",
          rect.x() == (1000 - 132) // 2 and rect.width() == 132, str(rect))
    check("pill sits above the bottom edge",
          rect.y() == 800 - 36 - 72, str(rect))

    portrait = QRect(3440, 0, 1080, 1920)
    rect = pill_rect(portrait, QSize(132, 36), margin=72)
    check("second monitor handled",
          rect.x() == 3440 + (1080 - 132) // 2 and rect.y() == 1920 - 36 - 72, str(rect))

    negative = QRect(-1920, -200, 3440, 1440)
    rect = pill_rect(negative, QSize(132, 36), margin=72)
    check("negative origin handled",
          rect.x() == -1920 + (3440 - 132) // 2 and rect.y() == -200 + 1440 - 36 - 72, str(rect))

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
