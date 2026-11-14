"""Render the app icon to assets/app.ico (build input).

    python scripts/make_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from gr.config import ASSETS_DIR  # noqa: E402
from gr.ui.icon import app_icon  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    png = ASSETS_DIR / "app-256.png"
    icon = app_icon()
    icon.pixmap(256, 256).save(str(png), "PNG")

    ico = ASSETS_DIR / "app.ico"
    try:
        from PIL import Image

        image = Image.open(png)
        image.save(ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        print(f"wrote {ico}")
    except Exception as exc:  # noqa: BLE001
        print(f"could not write .ico ({exc}); PNG left at {png}")
        return 1
    finally:
        png.unlink(missing_ok=True)
        app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
