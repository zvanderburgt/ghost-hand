# Contributing to Ghost Hand

Thanks for taking a look. This is a Windows desktop app that turns hand
gestures into input events, so most work happens in a small Python codebase with
a Qt interface.

## Setup

Requirements: Windows 10/11, Python 3.13, git. A RealSense camera is needed to
exercise the live path, but most development works without one.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run-debug.bat          # tray app with a console for tracebacks
```

No camera? The whole interface runs against a synthetic hand:

```powershell
.\.venv\Scripts\python.exe src\main.py --demo
```

`--demo` never sends input to Windows, so it's safe to poke at.

## Checks

Every subsystem has a self-checking script that runs headlessly:

```powershell
.\scripts\run_checks.ps1
```

or individually:

| Script | Covers |
| --- | --- |
| `pose_regression.py` | pose classifier, including tricky real-world hands |
| `arm_check.py` | arming pose behaviour |
| `ramp_check.py` | hold-to-ramp volume follows the binding |
| `dial_check.py` | rotary volume dial |
| `macro_check.py` | macro record/playback model |
| `sound_check.py` | routing, decoding, mixing |
| `cursor_check.py` | mapping, smoothing, clicks, scroll, dwell |
| `swipe_check.py` | directional swipes |
| `chord_check.py` | two-hand chords |
| `custom_check.py` | learned gesture descriptors |
| `profiles_check.py` | app and window-title profile matching |
| `calibration_check.py` | cursor-region maths |
| `diagnostics_check.py` | binding conflict detection |
| `tuning_check.py` | thresholds and per-gesture switches |
| `updater_check.py` | version comparison and release parsing |

CI runs all of them on every push and pull request (`.github/workflows/tests.yml`).

## Layout

```
src/gr/
  camera.py        RealSense capture, depth alignment
  hands.py         MediaPipe hand landmarks
  gestures.py      features, pose scoring, arming, swipes, chords, dial
  pipeline.py      camera -> tracker -> engine -> actions, annotation
  actions.py       key chords, media keys, macro and sound dispatch
  cursor.py        One Euro smoothing, clicks, drag, scroll, dwell
  custom.py        learned shape descriptor and matching
  profiles.py      foreground app / title matching
  diagnostics.py   binding conflict checks
  updater.py       GitHub release check
  ui/              window, tray, dialogs, icon
```

## Adding a gesture

1. Add an entry to `GESTURES` in `src/gr/config.py` (display name and hint).
2. Add a scorer to `score_poses` in `src/gr/gestures.py`. Use fuzzy `min`/`max`
   composition — a pose should require its defining fingers *and* the others to
   be curled, not just average them.
3. Add the pose to `POSE_SPECS` in `src/gr/synthetic.py` so it can be tested
   without a camera.
4. Add a case to `scripts/pose_regression.py`, including a plausible near-miss.
5. Run the checks.

Thresholds are shared (`engine.pose_threshold`); prefer making a pose
unambiguous rather than lowering the threshold for everyone.

## Adding an action

Add it to `ACTIONS` in `src/gr/config.py`, then handle it in
`ActionBus._execute` in `src/gr/actions.py`. Actions that should repeat while a
gesture is held belong in `RAMP_ACTIONS` in `gestures.py`.

## Style

- Type hints on public functions; comments explain *why*, not *what*.
- Keep modules focused: capture, perception, behaviour, UI.
- Anything that can be computed without a camera belongs behind a pure
  function so it can be tested.

## Releasing

1. Bump `VERSION` and `__version__` in `src/gr/__init__.py` (they are read by
   the updater and the packaging scripts).
2. Commit, then tag and push:

   ```powershell
   git tag v0.7.0
   git push origin v0.7.0
   ```

GitHub Actions builds the Windows zip, smoke-tests it locally by default, and
attaches it to the release. `package.ps1` produces the same zip on your machine.

## Reporting a bug

Use the issue template. The most useful details are the app version, your camera
model, the event log contents, and the relevant part of
`config/settings.json` (bindings, thresholds, disabled gestures).
