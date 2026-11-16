"""Per-application volume through Windows audio sessions.

Windows exposes each app's Volume Mixer slider as an ``ISimpleAudioVolume`` on
its WASAPI session. Media keys only move the master volume, so this is what lets
the dial and bindings target one app (Spotify, a game, a browser).

pycaw is imported lazily: a source checkout without it still starts, and the
app-volume actions fail with a readable message instead of taking down the app.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable

CACHE_SECONDS = 1.0
SYSTEM_TARGET = "system"
FOREGROUND_TARGET = "foreground"


class AppAudioError(RuntimeError):
    """App volume is unavailable or the chosen app has no audio session."""


@dataclass
class AudioApp:
    process: str
    pid: int
    volume: float
    muted: bool
    sessions: int = 1


@dataclass
class _Session:
    """One WASAPI session. ``volume`` is an ISimpleAudioVolume-like object."""

    process: str
    pid: int
    volume: object


def _clamp(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def _tokens(rule: str | None) -> list[str]:
    if not rule:
        return []
    cleaned = str(rule).replace(";", ",").replace("|", ",")
    return [token.strip().lower() for token in cleaned.split(",") if token.strip()]


def matches(rule: str | None, process: str) -> bool:
    """Case-insensitive substring match, same rules as profiles."""
    process = (process or "").lower()
    return bool(process and any(token in process for token in _tokens(rule)))


def dial_target(target: str | None, foreground: str = "") -> str | None:
    """Process the dial should control, or None for system volume.

    ``foreground`` is only consulted for the special "foreground" setting; an
    empty foreground falls back to the system so the dial never goes dead.
    """
    value = (target or SYSTEM_TARGET).strip()
    if value in ("", SYSTEM_TARGET):
        return None
    if value == FOREGROUND_TARGET:
        return (foreground or "").strip() or None
    return value


# COM is apartment-scoped. comtypes initialises the importing thread, so each
# new worker thread that touches sessions needs its own call.
_thread = threading.local()


def _ensure_com() -> None:
    if getattr(_thread, "ready", False):
        return
    import comtypes

    comtypes.CoInitialize()
    _thread.ready = True


def _enumerate_sessions() -> list[_Session]:
    """All live sessions on every active render endpoint.

    Watching every endpoint (not just the default one) matters when Spotify or a
    game is routed to a headset while Windows' default output is elsewhere.
    """
    _ensure_com()
    try:
        from pycaw.api.audiopolicy import IAudioSessionControl2
        from pycaw.constants import DEVICE_STATE, EDataFlow, AudioSessionState
        from pycaw.pycaw import AudioUtilities
        from pycaw.utils import AudioSession
    except ImportError as exc:  # pycaw pulls comtypes and psutil
        raise AppAudioError(
            "App volume needs pycaw. Run: pip install -r requirements.txt"
        ) from exc

    sessions: list[_Session] = []
    seen: set[str] = set()
    try:
        devices = AudioUtilities.GetAllDevices(
            data_flow=EDataFlow.eRender.value,
            device_state=DEVICE_STATE.ACTIVE.value,
        )
    except Exception as exc:  # noqa: BLE001 - COM errors are not uniform
        raise AppAudioError(f"Could not list audio outputs: {exc}") from exc

    for device in devices:
        try:
            manager = device.AudioSessionManager
            if manager is None:
                continue
            enumerator = manager.GetSessionEnumerator()
            for index in range(enumerator.GetCount()):
                try:
                    control = enumerator.GetSession(index)
                    if control is None:
                        continue
                    control2 = control.QueryInterface(IAudioSessionControl2)
                    if control2 is None:
                        continue
                    session = AudioSession(control2)
                    if session.State == AudioSessionState.Expired:
                        continue
                    process = session.Process
                    if process is None:
                        continue
                    name = process.name()
                    if not name:
                        continue
                    volume = session.SimpleAudioVolume
                    try:
                        ident = session.InstanceIdentifier
                    except Exception:  # noqa: BLE001 - fall back to object identity
                        ident = ""
                    key = ident or f"{name.lower()}:{session.ProcessId}:{id(volume)}"
                    if key in seen:
                        continue
                    seen.add(key)
                    sessions.append(_Session(name, int(session.ProcessId), volume))
                except Exception:  # noqa: BLE001 - one dead session must not hide the rest
                    continue
        except Exception:  # noqa: BLE001 - one bad endpoint must not hide the rest
            continue
    return sessions


class AppAudio:
    """Cached, thread-safe view of the current Windows audio sessions."""

    def __init__(
        self,
        enumerate_sessions: Callable[[], list[_Session]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._enumerate = enumerate_sessions or _enumerate_sessions
        self._clock = clock
        self._sessions: list[_Session] = []
        self._loaded_at = -CACHE_SECONDS
        self._lock = threading.Lock()

    # -- session cache ---------------------------------------------------- #

    def _refresh(self) -> None:
        try:
            sessions = self._enumerate()
        except AppAudioError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface as a friendly error
            raise AppAudioError(f"Could not read audio sessions: {exc}") from exc
        self._sessions = list(sessions)
        self._loaded_at = self._clock()

    def _cached(self) -> list[_Session]:
        with self._lock:
            if (self._clock() - self._loaded_at) >= CACHE_SECONDS:
                self._refresh()
            return list(self._sessions)

    def _invalidate(self) -> None:
        with self._lock:
            self._loaded_at = -CACHE_SECONDS

    def _find(self, process: str) -> list[_Session]:
        rule = (process or "").strip()
        if not rule:
            raise AppAudioError("No app chosen")
        found = [s for s in self._cached() if matches(rule, s.process)]
        if not found:
            raise AppAudioError(f"{process} is not playing audio on this PC")
        return found

    def _retry(self, process: str) -> list[_Session]:
        """Sessions that died between the cache read and the write."""
        self._invalidate()
        return self._find(process)

    @staticmethod
    def _apply(sessions: list[_Session], action: Callable[[object], None]) -> int:
        applied = 0
        for session in sessions:
            try:
                action(session.volume)
                applied += 1
            except Exception:  # noqa: BLE001 - skip sessions that just exited
                continue
        return applied

    # -- public API ------------------------------------------------------- #

    @staticmethod
    def available() -> bool:
        try:
            _ensure_com()
            from pycaw.pycaw import AudioUtilities  # noqa: F401
            return True
        except Exception:  # noqa: BLE001 - missing dependency or broken COM
            return False

    def apps(self) -> list[AudioApp]:
        """One row per process with an audio session, sorted by name."""
        grouped: dict[str, list[_Session]] = {}
        for session in self._cached():
            grouped.setdefault(session.process.lower(), []).append(session)

        apps: list[AudioApp] = []
        for group in grouped.values():
            for first in group:
                try:
                    volume = _clamp(float(first.volume.GetMasterVolume()))
                    muted = bool(first.volume.GetMute())
                except Exception:  # noqa: BLE001 - try another session for the app
                    continue
                apps.append(AudioApp(
                    process=first.process,
                    pid=first.pid,
                    volume=volume,
                    muted=muted,
                    sessions=len(group),
                ))
                break
        return sorted(apps, key=lambda app: app.process.lower())

    def get_volume(self, process: str) -> float:
        for session in self._find(process):
            try:
                return _clamp(float(session.volume.GetMasterVolume()))
            except Exception:  # noqa: BLE001
                continue
        for session in self._retry(process):
            try:
                return _clamp(float(session.volume.GetMasterVolume()))
            except Exception:  # noqa: BLE001
                continue
        raise AppAudioError(f"{process} has no readable audio session")

    def set_volume(self, process: str, volume: float) -> float:
        target = _clamp(float(volume))

        def apply(volume_control) -> None:
            volume_control.SetMasterVolume(target, None)

        applied = self._apply(self._find(process), apply)
        if not applied:
            applied = self._apply(self._retry(process), apply)
        if not applied:
            raise AppAudioError(f"{process} has no writable audio session")
        return target

    def adjust(self, process: str, delta: float) -> float:
        delta = float(delta)
        sessions = self._find(process)
        newest = self._adjust_sessions(sessions, delta)
        if newest is None:
            newest = self._adjust_sessions(self._retry(process), delta)
        if newest is None:
            raise AppAudioError(f"{process} has no writable audio session")
        return newest

    @staticmethod
    def _adjust_sessions(sessions: list[_Session], delta: float) -> float | None:
        newest = None
        for session in sessions:
            try:
                current = float(session.volume.GetMasterVolume())
                target = _clamp(current + delta)
                session.volume.SetMasterVolume(target, None)
                newest = target
            except Exception:  # noqa: BLE001 - skip sessions that just exited
                continue
        return newest

    def set_mute(self, process: str, muted: bool) -> bool:
        def apply(volume_control) -> None:
            volume_control.SetMute(bool(muted), None)

        applied = self._apply(self._find(process), apply)
        if not applied:
            applied = self._apply(self._retry(process), apply)
        if not applied:
            raise AppAudioError(f"{process} has no writable audio session")
        return bool(muted)

    def toggle_mute(self, process: str) -> bool:
        sessions = self._find(process)
        target = self._mute_target(sessions)
        if target is not None and self._apply(
            sessions, lambda volume: volume.SetMute(target, None)
        ):
            return target

        sessions = self._retry(process)
        target = self._mute_target(sessions)
        if target is None or not self._apply(
            sessions, lambda volume: volume.SetMute(target, None)
        ):
            raise AppAudioError(f"{process} has no writable audio session")
        return target

    @staticmethod
    def _mute_target(sessions: list[_Session]) -> bool | None:
        for session in sessions:
            try:
                return not bool(session.volume.GetMute())
            except Exception:  # noqa: BLE001
                continue
        return None

    def refresh(self) -> None:
        """Drop the cached session list so the next read sees new apps."""
        self._invalidate()

    def close(self) -> None:
        self._invalidate()
