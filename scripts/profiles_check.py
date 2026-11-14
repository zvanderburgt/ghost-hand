"""Per-app profile checks.

    python scripts/profiles_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.profiles import match_rule, profile_for, rule_tokens  # noqa: E402

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


def main() -> int:
    # ---- rules ---------------------------------------------------------- #
    check("rule splits on commas", rule_tokens("spotify.exe, vlc.exe") == ["spotify.exe", "vlc.exe"],
          str(rule_tokens("spotify.exe, vlc.exe")))
    check("rule accepts semicolons too", rule_tokens("a;b|c") == ["a", "b", "c"],
          str(rule_tokens("a;b|c")))
    check("substring match is case-insensitive", match_rule("Spotify", "spotify.exe"))
    check("non-matching app does not match", not match_rule("spotify", "chrome.exe"))
    check("empty rule never matches", not match_rule("", "spotify.exe"))

    profiles = [
        {"id": "media", "match": "spotify.exe, vlc.exe"},
        {"id": "code", "match": "code.exe"},
    ]
    check("first matching profile wins", profile_for(profiles, "vlc.exe") == "media")
    check("unmatched app falls back to default", profile_for(profiles, "explorer.exe") == "default")
    check("empty profile list is default", profile_for([], "spotify.exe") == "default")

    # ---- binding resolution --------------------------------------------- #
    settings = Settings()
    base_peace = settings.binding_for("peace")
    profile = settings.add_profile("Media", "spotify.exe")
    settings.set_binding("peace", "system.show_desktop", profile_id=profile["id"])

    check("profile binding is stored separately",
          settings.binding_for("peace", profile["id"]) == "system.show_desktop",
          str(settings.binding_for("peace", profile["id"])))
    check("default binding untouched", settings.binding_for("peace") == base_peace,
          str(settings.binding_for("peace")))

    settings.active_profile = profile["id"]
    check("active profile overrides", settings.binding_for("peace") == "system.show_desktop")
    check("unset gestures fall back to default",
          settings.binding_for("point_up") == settings.binding_for("point_up", "default"),
          f"{settings.binding_for('point_up')} vs {settings.binding_for('point_up', 'default')}")

    settings.set_binding("fist", "system.copy", profile_id=profile["id"])
    check("new profile binding resolves while active", settings.binding_for("fist") == "system.copy")

    settings.active_profile = "default"
    check("switching back restores defaults", settings.binding_for("peace") == base_peace)

    # ---- lifecycle ------------------------------------------------------- #
    settings.active_profile = profile["id"]
    settings.remove_profile(profile["id"])
    check("deleting a profile clears it as active", settings.active_profile == "default")
    check("deleted profile is gone", settings.profile_by_id(profile["id"]) is None)
    check("bindings still resolve after deletion", settings.binding_for("peace") == base_peace)

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
