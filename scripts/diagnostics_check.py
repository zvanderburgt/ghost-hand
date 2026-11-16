"""Binding conflict checks.

    python scripts/diagnostics_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.diagnostics import (ERROR, WARNING, check_bindings, check_chords,  # noqa: E402
                            check_custom_gestures, fix_duplicates, run_all)

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


def levels(issues) -> set[str]:
    return {issue.level for issue in issues}


def messages(issues, needle: str) -> bool:
    return any(needle.lower() in issue.message.lower() for issue in issues)


def main() -> int:
    # ---- clean state ---------------------------------------------------- #
    clean = Settings()
    check("default bindings are clean", run_all(clean) == [],
          str([i.message for i in run_all(clean)]))

    # ---- one gesture, two actions --------------------------------------- #
    dup = Settings()
    dup.bindings.append({"gesture": "peace", "action": "system.copy"})
    issues = check_bindings(dup)
    check("duplicate gesture with a different action is an error",
          ERROR in levels(issues) and messages(issues, "different actions"),
          str([i.message for i in issues]))
    check("duplicate gesture is reported once per gesture",
          sum(1 for i in issues if "V Sign" in i.message) == 1,
          str([i.message for i in issues]))

    # same action twice is only a warning
    same = Settings()
    same.bindings.append({"gesture": "peace", "action": "media.play_pause"})
    issues = check_bindings(same)
    check("identical duplicate is a warning", WARNING in levels(issues), str(issues))

    # ---- one action, two gestures --------------------------------------- #
    shared = Settings()
    shared.set_binding("fist", "media.play_pause")
    issues = check_bindings(shared)
    check("shared action is reported", messages(issues, "bound to 2 gestures"),
          str([i.message for i in issues]))

    # ---- dangling references -------------------------------------------- #
    dangling = Settings()
    dangling.set_binding("peace", "macro.play:gone")
    check("deleted macro is an error",
          messages(check_bindings(dangling), "deleted macro"))

    dangling.set_binding("peace", "sound.play:gone")
    check("deleted sound is an error",
          messages(check_bindings(dangling), "deleted sound"))

    missing_path = Settings()
    missing_path.set_binding("peace", "app.launch")
    check("app launch without a path warns",
          messages(check_bindings(missing_path), "no path is set"))

    missing_app = Settings()
    missing_app.set_binding("peace", "audio.app_up")
    check("app volume without an app warns",
          messages(check_bindings(missing_app), "no app is set"))

    two_apps = Settings()
    two_apps.set_binding("peace", "audio.app_up", "spotify.exe")
    two_apps.set_binding("fist", "audio.app_up", "chrome.exe")
    check("different app targets are separate actions",
          not messages(check_bindings(two_apps), "bound to 2 gestures"),
          str([i.message for i in check_bindings(two_apps)]))

    # ---- arming pose ---------------------------------------------------- #
    armed = Settings()
    armed.set_binding(armed.get("engine.arm_pose"), "media.play_pause")
    check("binding the arming pose warns",
          messages(check_bindings(armed), "arming pose"))

    # ---- profiles -------------------------------------------------------- #
    prof = Settings()
    profile = prof.add_profile("Media", "spotify.exe")
    prof.set_binding("peace", "system.show_desktop", profile_id=profile["id"])
    prof.set_binding("fist", "system.copy", profile_id=profile["id"])
    prof.set_binding("fist", "system.paste", profile_id=profile["id"])
    # the second call updates the row, so manufacture a duplicate by hand
    profile["bindings"].append({"gesture": "fist", "action": "system.undo"})
    issues = check_bindings(prof)
    check("profile duplicates are caught",
          any("Media" in i.message and "Fist" in i.message for i in issues),
          str([i.message for i in issues]))
    check("profile shadowing is reported as info",
          any(i.level == "info" for i in check_bindings(prof)),
          str([i.message for i in check_bindings(prof)]))

    # ---- duplicates can be repaired -------------------------------------- #
    repair = Settings()
    repair.bindings.append({"gesture": "peace", "action": "system.copy"})
    repair.add_profile("Media", "spotify.exe")
    removed = fix_duplicates(repair)
    check("fix removes duplicate rows", removed == 1, str(removed))
    check("fix keeps the newer action",
          repair.binding_for("peace") == "system.copy",
          str(repair.binding_for("peace")))
    check("fix leaves a clean state", run_all(repair) == [],
          str([i.message for i in run_all(repair)]))

    # ---- custom gesture overlap ------------------------------------------ #
    template = [0.0] * 42
    near = [value + 0.005 for value in template]
    far = [value + 0.4 for value in template]
    custom = Settings()
    custom.add_custom_gesture({"id": "a", "name": "Alpha", "template": template})
    custom.add_custom_gesture({"id": "b", "name": "Beta", "template": near})
    custom.add_custom_gesture({"id": "c", "name": "Gamma", "template": far})
    issues = check_custom_gestures(custom)
    check("near-identical custom gestures warn",
          messages(issues, "Alpha") and messages(issues, "Beta"),
          str([i.message for i in issues]))
    check("distinct custom gestures do not warn",
          not any("Gamma" in i.message for i in issues),
          str([i.message for i in issues]))

    # ---- chords ---------------------------------------------------------- #
    dupe_chord = Settings()
    dupe_chord.chords.append({"id": "again", "name": "Palms again",
                              "left": "open_palm", "right": "open_palm"})
    check("duplicate chord pair warns",
          messages(check_chords(dupe_chord), "same hand pair"),
          str([i.message for i in check_chords(dupe_chord)]))

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
