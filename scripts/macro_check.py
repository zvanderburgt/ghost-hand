"""Macro subsystem checks: catalogue, serialisation, playback, cancellation.

    python scripts/macro_check.py

Playback is exercised against fake controllers so no real input is sent.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pynput import keyboard  # noqa: E402

from gr.config import Settings, available_actions  # noqa: E402
from gr.macros import (MacroPlayer, event_to_key, key_to_event,  # noqa: E402
                       macro_duration, new_macro)

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


class FakeKeyboard:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def press(self, key) -> None:
        self.calls.append(("press", key))

    def release(self, key) -> None:
        self.calls.append(("release", key))


class FakeMouse:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.position = (0, 0)

    def press(self, button) -> None:
        self.calls.append(("press", getattr(button, "name", button)))

    def release(self, button) -> None:
        self.calls.append(("release", getattr(button, "name", button)))

    def scroll(self, dx, dy) -> None:
        self.calls.append(("scroll", dx, dy))


def main() -> int:
    # ---- catalogue ---------------------------------------------------- #
    settings = Settings()
    macro = new_macro("Demo", [
        {"t": 0.0, "kind": "key", "char": "a", "down": True},
        {"t": 0.2, "kind": "key", "char": "a", "down": False},
    ])
    settings.add_macro(macro)

    actions = available_actions(settings)
    action_id = f"macro.play:{macro['id']}"
    check("macro appears in action catalogue", action_id in actions, str(list(actions)[-1]))
    check("macro label resolves", settings.action_label(action_id) == "Play: Demo",
          settings.action_label(action_id))
    check("macro duration computed", abs(macro_duration(macro) - 0.2) < 1e-6,
          f"{macro_duration(macro)}")

    # ---- persistence --------------------------------------------------- #
    tmp = ROOT / "debug" / "macro-test-settings.json"
    settings.save(tmp)
    reloaded = Settings.load(tmp)
    check("macro survives a save/load round trip",
          reloaded.macro(macro["id"]) is not None)
    check("binding label survives reload",
          reloaded.action_label(action_id) == "Play: Demo")
    tmp.unlink(missing_ok=True)

    # ---- key serialisation --------------------------------------------- #
    event = key_to_event(keyboard.Key.ctrl, True)
    check("special key round trip", event_to_key(event) is keyboard.Key.ctrl, str(event))
    event = key_to_event(keyboard.KeyCode.from_char("q"), True)
    check("character key round trip", event_to_key(event) == "q", str(event))

    # ---- playback ------------------------------------------------------- #
    fake_kb, fake_mouse = FakeKeyboard(), FakeMouse()
    player = MacroPlayer(controller_factory=lambda: (fake_kb, fake_mouse))
    script = {"events": [
        {"t": 0.00, "kind": "key", "char": "a", "down": True},
        {"t": 0.03, "kind": "key", "char": "a", "down": False},
        {"t": 0.06, "kind": "mouse", "x": 10, "y": 20, "button": "left", "down": True},
        {"t": 0.09, "kind": "mouse", "x": 10, "y": 20, "button": "left", "down": False},
        {"t": 0.12, "kind": "scroll", "x": 10, "y": 20, "dx": 0, "dy": -1},
    ]}
    started = time.perf_counter()
    played = player.play(script, speed=4.0)
    player.wait(3.0)
    elapsed = time.perf_counter() - started

    check("playback started", played)
    check("key events dispatched", fake_kb.calls == [("press", "a"), ("release", "a")],
          str(fake_kb.calls))
    check("mouse events dispatched", fake_mouse.calls[:2] == [("press", "left"), ("release", "left")],
          str(fake_mouse.calls))
    check("scroll dispatched", ("scroll", 0, -1) in fake_mouse.calls, str(fake_mouse.calls))
    check("speed multiplier shortened playback", elapsed < 0.5, f"{elapsed:.2f}s")

    # ---- cancellation ---------------------------------------------------- #
    long_kb = FakeKeyboard()
    canceller = MacroPlayer(controller_factory=lambda: (long_kb, FakeMouse()))
    long_script = {"events": [
        {"t": 0.0, "kind": "key", "char": "a", "down": True},
        {"t": 1.0, "kind": "key", "char": "a", "down": False},
    ]}
    canceller.play(long_script)
    time.sleep(0.1)
    canceller.stop()
    canceller.wait(1.5)
    check("stop cancels playback", not canceller.playing and long_kb.calls == [("press", "a")],
          str(long_kb.calls))

    # ---- report ---------------------------------------------------------- #
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
