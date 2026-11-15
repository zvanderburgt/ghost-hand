"""Version parsing and update-check behaviour (no network).

    python scripts/updater_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.updater import check, is_newer, latest_release, parse_version  # noqa: E402

results: list[tuple[str, bool, str]] = []


def ok(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


def payload(tag: str, url: str = "https://example.invalid/rel") -> bytes:
    return json.dumps({"tag_name": tag, "html_url": url, "name": tag}).encode()


def main() -> int:
    # ---- parsing --------------------------------------------------------- #
    ok("plain semver", parse_version("0.6.0") == (0, 6, 0), str(parse_version("0.6.0")))
    ok("tag prefix stripped", parse_version("v0.7.1") == (0, 7, 1), str(parse_version("v0.7.1")))
    ok("short version padded", parse_version("1.2") == (1, 2), str(parse_version("1.2")))
    ok("garbage is zero", parse_version("nightly") == (0,), str(parse_version("nightly")))

    # ---- comparison ------------------------------------------------------ #
    ok("newer patch detected", is_newer("v0.6.1", "0.6.0"))
    ok("same version is not newer", not is_newer("0.6.0", "0.6.0"))
    ok("older is not newer", not is_newer("0.5.9", "0.6.0"))
    ok("numeric not lexical", is_newer("0.10.0", "0.9.9"), "0.10.0 vs 0.9.9")
    ok("shorter candidate", is_newer("0.6.1", "0.6"), "0.6.1 vs 0.6")

    # ---- release parsing ------------------------------------------------- #
    release = latest_release(fetch=lambda url, timeout: payload("v9.9.9"))
    ok("release parsed", release is not None and release.version == "v9.9.9",
       str(release))
    ok("release url carried", release is not None and release.url.endswith("/rel"),
       str(release))

    ok("bad json yields none",
       latest_release(fetch=lambda url, timeout: b"not json") is None)
    ok("missing tag yields none",
       latest_release(fetch=lambda url, timeout: json.dumps({}).encode()) is None)
    ok("network error yields none",
       latest_release(fetch=lambda url, timeout: (_ for _ in ()).throw(OSError("offline"))) is None)

    # ---- check() --------------------------------------------------------- #
    offered = check("0.6.0", fetch=lambda url, timeout: payload("v0.7.0"))
    ok("newer release offered", offered is not None and offered.version == "v0.7.0", str(offered))
    ok("current release not offered",
       check("0.6.0", fetch=lambda url, timeout: payload("v0.6.0")) is None)
    ok("offline is silent",
       check("0.6.0", fetch=lambda url, timeout: (_ for _ in ()).throw(OSError())) is None)

    failures = 0
    for name, condition, detail in results:
        print(f"  {'PASS' if condition else 'FAIL'}  {name}{'  ' + detail if detail and not condition else ''}")
        if not condition:
            failures += 1
    print()
    print("all checks pass" if not failures else f"{failures} FAILURE(S)")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
