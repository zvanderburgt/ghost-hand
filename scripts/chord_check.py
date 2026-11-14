"""Two-hand chord checks.

    python scripts/chord_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.config import Settings  # noqa: E402
from gr.gestures import GestureEngine  # noqa: E402
from gr.synthetic import make_hand  # noqa: E402

W, H = 1280, 720


def hand(pose: str, cx: float, cy: float = 400.0):
    return make_hand(pose, W, H, size_px=380, center=(cx, cy))


def new_engine() -> GestureEngine:
    settings = Settings()
    settings.set("engine.chord_enabled", True)
    settings.set("engine.chord_cooldown_ms", 900)
    return GestureEngine(settings)


def arm(engine: GestureEngine, t: float) -> float:
    for _ in range(60):
        engine.update([hand("rock", 640.0)], t)
        t += 33.0
    return t


def run_pair(a: str, b: str, frames: int = 30, armed: bool = True) -> list[str]:
    engine = new_engine()
    t = 1000.0
    if armed:
        t = arm(engine, t)
    fired: list[str] = []
    for _ in range(frames):
        state = engine.update([hand(a, 380.0), hand(b, 900.0)], t)
        t += 33.0
        fired.extend(state.fired)
    return fired


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        results.append((name, bool(condition), detail))

    palms = run_pair("open_palm", "open_palm")
    check("both palms fires the chord", palms == ["chord:both_palms"], str(palms))

    fist_palm = run_pair("fist", "open_palm")
    check("fist + palm fires its chord", fist_palm == ["chord:fist_and_palm"], str(fist_palm))

    reversed_order = run_pair("open_palm", "fist")
    check("chord order does not matter",
          reversed_order == ["chord:fist_and_palm"], str(reversed_order))

    unmatched = run_pair("peace", "fist")
    chords_only = [item for item in unmatched if item.startswith("chord:")]
    check("unconfigured pair does nothing", chords_only == [], str(unmatched))

    single = new_engine()
    t = arm(single, 1000.0)
    fired: list[str] = []
    for _ in range(30):
        state = single.update([hand("open_palm", 640.0)], t)
        t += 33.0
        fired.extend(state.fired)
    check("one hand never fires a chord", fired == [], str(fired))

    disarmed = run_pair("open_palm", "open_palm", armed=False)
    check("chords need arming", disarmed == [], str(disarmed))

    # held chord must not repeat
    engine = new_engine()
    t = arm(engine, 1000.0)
    fired = []
    for _ in range(90):  # ~3 s of holding
        state = engine.update([hand("open_palm", 380.0), hand("open_palm", 900.0)], t)
        t += 33.0
        fired.extend(state.fired)
    check("held chord fires once", fired == ["chord:both_palms"], str(fired))

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
