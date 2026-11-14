"""Entry point: tray app + preview window.

    python src/main.py               # normal
    python src/main.py --demo        # synthetic hands, no camera
    python src/main.py --minimized   # start hidden in the tray
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PySide6.QtCore import QTimer, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QSystemTrayIcon  # noqa: E402

from gr.config import APP_NAME, SETTINGS_PATH, Settings  # noqa: E402
from gr.ui import theme  # noqa: E402
from gr.ui.icon import app_icon  # noqa: E402
from gr.ui.main_window import MainWindow  # noqa: E402
from gr.ui.tray import TrayIcon  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=APP_NAME)
    ap.add_argument("--demo", action="store_true", help="use a synthetic hand source")
    ap.add_argument("--minimized", action="store_true", help="start hidden in the tray")
    ap.add_argument("--screenshot", metavar="PATH", help="dev: grab the window and exit")
    ap.add_argument("--screenshot-delay", type=int, default=2600)
    ap.add_argument("--quit-after", type=int, default=0,
                    help="dev: quit cleanly after N milliseconds")
    args = ap.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("gesture-control")
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(app_icon())
    app.setQuitOnLastWindowClosed(False)
    app.setStyleSheet(theme.stylesheet())

    settings = Settings.load()
    if not SETTINGS_PATH.exists():
        try:
            settings.save()
        except OSError:
            pass
    window = MainWindow(settings, demo=args.demo)

    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = TrayIcon(window)
        window.tray = tray

    if args.screenshot:
        window.show()

        def grab() -> None:
            pixmap = window.grab()
            Path(args.screenshot).parent.mkdir(parents=True, exist_ok=True)
            pixmap.save(args.screenshot)
            print(f"saved {args.screenshot}")
            window._quitting = True
            window.quit_app()
            app.quit()

        QTimer.singleShot(args.screenshot_delay, grab)
        return app.exec()

    if not args.minimized:
        window.show()

    if not settings.get("ui.guide_seen", False):
        QTimer.singleShot(700, window.show_guide)

    if args.quit_after:
        QTimer.singleShot(args.quit_after, window.quit_app)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
