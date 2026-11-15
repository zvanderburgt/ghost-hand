"""Tuning and per-gesture switch checks.

    python scripts/tuning_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.gestures import GestureEngine  # noqa: E402
from gr.synthetic import POSE_SPECS, make_hand  # noqa: E402

W, H = 1280, 720
results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, bool(condition), detail))


def hand(pose: str, cx: float = 640.0):
    return make_hand(pose, W, H, size_px=417, center=(cx, 400.0))


def arm(engine: GestureEngine, t: float) -> float:
    for _ in range(60):
        engine.update([hand("rock")], t)
        t += 33.0
    return t


def main() -> int:
    # ---- settings round trip --------------------------------------------- #
    settings = Settings()
    check("gestures are enabled by default", settings.is_gesture_enabled("peace"))
    settings.set_gesture_enabled("peace", False)
    check("disabling records the gesture", not settings.is_gesture_enabled("peace"))
    check("disabled list is stored", settings.disabled_gestures == ["peace"],
          str(settings.disabled_gestures))
    settings.set_gesture_enabled("peace", True)
    check("re-enabling clears it", settings.disabled_gestures == [],
          str(settings.disabled_gestures))
    settings.set_gesture_enabled("peace", False)
    settings.set_gesture_enabled("peace", False)
    check("disabling twice is idempotent", settings.disabled_gestures == ["peace"],
          str(settings.disabled_gestures))

    # ---- disabled gestures cannot win ------------------------------------ #
    settings = Settings()
    settings.set_gesture_enabled("peace", False)
    engine = GestureEngine(settings)
    t = arm(engine, 1000.0)
    fired: list[str] = []
    labels = set()
    for _ in range(40):
        state = engine.update([hand("peace")], t)
        t += 33.0
        fired.extend(state.fired)
        labels.add(state.stable_label or state.label)
    check("disabled gesture never fires", fired == [], str(fired))
    check("disabled gesture is not reported", "peace" not in labels, str(labels))

    # ---- arming pose is exempt ------------------------------------------- #
    settings = Settings()
    settings.set_gesture_enabled("rock", False)
    engine = GestureEngine(settings)
    t = 1000.0
    armed = False
    for _ in range(60):
        state = engine.update([hand("rock")], t)
        t += 33.0
        armed = armed or state.armed
    check("arming pose cannot be disabled", armed)

    # ---- chords respect the switch --------------------------------------- #
    settings = Settings()
    settings.set_gesture_enabled("open_palm", False)
    engine = GestureEngine(settings)
    t = arm(engine, 1000.0)
    fired = []
    for _ in range(40):
        state = engine.update([hand("open_palm", 380.0), hand("open_palm", 900.0)], t)
        t += 33.0
        fired.extend(state.fired)
    check("chord cannot form from a disabled pose",
          [g for g in fired if g.startswith("chord:")] == [], str(fired))

    # ---- thresholds are read from settings ------------------------------- #
    settings = Settings()
    settings.set("engine.pose_threshold", 1.01)  # nothing can reach this
    engine = GestureEngine(settings)
    t = arm(engine, 1000.0)
    labels = set()
    for _ in range(40):
        state = engine.update([hand("peace")], t)
        t += 33.0
        labels.add(state.stable_label or state.label)
    check("pose threshold is applied", "peace" not in labels, str(labels))

    # ---- custom gestures can be switched off ----------------------------- #
    POSE_SPECS["index_ring"] = "1010"
    from gr.custom import descriptor  # noqa: E402

    template = descriptor(hand("index_ring"))
    settings = Settings()
    settings.add_custom_gesture({"id": "learned", "name": "Learned",
                                 "template": template, "samples": 20})
    settings.set_binding("custom:learned", "media.play_pause")
    settings.set_gesture_enabled("custom:learned", False)
    engine = GestureEngine(settings)
    t = arm(engine, 1000.0)
    fired = []
    for _ in range(40):
        state = engine.update([hand("index_ring")], t)
        t += 33.0
        fired.extend(state.fired)
    check("custom gesture can be disabled", fired == [], str(fired))

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
