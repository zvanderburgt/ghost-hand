"""Camera + microphone access check (used by the repair scripts).

    python scripts/check_av.py
"""

from __future__ import annotations

import sys


def camera() -> bool:
    try:
        import pyrealsense2 as rs
    except ImportError:
        print("camera: pyrealsense2 not installed")
        return False
    try:
        devices = list(rs.context().query_devices())
    except Exception as exc:  # noqa: BLE001
        print(f"camera error: {exc}")
        return False
    print(f"camera devices: {len(devices)}")
    for dev in devices:
        print(f"   {dev.get_info(rs.camera_info.name)}")
    return len(devices) > 0


def microphone() -> bool:
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError:
        print("mic: sounddevice not installed")
        return False
    try:
        apis = sd.query_hostapis()
        wasapi = next((a for a in apis if a["name"] == "Windows WASAPI"), None)
        device = wasapi["default_input_device"] if wasapi else -1
        if device is None or device < 0:
            print("mic: no default WASAPI input device")
            return False
        info = sd.query_devices(device)
        rate = int(info["default_samplerate"])
        rec = sd.rec(int(0.2 * rate), samplerate=rate, channels=1,
                     device=device, blocking=True, dtype="float32")
        peak = float(np.abs(rec).max())
        print(f"mic ok: {info['name']} peak={peak:.4f}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"mic error: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    cam_ok = camera()
    mic_ok = microphone()
    print(f"RESULT camera={'ok' if cam_ok else 'fail'} mic={'ok' if mic_ok else 'fail'}")
    return 0 if cam_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
