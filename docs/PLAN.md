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

## 9. Per-application volume (Spotify first, post-0.7.0)

The Windows Volume Mixer, exposed to gestures. The dial keeps controlling the system
by default, but can be pointed at the focused app or one named process such as
`spotify.exe`; bindings can nudge or mute a named app independently of the dial.

WASAPI session volumes are what the mixer edits; the media keys used today only move
the master volume. pycaw is the smallest reliable wrapper, works offline and needs no
Spotify login. Verified: pycaw sees the running `Spotify.exe` session and a
`SetMasterVolume` round-trip (1.00 → 0.97 → 1.00) changes it.

- [x] `gr/app_audio.py`: pycaw-backed session service. List active render sessions,
  match process names case-insensitively, group multiple sessions, cache for ~1 s,
  retry once on a dead session, and return friendly errors when the app isn't playing.
  COM is initialised on the calling thread and sessions stay on that thread.
- [x] Actions `audio.app_up`, `audio.app_down`, `audio.app_mute`; the binding's
  existing `target` field holds the process match (`spotify.exe`). Up/down belong in
  the ramp set but only ramp when a target is set; mute is one-shot. `action_label`
  takes the target so labels read "Spotify — Volume Up"; diagnostics flags a missing
  target.
- [x] `engine.dial_target` = `"system"` (default), `"foreground"`, or a process match.
  Resolve it when the dial engages and hold it until release. App targets change
  `ISimpleAudioVolume` by 2% per tick and never send media keys.
- [x] Bindings → Volume dial gets a **Controls** picker (System / Focused app /
  running app / type a process name). The main-window readout names the target.
- [x] Batch dial/ramp ticks into one app-volume write (`ActionBus.fire(..., repeat=n)`)
  so a fast turn is one COM call and one log line, not five.
- [x] `audio_check.py`: fake session backend covers case-insensitive matching,
  multiple sessions, clamping, mute, missing apps and batched steps. `--live` finds
  Spotify, nudges 1% and restores. Add app-volume cases to `ramp_check.py`.
- [x] `requirements.txt`: `pycaw` (MIT; pulls comtypes + psutil). Add pycaw to the
  PyInstaller collect list and confirm a packaged build controls Spotify.
- [x] README and the in-app guide mention the dial target, with Spotify as the example.
- Live Spotify session verified from source and from the frozen build:
  `audio_check.py --live` and `GhostHand.exe --audio-probe` both nudge 1% and
  restore it. The full manual gesture acceptance pass is still open.
- Acceptance: with Spotify playing, the dial changes Spotify's session volume while
  system volume stays put; a gesture can mute Spotify without muting other audio;
  stopping/restarting Spotify recovers; practice mode changes nothing; a build still
  launches on a machine without Spotify.
- Spotify limits: controls the desktop app on this PC. Spotify Connect to a phone or
  speaker, and Spotify in a browser (`chrome.exe`/`msedge.exe`), are separate
  sessions; a single browser tab cannot be isolated with WASAPI. Document both.

- [x] **Mixer…** dialog from the Volume dial card: live sessions with per-app
  sliders, mute, Refresh, and "Use for dial".

## Pending review

- [ ] **0.7.0 release decision (check after 2026-11-17).** 0.7.0 is committed but
  untagged. Run it daily for a couple of days — cursor feel, right-click, scroll,
  dwell, tuning persistence, per-gesture switches, title profiles, armed toast —
  then tag `v0.7.0` (CI builds the release) or fix and retag. Tracked as a GitHub
  issue as well.

## Out of scope

- Code signing (needs a purchased certificate).
- Removing OpenCV to shrink the download (broad refactor, no functional gain).
- Replacing the rule-based classifier with a learned model.
