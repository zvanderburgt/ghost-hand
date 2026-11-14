"""Camera diagnostics: answers "why can't the app see my RealSense?".

    python scripts/doctor.py

Checks the things that actually cause 'Access is denied' on Windows:
privacy consent, PnP state, DirectShow registration, the Frame Server, and
whether any process has the device open.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

OK = "[ ok ]"
WARN = "[warn]"
FAIL = "[fail]"

CONSENT = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"


def _run(args: list[str]) -> str:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=25)
        return (out.stdout or "") + (out.stderr or "")
    except Exception as exc:  # noqa: BLE001
        return f"<error: {exc}>"


def check_librealsense() -> bool:
    try:
        import pyrealsense2 as rs
    except ImportError:
        print(f"{FAIL} pyrealsense2 is not installed in this interpreter")
        return False

    try:
        devices = list(rs.context().query_devices())
    except RuntimeError as exc:
        print(f"{FAIL} librealsense cannot enumerate devices: {exc}")
        print("       -> the camera stack is refusing access, see the hints at the end")
        return False

    if not devices:
        print(f"{FAIL} no RealSense devices found (check the USB cable / port)")
        return False

    for dev in devices:
        name = dev.get_info(rs.camera_info.name)
        serial = dev.get_info(rs.camera_info.serial_number)
        print(f"{OK} {name}  serial {serial}")
    return True


def check_consent() -> None:
    import winreg

    for hive, label in ((winreg.HKEY_LOCAL_MACHINE, "machine"),
                        (winreg.HKEY_CURRENT_USER, "user")):
        try:
            with winreg.OpenKey(hive, CONSENT) as key:
                value, _ = winreg.QueryValueEx(key, "Value")
        except OSError:
            value = "missing"
        marker = OK if value == "Allow" else FAIL
        print(f"{marker} camera consent ({label}): {value}")
        if value != "Allow":
            print("       -> Settings > Privacy & security > Camera > let desktop apps access")


def check_pnp() -> None:
    out = _run(["pnputil", "/enum-devices", "/class", "Camera"])
    cameras = [line.strip() for line in out.splitlines() if "RealSense" in line]
    if cameras:
        for line in cameras:
            print(f"{OK} PnP: {line}")
    else:
        print(f"{WARN} pnputil reported no RealSense camera-class devices")


def check_frame_server() -> None:
    out = _run(["sc", "query", "FrameServer"])
    state = "unknown"
    for line in out.splitlines():
        if "STATE" in line:
            state = line.split(":", 1)[-1].strip()
    print(f"{OK} FrameServer service: {state}")
    print("       -> if capture is denied, restart it from an elevated prompt:")
    print("          Restart-Service FrameServer")


def check_holder_processes() -> None:
    names = ["NVIDIA Broadcast", "obs64", "Discord", "Teams", "Zoom",
             "Intel.RealSense.Viewer", "WindowsCamera"]
    out = _run(["tasklist"])
    found = [n for n in names if n.lower() in out.lower()]
    if found:
        print(f"{WARN} possibly camera-related apps running: {', '.join(found)}")
    else:
        print(f"{OK} no common camera-holding apps running")


def main() -> int:
    print("RealSense gesture control - camera doctor\n")
    print(f"python: {sys.executable}\n")

    print("-- devices ------------------------------------------------------")
    lib_ok = check_librealsense()

    print("\n-- permissions --------------------------------------------------")
    check_consent()

    print("\n-- windows device state -----------------------------------------")
    check_pnp()
    check_frame_server()
    check_holder_processes()

    print("\n-- next steps ---------------------------------------------------")
    if lib_ok:
        print("Camera is reachable. Run:  python scripts/probe.py --frames 90 --save")
    else:
        print("1. Unplug the RealSense and plug it back in (prefer a rear USB 3 port).")
        print("2. Close NVIDIA Broadcast / OBS / Discord camera previews.")
        print("3. Restart the camera stack (elevated PowerShell):")
        print("     Restart-Service FrameServer")
        print("     pnputil /restart-device \"USB\\VID_8086&PID_0B07&MI_00\\6&6cdf577&0&0000\"")
        print("4. Reboot if it still fails - that clears a wedged UVC/FrameServer claim.")
    return 0 if lib_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
