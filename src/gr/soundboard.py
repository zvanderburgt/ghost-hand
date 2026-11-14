"""Soundboard: layered playback with optional virtual-cable (mic) routing.

Routing model mirrors how Discord/Zoom expect it:

    speakers path : desktop audio  -> default output device
    mic path      : this app       -> "CABLE Input"  (VB-Audio virtual cable)
                                     apps pick "CABLE Output" as their microphone

Both paths can run at once, so you hear it and the call hears it.
"""

from __future__ import annotations

import os
import threading
from typing import Callable

import numpy as np
import sounddevice as sd
import soundfile as sf

RATE = 48000
CHANNELS = 2
FRAMES = 1024


def _resample(data: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out or len(data) == 0:
        return data
    n_out = max(1, int(round(len(data) * sr_out / sr_in)))
    idx = np.linspace(0.0, len(data) - 1, n_out)
    lo = np.floor(idx).astype(np.int64)
    hi = np.minimum(lo + 1, len(data) - 1)
    frac = (idx - lo)[:, None].astype(np.float32)
    return (data[lo] * (1.0 - frac) + data[hi] * frac).astype(np.float32)


class DeviceSource:
    """Indirection so routing decisions can be tested without audio hardware."""

    def devices(self):
        return sd.query_devices()

    def hostapis(self):
        return sd.query_hostapis()


class _Mixer:
    """One output stream that mixes several short sounds concurrently."""

    def __init__(self, device, rate: int, channels: int, max_voices: int = 8,
                 start: bool = True) -> None:
        self.device = device
        self.rate = rate
        self.channels = max(1, channels)
        self.max_voices = max(1, max_voices)
        self._voices: list[list] = []
        self._lock = threading.Lock()
        self.stream = None
        if start:
            self.stream = sd.OutputStream(
                samplerate=rate,
                channels=self.channels,
                device=device,
                blocksize=FRAMES,
                callback=self._callback,
            )
            self.stream.start()

    def add(self, data: np.ndarray, volume: float) -> None:
        if data.shape[1] != self.channels:
            if data.shape[1] > self.channels:
                data = data[:, : self.channels]
            else:
                data = np.repeat(data, self.channels, axis=1)[:, : self.channels]
        with self._lock:
            self._voices.append([data, 0, float(volume)])
            while len(self._voices) > self.max_voices:
                self._voices.pop(0)

    @property
    def active(self) -> int:
        return len(self._voices)

    def _callback(self, outdata, frames, time_info, status) -> None:  # noqa: ARG002
        outdata.fill(0.0)
        finished = []
        with self._lock:
            for voice in self._voices:
                buf, pos, volume = voice
                remaining = len(buf) - pos
                if remaining <= 0:
                    finished.append(voice)
                    continue
                n = min(frames, remaining)
                outdata[:n] += buf[pos:pos + n] * volume
                voice[1] = pos + n
                if voice[1] >= len(buf):
                    finished.append(voice)
            for voice in finished:
                if voice in self._voices:
                    self._voices.remove(voice)

    def close(self) -> None:
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:  # noqa: BLE001 - never raise on teardown
                pass
            self.stream = None


class SoundBoard:
    def __init__(self, settings, log: Callable[[str], None] | None = None,
                 source: DeviceSource | None = None) -> None:
        self.s = settings
        self.log = log or (lambda _m: None)
        self.source = source or DeviceSource()
        self._mixers: dict[int | None, _Mixer] = {}
        self._cache: dict[tuple[str, float], np.ndarray] = {}

    # -- device routing -------------------------------------------------- #

    def _is_wasapi(self, index: int, devices, hostapis) -> bool:
        try:
            api = int(devices[index]["hostapi"])
            return "wasapi" in str(hostapis[api].get("name", "")).lower()
        except (IndexError, KeyError, TypeError):
            return False

    def find_output(self, hint: str) -> int | None:
        """Best output device whose name contains `hint` (WASAPI preferred)."""
        if not hint:
            return None
        devices = self.source.devices()
        hostapis = self.source.hostapis()
        matches = [
            i for i, d in enumerate(devices)
            if d.get("max_output_channels", 0) > 0 and hint.lower() in str(d.get("name", "")).lower()
        ]
        if not matches:
            return None
        wasapi = [i for i in matches if self._is_wasapi(i, devices, hostapis)]
        return (wasapi or matches)[0]

    def cable_device(self) -> int | None:
        hint = str(self.s.get("soundboard.cable_device", "") or "cable input")
        return self.find_output(hint)

    def targets(self) -> list[int | None]:
        """Output devices to feed. None means the system default."""
        mic_route = bool(self.s.get("soundboard.mic_route", True))
        monitor = bool(self.s.get("soundboard.monitor", True))

        out: list[int | None] = []
        if mic_route:
            cable = self.cable_device()
            if cable is not None:
                out.append(cable)
            else:
                self.log("No virtual cable output found (is VB-Audio Cable installed?)")

        if monitor or not out:
            override = str(self.s.get("soundboard.output_device", "") or "")
            local = self.find_output(override) if override else None
            if local not in out:
                out.append(local)
        return out

    # -- playback -------------------------------------------------------- #

    def decode(self, path: str) -> np.ndarray | None:
        try:
            stamp = os.stat(path).st_mtime
        except OSError:
            return None
        key = (path, stamp)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        try:
            data, rate = sf.read(path, dtype="float32", always_2d=True)
        except Exception as exc:  # noqa: BLE001 - bad file should not crash the app
            self.log(f"Could not decode {os.path.basename(path)}: {exc}")
            return None
        if data.size == 0:
            return None
        if data.shape[1] == 1:
            data = np.repeat(data, 2, axis=1)
        elif data.shape[1] > 2:
            data = data[:, :2]
        data = _resample(data, int(rate), RATE)
        self._cache[key] = data
        return data

    def _mixer(self, device: int | None) -> _Mixer | None:
        existing = self._mixers.get(device)
        if existing is not None:
            return existing
        try:
            info = sd.query_devices(device, "output")
        except Exception:  # noqa: BLE001
            info = {"default_samplerate": RATE, "max_output_channels": 2}
        rate = int(info.get("default_samplerate") or RATE)
        channels = min(CHANNELS, max(1, int(info.get("max_output_channels") or CHANNELS)))
        try:
            mixer = _Mixer(device, rate, channels,
                           max_voices=int(self.s.get("soundboard.max_voices", 8)))
        except Exception as exc:  # noqa: BLE001
            self.log(f"Could not open audio device {device}: {exc}")
            return None
        self._mixers[device] = mixer
        return mixer

    def play(self, sound: dict) -> bool:
        path = sound.get("path", "")
        data = self.decode(path)
        if data is None:
            return False
        volume = float(sound.get("volume", 1.0)) * float(self.s.get("soundboard.volume", 0.8))
        devices = self.targets()
        played = False
        for device in devices:
            mixer = self._mixer(device)
            if mixer is None:
                continue
            mixer.add(_resample(data, RATE, mixer.rate), volume)
            played = True
        return played

    def stop_all(self) -> None:
        for mixer in self._mixers.values():
            with mixer._lock:  # noqa: SLF001 - internal by design
                mixer._voices.clear()

    def close(self) -> None:
        for mixer in self._mixers.values():
            mixer.close()
        self._mixers.clear()
