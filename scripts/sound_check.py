"""Soundboard checks: routing decisions, decoding, and the voice mixer.

No real audio device is opened: routing uses a fake device list and the mixer is
constructed without a stream.

    python scripts/sound_check.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.soundboard import RATE, SoundBoard, _Mixer  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


class FakeDevices:
    def __init__(self, devices, hostapis):
        self._devices = devices
        self._hostapis = hostapis

    def devices(self):
        return self._devices

    def hostapis(self):
        return self._hostapis


def make_source(with_cable: bool = True) -> FakeDevices:
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}]
    devices = [
        {"name": "Speakers (Realtek)", "max_output_channels": 2,
         "max_input_channels": 0, "hostapi": 0, "default_samplerate": 48000},
    ]
    if with_cable:
        devices.append({"name": "CABLE Input (VB-Audio Virtual Cable)",
                        "max_output_channels": 2, "max_input_channels": 0,
                        "hostapi": 1, "default_samplerate": 48000})
    return FakeDevices(devices, hostapis)


def main() -> int:
    # ---- routing ------------------------------------------------------- #
    settings = Settings()
    board = SoundBoard(settings, source=make_source())
    check("cable detected", board.cable_device() == 1, str(board.cable_device()))

    settings.set("soundboard.mic_route", True)
    settings.set("soundboard.monitor", True)
    check("mic + monitor routes to both", board.targets() == [1, None], str(board.targets()))

    settings.set("soundboard.monitor", False)
    check("mic only routes to cable", board.targets() == [1], str(board.targets()))

    settings.set("soundboard.mic_route", False)
    settings.set("soundboard.monitor", True)
    check("monitor only routes to default", board.targets() == [None], str(board.targets()))

    nolink = SoundBoard(Settings(), source=make_source(with_cable=False))
    check("missing cable falls back to speakers", nolink.targets() == [None],
          str(nolink.targets()))

    # ---- decoding / resampling ----------------------------------------- #
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "blip.wav"
        tone = (0.2 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))).astype(np.float32)
        sf.write(path, np.column_stack([tone, tone]), 44100)

        data = board.decode(str(path))
        check("decode returns stereo", data is not None and data.shape[1] == 2, str(None if data is None else data.shape))
        check("resampled to engine rate", data is not None and abs(len(data) - RATE) <= 2,
              str(None if data is None else len(data)))
        cached = board.decode(str(path))
        check("decode is cached", cached is data or (cached is not None and np.shares_memory(cached, data)))

        missing = SoundBoard(Settings(), source=make_source())
        check("missing file returns None", missing.decode(str(Path(tmp) / "nope.wav")) is None)

    # ---- mixer --------------------------------------------------------- #
    mixer = _Mixer(device=None, rate=RATE, channels=2, start=False)
    a = np.full((100, 2), 0.25, dtype=np.float32)
    b = np.full((100, 2), 0.10, dtype=np.float32)
    mixer.add(a, 1.0)
    mixer.add(b, 1.0)
    out = np.zeros((FRAMES_TEST := 64, 2), dtype=np.float32)
    mixer._callback(out, FRAMES_TEST, None, None)
    check("mixer sums concurrent voices", np.allclose(out, 0.35, atol=1e-6),
          f"peak={float(np.abs(out).max()):.3f}")
    check("voices still active after partial read", mixer.active == 2, str(mixer.active))

    out2 = np.zeros((64, 2), dtype=np.float32)
    mixer._callback(out2, 64, None, None)
    check("voices finish and are retired", mixer.active == 0, str(mixer.active))

    # ---- catalogue ------------------------------------------------------ #
    settings = Settings()
    settings.add_sound({"id": "abc123", "name": "Airhorn", "path": "x.wav", "volume": 1.0})
    from gr.config import available_actions  # noqa: E402

    actions = available_actions(settings)
    check("sound appears in action catalogue", "sound.play:abc123" in actions)
    check("sound label resolves", settings.action_label("sound.play:abc123") == "Sound: Airhorn",
          settings.action_label("sound.play:abc123"))

    settings.remove_sound("abc123")
    check("deleting a sound is clean", settings.sound("abc123") is None)

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
