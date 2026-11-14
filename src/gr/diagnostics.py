"""Static checks over bindings, chords and learned gestures.

Catches the problems that are invisible in the UI but change behaviour:

* one gesture bound to two different actions (only the last one can ever fire),
* the same action wired to several gestures (usually a mistake, but legal),
* bindings pointing at macros/sounds/custom gestures that no longer exist,
* the arming pose given an action (the engine never fires it),
* two learned hand shapes that are too similar to tell apart,
* duplicate two-hand chord definitions.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import Settings
from .custom import CUSTOM_CUTOFF, distance

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass(frozen=True)
class Issue:
    level: str
    message: str


def _sets(settings: Settings):
    yield "Default", settings.bindings
    for profile in settings.profiles:
        yield profile.get("name", "profile"), profile.setdefault("bindings", [])


def _gesture_name(settings: Settings, gesture_id: str | None) -> str:
    return settings.gesture_label(gesture_id)


def check_bindings(settings: Settings) -> list[Issue]:
    issues: list[Issue] = []
    arm_pose = str(settings.get("engine.arm_pose", "") or "")

    for scope, rows in _sets(settings):
        by_gesture: dict[str, list[str]] = {}
        by_action: dict[str, list[str]] = {}
        for row in rows:
            gesture = row.get("gesture") or "?"
            action = row.get("action") or "none"
            by_gesture.setdefault(gesture, []).append(action)
            if action != "none":
                by_action.setdefault(action, []).append(gesture)

        for gesture, actions in by_gesture.items():
            if len(actions) > 1:
                unique = sorted(set(actions))
                if len(unique) > 1:
                    labels = ", ".join(settings.action_label(a) for a in unique)
                    issues.append(Issue(
                        ERROR,
                        f"{scope}: «{_gesture_name(settings, gesture)}» is bound to "
                        f"{len(unique)} different actions ({labels}) — only one can fire",
                    ))
                else:
                    issues.append(Issue(
                        WARNING,
                        f"{scope}: «{_gesture_name(settings, gesture)}» is listed "
                        f"{len(actions)} times",
                    ))

        for action, gestures in by_action.items():
            if len(gestures) > 1:
                names = ", ".join(_gesture_name(settings, g) for g in gestures)
                issues.append(Issue(
                    WARNING,
                    f"{scope}: «{settings.action_label(action)}» is bound to "
                    f"{len(gestures)} gestures ({names})",
                ))

        for index, row in enumerate(rows):
            action = str(row.get("action") or "")
            gesture = row.get("gesture")
            if action.startswith("macro.play:"):
                if settings.macro(action.split(":", 1)[1]) is None:
                    issues.append(Issue(
                        ERROR, f"{scope}: «{_gesture_name(settings, gesture)}» points at a deleted macro"))
            elif action.startswith("sound.play:"):
                if settings.sound(action.split(":", 1)[1]) is None:
                    issues.append(Issue(
                        ERROR, f"{scope}: «{_gesture_name(settings, gesture)}» points at a deleted sound"))
            elif action == "app.launch" and not row.get("target"):
                issues.append(Issue(
                    WARNING,
                    f"{scope}: «{_gesture_name(settings, gesture)}» launches an app "
                    f"but no path is set",
                ))
            elif gesture and str(gesture).startswith("custom:"):
                if settings.custom_gesture(str(gesture).split(":", 1)[1]) is None:
                    issues.append(Issue(
                        ERROR, f"{scope}: binding points at a deleted custom gesture"))

        if arm_pose:
            for index, row in enumerate(rows):
                if row.get("gesture") == arm_pose and (row.get("action") or "none") != "none":
                    issues.append(Issue(
                        WARNING,
                        f"{scope}: «{_gesture_name(settings, arm_pose)}» is the arming pose, "
                        f"so its «{settings.action_label(row.get('action'))}» binding never fires",
                    ))
                    break

    # Profiles that override a default binding are expected, but silent
    # shadowing is worth surfacing once.
    if settings.profiles:
        default_gestures = {row.get("gesture") for row in settings.bindings}
        shadowed = 0
        for profile in settings.profiles:
            for row in profile.get("bindings", []):
                if row.get("gesture") in default_gestures:
                    shadowed += 1
        if shadowed:
            issues.append(Issue(
                INFO,
                f"{shadowed} profile binding(s) override a default binding while that "
                f"app is focused",
            ))
    return issues


def check_custom_gestures(settings: Settings) -> list[Issue]:
    issues: list[Issue] = []
    learned = [
        (g.get("id"), g.get("name") or "custom", g.get("template"))
        for g in settings.custom_gestures
    ]
    for i in range(len(learned)):
        for j in range(i + 1, len(learned)):
            _, name_a, template_a = learned[i]
            _, name_b, template_b = learned[j]
            if not template_a or not template_b:
                continue
            gap = distance(template_a, template_b)
            if gap < CUSTOM_CUTOFF * 0.55:
                issues.append(Issue(
                    WARNING,
                    f"Custom gestures «{name_a}» and «{name_b}» are nearly identical "
                    f"(distance {gap:.2f}) — they will fire each other",
                ))
    return issues


def check_chords(settings: Settings) -> list[Issue]:
    issues: list[Issue] = []
    seen: dict[tuple[str, str], str] = {}
    for chord in settings.chords:
        pair = tuple(sorted((str(chord.get("left")), str(chord.get("right")))))
        name = chord.get("name") or chord.get("id") or "chord"
        if pair in seen:
            issues.append(Issue(
                WARNING,
                f"Chords «{seen[pair]}» and «{name}» use the same hand pair",
            ))
        else:
            seen[pair] = name
    return issues


def run_all(settings: Settings) -> list[Issue]:
    return check_bindings(settings) + check_custom_gestures(settings) + check_chords(settings)


def fix_duplicates(settings: Settings) -> int:
    """Collapse repeated gesture rows, keeping the most recent entry."""
    removed = 0
    for _, rows in _sets(settings):
        keep: list[dict] = []
        index: dict[str, int] = {}
        for row in rows:
            gesture = row.get("gesture")
            if gesture in index:
                keep[index[gesture]] = row
                removed += 1
            else:
                index[gesture] = len(keep)
                keep.append(row)
        rows[:] = keep
    return removed
