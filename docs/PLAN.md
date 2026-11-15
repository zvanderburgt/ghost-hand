# Plan

Post-roadmap work, in the order it will be built. Each item is done when its
acceptance criteria hold and the relevant checks pass (`scripts/*_check.py`).

## 1. Tuning panel

A dialog that exposes the thresholds currently buried in `settings.json`, with the
defaults intact and changes applied live.

- [x] Pose confidence, stability frames, hold-to-fire, cooldown
- [x] Depth window (min/max metres)
- [x] Swipe distance and cooldown
- [x] Opened from Bindings ("Tuning…") and the tray
- Acceptance: moving a slider changes engine behaviour without a restart; values
  persist on release; `tuning_check.py` covers score filtering and round-trip.

## 2. Per-gesture enable/disable

Turn a gesture off entirely rather than just unbinding it.

- [x] `disabled_gestures` in settings, honoured by the engine and chord detector
- [x] Checklist inside the tuning panel (arming pose not disableable)
- [x] Disabled gestures hidden from the Live scores board
- Acceptance: a disabled gesture cannot win, cannot fire, and cannot form a chord.

## 3. Cursor: right-click and scroll

- [x] Right-click from thumb + middle tip, own cooldown
- [x] Scroll from the peace pose plus vertical hand movement
- [x] Both respect the freeze-while-pinching rule
- Acceptance: `cursor_check.py` covers right-click edges and scroll accumulation.

## 4. Dwell clicking

Click by holding the pointer still, for people who find pinching unreliable.

- [x] `cursor.dwell_enabled` (default off), `dwell_ms`, `dwell_radius_px`
- [x] One click per dwell, re-armed after leaving the radius
- Acceptance: a stationary pointer clicks once; moving resets the timer.

## 5. Demo GIF

- [x] `scripts/make_demo.py` renders the demo source to `docs/demo.gif`
- [x] Referenced from the README
- Acceptance: GIF is under ~5 MB and shows the skeleton with the gesture name.

## 6. Update check

- [x] Read the latest GitHub release, compare with the running version
- [x] Tray notification plus a menu item; silent when offline or up to date
- [x] `ui.check_updates` toggle
- Acceptance: version comparison and release parsing covered offline.

## 7. Window-title profiles

- [x] Optional title substring on a profile, in addition to the process rule
- [x] `Ctrl+Alt+T`-style tabs (browser tabs) become distinguishable
- Acceptance: process-only profiles behave exactly as before.

## 8. Contributor scaffolding

- [x] `CONTRIBUTING.md`: setup, checks, adding a gesture, releasing
- [x] Issue templates and PR template
- Acceptance: a newcomer can go from clone to green tests using only the docs.

## Out of scope

- Code signing (needs a purchased certificate).
- Removing OpenCV to shrink the download (broad refactor, no functional gain).
- Replacing the rule-based classifier with a learned model.
