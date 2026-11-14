"""Start-with-Windows support via the per-user Run key."""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - non-Windows
    winreg = None

from .config import APP_DIR, FROZEN

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "GhostHand"
LEGACY_VALUE = "RealSenseGestureControl"
ENTRY_SCRIPT = APP_DIR / "src" / "main.py"


def launch_command() -> str:
    if FROZEN:
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    exe = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{exe}" "{ENTRY_SCRIPT}" --minimized'


def is_enabled() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, launch_command())
                try:  # drop the pre-rename entry so it can't launch a stale build
                    winreg.DeleteValue(key, LEGACY_VALUE)
                except FileNotFoundError:
                    pass
            else:
                for name in (VALUE_NAME, LEGACY_VALUE):
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
        return True
    except OSError:
        return False
