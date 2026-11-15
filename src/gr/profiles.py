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


def foreground_window() -> tuple[str, str]:
    """(lower-case exe name, window title) of the focused window."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", ""

        title_buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buffer, 512)
        title = title_buffer.value

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return "", title

        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return "", title
        try:
            buffer = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buffer))
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return Path(buffer.value).name.lower(), title
        finally:
            kernel32.CloseHandle(handle)
    except Exception:  # noqa: BLE001 - non-Windows or access denied
        return "", ""
    return "", ""


def foreground_process_name() -> str:
    """Lower-case exe name of the focused window, or '' if unavailable."""
    return foreground_window()[0]


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


def profile_for(profiles: list[dict], process: str, title: str = "") -> str:
    """First profile whose rules match, else 'default'.

    A profile can match on process, window title, or both. An empty profile with
    no rules at all never matches, so a blank entry can't swallow everything.
    """
    for profile in profiles:
        process_rule = str(profile.get("match") or "").strip()
        title_rule = str(profile.get("title") or "").strip()
        if not process_rule and not title_rule:
            continue
        process_ok = (not process_rule) or match_rule(process_rule, process)
        title_ok = (not title_rule) or (title_rule.lower() in (title or "").lower())
        if process_ok and title_ok:
            return str(profile.get("id") or "default")
    return "default"
