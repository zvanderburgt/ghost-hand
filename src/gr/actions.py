"""Windows action dispatch.

Everything is routed through :class:`ActionBus`, which refuses to touch the
keyboard while practice mode is on - it only reports what it *would* have done.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

from .config import ACTIONS, Settings
from .macros import MacroPlayer
from .soundboard import SoundBoard

user32 = ctypes.windll.user32

# ---------------------------------------------------------------- SendInput

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_EXTENDEDKEY = 0x0001

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12
VK_LWIN = 0x5B

VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

VK_C = 0x43
VK_V = 0x56
VK_D = 0x44
VK_ESC = 0x1B
VK_TAB = 0x09
VK_Z = 0x5A
VK_Y = 0x59
VK_S = 0x53

ULONG_PTR = ctypes.POINTER(ctypes.c_ulong)


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD),
        ("dwFlags", wt.DWORD), ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
        ("time", wt.DWORD), ("dwExtraInfo", ULONG_PTR),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("union", _INPUTUNION)]


def _key_events(*pairs: tuple[int, bool]) -> None:
    """pairs of (virtual_key, is_key_up)."""
    if not pairs:
        return
    n = len(pairs)
    arr = (INPUT * n)()
    for i, (vk, up) in enumerate(pairs):
        arr[i].type = INPUT_KEYBOARD
        arr[i].union.ki = KEYBDINPUT(
            wVk=vk,
            wScan=0,
            dwFlags=KEYEVENTF_KEYUP if up else 0,
            time=0,
            dwExtraInfo=None,
        )
    user32.SendInput(n, arr, ctypes.sizeof(INPUT))


def tap(vk: int) -> None:
    _key_events((vk, False), (vk, True))


def chord(modifiers: list[int], vk: int) -> None:
    for mod in modifiers:
        _key_events((mod, False))
        time.sleep(0.012)
    tap(vk)
    for mod in reversed(modifiers):
        time.sleep(0.012)
        _key_events((mod, True))


# ---------------------------------------------------------------- Actions


@dataclass
class ActionResult:
    ok: bool
    message: str
    action_id: str = ""


class ActionBus:
    MEDIA = {
        "media.play_pause": VK_MEDIA_PLAY_PAUSE,
        "media.next": VK_MEDIA_NEXT_TRACK,
        "media.prev": VK_MEDIA_PREV_TRACK,
        "media.mute": VK_VOLUME_MUTE,
        "media.volume_up": VK_VOLUME_UP,
        "media.volume_down": VK_VOLUME_DOWN,
    }

    def __init__(self, settings: Settings, log: Callable[[str], None] | None = None) -> None:
        self.s = settings
        self.log = log or (lambda _msg: None)
        self.macro_player = MacroPlayer()
        self.soundboard = SoundBoard(settings, log=self.log)
        self.dry_run = False           # demo mode: log actions, never send input

    @property
    def practice(self) -> bool:
        return bool(self.s.get("safety.practice_mode", True))

    def label(self, action_id: str) -> str:
        return self.s.action_label(action_id)

    def fire(self, action_id: str, target: str | None = None) -> ActionResult:
        if action_id in ("", "none", None):
            return ActionResult(False, "No action bound", action_id or "")

        name = self.label(action_id)
        if self.practice or self.dry_run:
            msg = f"Practice: would run «{name}»"
            self.log(msg)
            return ActionResult(True, msg, action_id)

        try:
            self._execute(action_id, target)
        except Exception as exc:  # noqa: BLE001 - surface anything to the log
            msg = f"Action failed: {name} ({exc})"
            self.log(msg)
            return ActionResult(False, msg, action_id)

        msg = f"Ran «{name}»"
        self.log(msg)
        return ActionResult(True, msg, action_id)

    def _execute(self, action_id: str, target: str | None = None) -> None:
        if action_id in self.MEDIA:
            tap(self.MEDIA[action_id])
            return

        simple = {
            "system.copy": ([VK_CONTROL], VK_C),
            "system.paste": ([VK_CONTROL], VK_V),
            "system.undo": ([VK_CONTROL], VK_Z),
            "system.redo": ([VK_CONTROL], VK_Y),
            "system.show_desktop": ([VK_LWIN], VK_D),
            "system.alt_tab": ([VK_MENU], VK_TAB),
            "system.task_manager": ([VK_CONTROL, VK_SHIFT], VK_ESC),
            "system.screenshot": ([VK_LWIN, VK_SHIFT], VK_S),
        }
        if action_id in simple:
            mods, key = simple[action_id]
            chord(mods, key)
            return

        if action_id == "system.lock":
            user32.LockWorkStation()
            return

        if action_id == "app.launch":
            if not target:
                raise RuntimeError("No app path configured for this binding")
            self.launch(target)
            return

        if action_id.startswith("sound.play:"):
            sound_id = action_id.split(":", 1)[1]
            sound = self.s.sound(sound_id)
            if not sound:
                raise RuntimeError(f"Sound {sound_id!r} no longer exists")
            if not self.soundboard.play(sound):
                raise RuntimeError("Could not play sound")
            return

        if action_id.startswith("macro.play:"):
            macro_id = action_id.split(":", 1)[1]
            macro = self.s.macro(macro_id)
            if not macro:
                raise RuntimeError(f"Macro {macro_id!r} no longer exists")
            if not self.macro_player.play(macro):
                raise RuntimeError("A macro is already playing")
            return

        raise RuntimeError(f"Unknown action {action_id!r}")

    # -- helpers for future editing ------------------------------------- #

    @staticmethod
    def launch(path: str, args: str = "") -> None:
        if path.lower().endswith((".exe", ".bat", ".cmd", ".lnk")) and args:
            subprocess.Popen([path, *args.split()], close_fds=True)
        else:
            os.startfile(path)  # noqa: S606 - intentional shell open
