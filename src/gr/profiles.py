"""Foreground-application profiles.

A profile is a named binding set with a match rule, e.g. ``"spotify.exe, vlc.exe"``.
When the focused window's process matches, that profile's bindings take precedence;
anything it doesn't define falls back to the default bindings.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from pathlib import Path

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def foreground_process_name() -> str:
    """Lower-case exe name of the focused window, or '' if unavailable."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return ""
        try:
            buffer = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buffer))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return Path(buffer.value).name.lower()
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 - non-Windows or access denied
        return ""
    return ""


def rule_tokens(rule: str) -> list[str]:
    if not rule:
        return []
    cleaned = rule.replace(";", ",").replace("|", ",")
    return [token.strip().lower() for token in cleaned.split(",") if token.strip()]


def match_rule(rule: str, process: str) -> bool:
    """Case-insensitive substring match against any token in the rule."""
    if not rule or not process:
        return False
    process = process.lower()
    return any(token in process for token in rule_tokens(rule))


def profile_for(profiles: list[dict], process: str) -> str:
    """First profile whose rule matches, else 'default'."""
    for profile in profiles:
        if match_rule(str(profile.get("match", "")), process):
            return str(profile.get("id") or "default")
    return "default"
