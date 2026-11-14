"""Render the bindings dialog to a PNG for a quick visual check.

    python scripts/ui_smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from gr.config import DEBUG_DIR, Settings  # noqa: E402
from gr.macros import new_macro  # noqa: E402
from gr.ui import theme  # noqa: E402
from gr.ui.bindings_dialog import BindingsDialog  # noqa: E402
from gr.ui.custom_dialog import CustomGesturesDialog  # noqa: E402
from gr.ui.guide_dialog import GuideDialog  # noqa: E402
from gr.ui.macros_dialog import MacrosDialog  # noqa: E402
from gr.ui.sounds_dialog import SoundsDialog  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(theme.stylesheet())

    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    bindings = BindingsDialog(Settings.load())
    bindings.show()
    app.processEvents()
    bindings.resize(940, 680)
    app.processEvents()
    out = DEBUG_DIR / "bindings-dialog.png"
    bindings.grab().save(str(out))
    print(f"saved {out}")
    bindings.close()

    sample = Settings()
    sample.add_macro(new_macro("Open browser tabs", [
        {"t": 0.0, "kind": "key", "special": "ctrl", "down": True},
        {"t": 0.1, "kind": "key", "char": "t", "down": True},
        {"t": 0.2, "kind": "key", "char": "t", "down": False},
        {"t": 0.3, "kind": "key", "special": "ctrl", "down": False},
    ]))
    macros = MacrosDialog(sample)
    macros.show()
    app.processEvents()
    macros.resize(780, 520)
    app.processEvents()
    out = DEBUG_DIR / "macros-dialog.png"
    macros.grab().save(str(out))
    print(f"saved {out}")

    sounds_settings = Settings()
    sounds_settings.add_sound({
        "id": "demo1", "name": "Airhorn", "path": r"C:\sounds\airhorn.mp3",
        "duration": 1.4, "volume": 1.0,
    })
    sounds_settings.add_sound({
        "id": "demo2", "name": "Nice", "path": r"C:\sounds\nice.wav",
        "duration": 0.6, "volume": 1.0,
    })
    sounds = SoundsDialog(sounds_settings)
    sounds.show()
    app.processEvents()
    sounds.resize(820, 620)
    app.processEvents()
    out = DEBUG_DIR / "sounds-dialog.png"
    sounds.grab().save(str(out))
    print(f"saved {out}")

    custom = CustomGesturesDialog(sounds_settings)
    custom.show()
    app.processEvents()
    custom.resize(640, 480)
    app.processEvents()
    out = DEBUG_DIR / "custom-dialog.png"
    custom.grab().save(str(out))
    print(f"saved {out}")

    guide = GuideDialog(sample)
    guide.show()
    app.processEvents()
    guide.resize(880, 620)
    app.processEvents()
    out = DEBUG_DIR / "guide-dialog.png"
    guide.grab().save(str(out))
    print(f"saved {out}")

    for dialog in (bindings, macros, sounds, custom, guide):
        dialog.close()
        dialog.deleteLater()
    app.processEvents()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
