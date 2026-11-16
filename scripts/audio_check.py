"""Per-application volume checks.

No real audio device is touched unless ``--live`` is passed. The normal run uses
fake sessions, so it is safe in CI and on machines without Spotify.

    python scripts/audio_check.py
    python scripts/audio_check.py --live    # nudges the running Spotify by 1%
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.actions import ActionBus  # noqa: E402
from gr.app_audio import AppAudio, AppAudioError, _Session, dial_target  # noqa: E402
from gr.config import Settings, app_name  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


class FakeVolume:
    def __init__(self, volume: float = 1.0, muted: bool = False) -> None:
        self.volume = volume
        self.muted = muted
        self.writes = 0

    def GetMasterVolume(self) -> float:
        return self.volume

    def SetMasterVolume(self, value: float, _context) -> None:
        self.volume = max(0.0, min(1.0, float(value)))
        self.writes += 1

    def GetMute(self) -> bool:
        return self.muted

    def SetMute(self, muted: bool, _context) -> None:
        self.muted = bool(muted)
        self.writes += 1


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_audio(sessions, clock: Clock | None = None) -> AppAudio:
    return AppAudio(enumerate_sessions=lambda: sessions, clock=clock or Clock())


def test_catalogue() -> None:
    settings = Settings()
    check(
        "app label names the process",
        settings.action_label("audio.app_up", "spotify.exe") == "Spotify — App Volume Up",
        settings.action_label("audio.app_up", "spotify.exe"),
    )
    check(
        "app label warns when no app is set",
        settings.action_label("audio.app_up") == "App Volume Up (no app)",
        settings.action_label("audio.app_up"),
    )
    check("multi-process label", app_name("spotify.exe, vlc.exe") == "Spotify +1",
          app_name("spotify.exe, vlc.exe"))


def test_routing() -> None:
    check("system route stays system", dial_target("system") is None)
    check("empty route stays system", dial_target("") is None)
    check("foreground route uses the focused app",
          dial_target("foreground", "chrome.exe") == "chrome.exe",
          str(dial_target("foreground", "chrome.exe")))
    check("foreground without a window falls back",
          dial_target("foreground", "") is None)
    check("named route passes through",
          dial_target("spotify.exe", "chrome.exe") == "spotify.exe")


def test_sessions() -> None:
    spotify_a = FakeVolume(0.80)
    spotify_b = FakeVolume(0.60)
    chrome_a = FakeVolume(0.50)
    chrome_b = FakeVolume(0.40)
    sessions = [
        _Session("Spotify.exe", 100, spotify_a),
        _Session("Spotify.exe", 101, spotify_b),
        _Session("chrome.exe", 200, chrome_a),
        _Session("chrome.exe", 201, chrome_b),
    ]
    audio = make_audio(sessions)

    apps = audio.apps()
    check("apps are grouped by process", len(apps) == 2, str(len(apps)))
    check("multiple sessions are counted",
          next(a for a in apps if a.process.lower() == "spotify.exe").sessions == 2)
    check("case-insensitive lookup", audio.get_volume("SPOTIFY.EXE") == 0.80,
          str(audio.get_volume("SPOTIFY.EXE")))
    check("substring lookup", audio.get_volume("spotify") == 0.80)

    try:
        audio.get_volume("not-running.exe")
        missing = False
    except AppAudioError:
        missing = True
    check("missing app raises", missing)

    audio.adjust("spotify.exe", 0.05)
    check("adjust moves every session for the app",
          abs(spotify_a.volume - 0.85) < 1e-9 and abs(spotify_b.volume - 0.65) < 1e-9,
          f"{spotify_a.volume:.2f}/{spotify_b.volume:.2f}")

    audio.adjust("spotify.exe", 2.0)
    check("upper clamp", abs(spotify_a.volume - 1.0) < 1e-9, str(spotify_a.volume))
    audio.adjust("chrome.exe", -2.0)
    check("lower clamp", abs(chrome_a.volume) < 1e-9, str(chrome_a.volume))

    audio.set_volume("chrome.exe", 0.25)
    check("set applies to every session",
          abs(chrome_a.volume - 0.25) < 1e-9 and abs(chrome_b.volume - 0.25) < 1e-9,
          f"{chrome_a.volume:.2f}/{chrome_b.volume:.2f}")

    muted = audio.toggle_mute("spotify.exe")
    check("toggle mutes all sessions",
          muted and spotify_a.muted and spotify_b.muted)
    muted = audio.toggle_mute("spotify.exe")
    check("toggle unmutes all sessions",
          not muted and not spotify_a.muted and not spotify_b.muted)

    audio.set_mute("chrome.exe", True)
    check("set_mute applies to every session", chrome_a.muted and chrome_b.muted)


def test_cache_and_retry() -> None:
    clock = Clock()
    calls = {"n": 0}
    dead = FakeVolume(0.5)
    good = FakeVolume(0.5)
    dead.SetMasterVolume = lambda value, context: (_ for _ in ()).throw(
        RuntimeError("session gone")
    )

    def enum():
        calls["n"] += 1
        return [_Session("Spotify.exe", 1, dead if calls["n"] == 1 else good)]

    audio = AppAudio(enumerate_sessions=enum, clock=clock)
    audio.apps()
    audio.apps()
    check("sessions are cached", calls["n"] == 1, str(calls["n"]))
    clock.now = 1.1
    audio.apps()
    check("cache expires", calls["n"] == 2, str(calls["n"]))
    audio.refresh()
    audio.apps()
    check("refresh forces re-enumeration", calls["n"] == 3, str(calls["n"]))

    clock.now = 3.0
    calls["n"] = 0
    now = audio.adjust("spotify.exe", 0.10)
    check("a dead session is refreshed and retried",
          abs(now - 0.6) < 1e-9 and calls["n"] == 2,
          f"vol={now:.2f} calls={calls['n']}")


def test_action_bus() -> None:
    settings = Settings()
    settings.set("safety.practice_mode", False)
    settings.set("engine.app_volume_step", 2)
    volume = FakeVolume(0.50)
    audio = make_audio([_Session("Spotify.exe", 1, volume)])
    bus = ActionBus(settings, app_audio=audio)

    result = bus.fire("audio.app_up", "spotify.exe", repeat=3)
    check("batched app tick is one 6% write",
          result.ok and abs(volume.volume - 0.56) < 1e-9,
          f"{volume.volume:.2f}")
    check("batch is reported", "×3" in result.message, result.message)

    bus.fire("audio.app_down", "spotify.exe", repeat=1)
    check("app volume down", abs(volume.volume - 0.54) < 1e-9,
          f"{volume.volume:.2f}")

    row = bus.fire("audio.app_mute", "spotify.exe")
    check("mute action toggles", row.ok and volume.muted)

    before = volume.volume
    settings.set("safety.practice_mode", True)
    practice = bus.fire("audio.app_up", "spotify.exe", repeat=2)
    check("practice mode changes nothing",
          practice.ok and abs(volume.volume - before) < 1e-9,
          practice.message)


def live() -> int:
    print("Live Spotify check (1% nudge, restored afterwards)")
    audio = AppAudio()
    apps = audio.apps()
    spotify = next(
        (app for app in apps if app.process.lower() == "spotify.exe"), None
    )
    if spotify is None:
        print("  SKIP  Spotify has no audio session — start a track and retry")
        return 0

    before = spotify.volume
    after = audio.adjust("spotify.exe", -0.01)
    audio.set_volume("spotify.exe", before)
    restored = audio.get_volume("spotify.exe")
    print(f"  Spotify volume {before:.2f} -> {after:.2f} -> {restored:.2f}")
    ok = abs(after - (before - 0.01)) < 0.02 and abs(restored - before) < 0.02
    print("  PASS" if ok else "  FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="touch the running Spotify session (1% nudge + restore)")
    args = ap.parse_args()

    test_catalogue()
    test_routing()
    test_sessions()
    test_cache_and_retry()
    test_action_bus()

    failures = 0
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  ' + detail if detail and not ok else ''}")
        if not ok:
            failures += 1

    if args.live:
        failures += live()

    print()
    print("all checks pass" if not failures else f"{failures} FAILURE(S)")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
