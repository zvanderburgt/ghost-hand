"""Macro recording and playback.

A macro is a list of timestamped events stored in settings.json:

    {"t": 0.42, "kind": "key",   "char": "a", "down": true}
    {"t": 0.51, "kind": "key",   "special": "ctrl", "down": true}
    {"t": 0.60, "kind": "mouse", "x": 900, "y": 500, "button": "left", "down": true}
    {"t": 0.70, "kind": "scroll", "x": 900, "y": 500, "dx": 0, "dy": -1}

Recording uses global pynput listeners (so it captures input sent to any app);
playback replays the same events through pynput controllers.
"""

from __future__ import annotations

import threading
import time
import uuid

from PySide6.QtCore import QObject, Signal

from pynput import keyboard, mouse

STOP_HOTKEY = "Ctrl+Alt+M"
MAX_EVENTS = 800
MODIFIER_NAMES = {"ctrl", "ctrl_l", "ctrl_r", "alt", "alt_l", "alt_r",
                  "alt_gr", "shift", "shift_l", "shift_r", "cmd", "cmd_l", "cmd_r"}


# --------------------------------------------------------------------------- #
# Event conversion
# --------------------------------------------------------------------------- #


def key_to_event(key, down: bool) -> dict | None:
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return {"kind": "key", "char": key.char, "down": down}
        if key.vk:
            return {"kind": "key", "vk": int(key.vk), "down": down}
        return None
    name = getattr(key, "name", None)
    if not name:
        return None
    return {"kind": "key", "special": name, "down": down}


def event_to_key(event: dict):
    if "char" in event:
        return event["char"]
    if "special" in event:
        return getattr(keyboard.Key, event["special"], None)
    if "vk" in event:
        return keyboard.KeyCode.from_vk(int(event["vk"]))
    return None


def describe(event: dict) -> str:
    kind = event.get("kind")
    if kind == "key":
        name = event.get("char") or event.get("special") or f"vk{event.get('vk')}"
        if name in MODIFIER_NAMES:
            return name.upper()
        return name if event.get("down") else f"↑{name}"
    if kind == "mouse":
        return f"{event.get('button', 'left')} {'down' if event.get('down') else 'up'}"
    if kind == "scroll":
        return f"scroll {event.get('dy', 0):+d}"
    return kind or "?"


def macro_duration(macro: dict) -> float:
    events = macro.get("events") or []
    return float(events[-1].get("t", 0.0)) if events else 0.0


# --------------------------------------------------------------------------- #
# Recorder
# --------------------------------------------------------------------------- #


class MacroRecorder(QObject):
    """Captures global keyboard/mouse input until stopped."""

    changed = Signal(int)
    stopped = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.events: list[dict] = []
        self._t0 = 0.0
        self._kb: keyboard.Listener | None = None
        self._ms: mouse.Listener | None = None
        self._mods: set[str] = set()
        self._finished = False

    @property
    def recording(self) -> bool:
        return self._kb is not None

    def start(self) -> None:
        if self.recording:
            return
        self.events = []
        self._mods = set()
        self._finished = False
        self._t0 = time.perf_counter()
        self._kb = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._ms = mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll)
        self._kb.start()
        self._ms.start()

    def stop(self) -> list[dict]:
        return self._finish()

    def _finish(self) -> list[dict]:
        if self._finished:
            return self.events
        self._finished = True
        for listener in (self._kb, self._ms):
            if listener is not None:
                try:
                    listener.stop()
                except Exception:  # noqa: BLE001 - stopping must never raise
                    pass
        self._kb = None
        self._ms = None
        self.stopped.emit()
        return self.events

    # -- listeners ---------------------------------------------------- #

    def _stamp(self) -> float:
        return round(time.perf_counter() - self._t0, 3)

    def _add(self, event: dict) -> None:
        if len(self.events) >= MAX_EVENTS:
            threading.Thread(target=self._finish, daemon=True).start()
            return
        event["t"] = self._stamp()
        self.events.append(event)
        self.changed.emit(len(self.events))

    def _is_stop_combo(self, key) -> bool:
        name = getattr(key, "name", None) or getattr(key, "char", None)
        if name not in ("m", "M"):
            return False
        return bool({"ctrl", "ctrl_l", "ctrl_r"} & self._mods) and bool(
            {"alt", "alt_l", "alt_r", "alt_gr"} & self._mods
        )

    def _on_press(self, key) -> None:
        name = getattr(key, "name", None)
        if self._is_stop_combo(key):
            threading.Thread(target=self._finish, daemon=True).start()
            return
        if name in MODIFIER_NAMES:
            self._mods.add(name)
        event = key_to_event(key, True)
        if event:
            self._add(event)

    def _on_release(self, key) -> None:
        name = getattr(key, "name", None)
        if name in MODIFIER_NAMES:
            self._mods.discard(name)
        if self._is_stop_combo(key):
            return
        event = key_to_event(key, False)
        if event:
            self._add(event)

    def _on_click(self, x, y, button, pressed) -> None:
        self._add({
            "kind": "mouse",
            "x": int(x),
            "y": int(y),
            "button": getattr(button, "name", "left"),
            "down": bool(pressed),
        })

    def _on_scroll(self, x, y, dx, dy) -> None:
        self._add({
            "kind": "scroll",
            "x": int(x),
            "y": int(y),
            "dx": int(dx),
            "dy": int(dy),
        })


# --------------------------------------------------------------------------- #
# Player
# --------------------------------------------------------------------------- #


class MacroPlayer:
    """Replays a macro on a background thread, interruptibly."""

    def __init__(self, controller_factory=None) -> None:
        self._factory = controller_factory or (lambda: (keyboard.Controller(), mouse.Controller()))
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def play(self, macro: dict, speed: float = 1.0) -> bool:
        if self.playing:
            return False
        events = macro.get("events") or []
        if not events:
            return False
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, args=(events, max(0.1, float(speed))), daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def wait(self, timeout: float | None = None) -> None:
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self, events: list[dict], speed: float) -> None:
        keyboard_ctl, mouse_ctl = self._factory()
        start = time.perf_counter()
        scale = 1.0 / speed
        for event in events:
            target = start + float(event.get("t", 0.0)) * scale
            while True:
                remaining = target - time.perf_counter()
                if remaining <= 0:
                    break
                if self._stop.wait(min(remaining, 0.05)):
                    return
            self._dispatch(event, keyboard_ctl, mouse_ctl)

    @staticmethod
    def _dispatch(event: dict, keyboard_ctl, mouse_ctl) -> None:
        kind = event.get("kind")
        if kind == "key":
            key = event_to_key(event)
            if key is None:
                return
            if event.get("down"):
                keyboard_ctl.press(key)
            else:
                keyboard_ctl.release(key)
        elif kind == "mouse":
            mouse_ctl.position = (event.get("x", 0), event.get("y", 0))
            button = getattr(mouse.Button, event.get("button", "left"), mouse.Button.left)
            if event.get("down"):
                mouse_ctl.press(button)
            else:
                mouse_ctl.release(button)
        elif kind == "scroll":
            mouse_ctl.position = (event.get("x", 0), event.get("y", 0))
            mouse_ctl.scroll(event.get("dx", 0), event.get("dy", 0))


def new_macro(name: str, events: list[dict]) -> dict:
    return {
        "id": uuid.uuid4().hex[:10],
        "name": name.strip() or "Untitled macro",
        "events": events,
        "created": time.strftime("%Y-%m-%d %H:%M"),
    }
