"""Check whether a PE file's imported DLLs actually exist on this machine.

Missing non-API-set imports explain "service terminated unexpectedly" crashes
after a component was stripped from an image.

    python scripts/pe_deps.py C:\\Windows\\System32\\CapabilityAccessManager.dll
"""

from __future__ import annotations

import sys
from pathlib import Path

import pefile

SYSTEM32 = Path(r"C:\Windows\System32")
SYSWOW64 = Path(r"C:\Windows\SysWOW64")


def resolve(name: str) -> Path | None:
    for base in (SYSTEM32, SYSWOW64):
        candidate = base / name
        if candidate.exists():
            return candidate
    return None


def check(path: Path) -> int:
    try:
        pe = pefile.PE(str(path), fast_load=True)
        pe.parse_data_directories(
            directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"],
                         pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT"]]
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  could not parse: {exc}")
        return 0

    names: list[str] = []
    for attr in ("DIRECTORY_ENTRY_IMPORT", "DIRECTORY_ENTRY_DELAY_IMPORT"):
        for entry in getattr(pe, attr, []) or []:
            names.append(entry.dll.decode("ascii", "replace"))

    missing = []
    for name in sorted(set(names)):
        if name.lower().startswith(("api-ms-win", "ext-ms-win")):
            continue
        if resolve(name) is None:
            missing.append(name)

    print(f"{path.name}")
    print(f"  imports: {len(set(names))} dlls")
    if missing:
        print("  MISSING:")
        for name in missing:
            print(f"    - {name}")
    else:
        print("  all non-apiset imports resolve")
    pe.close()
    return len(missing)


def main(argv: list[str]) -> int:
    targets = [Path(a) for a in argv[1:]]
    if not targets:
        targets = [
            SYSTEM32 / "CapabilityAccessManager.dll",
            SYSTEM32 / "CapabilityAccessManager.Desktop.Storage.dll",
            SYSTEM32 / "CapabilityAccessManager.Desktop.Identity.dll",
            SYSTEM32 / "CapabilityAccessManagerClient.dll",
        ]
    total = 0
    for path in targets:
        if not path.exists():
            print(f"{path.name}: NOT PRESENT")
            continue
        total += check(path)
        print()
    print(f"TOTAL MISSING IMPORTS: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
