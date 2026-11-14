"""Settings, gesture library and default bindings.

Everything the user can change lives in config/settings.json.  Unknown keys are
filled in from DEFAULT_SETTINGS on load so old configs keep working.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

APP_NAME = "Ghost Hand"

# When frozen by PyInstaller the program lives next to the exe, but bundled data
# (the hand model) is unpacked into _MEIPASS. Config and debug output always sit
# beside the exe so the user can edit and inspect them.
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parents[2]
    BUNDLE_DIR = APP_DIR

ASSETS_DIR = BUNDLE_DIR / "assets"
MODELS_DIR = ASSETS_DIR / "models"
CONFIG_DIR = APP_DIR / "config"
DEBUG_DIR = APP_DIR / "debug"
SETTINGS_PATH = CONFIG_DIR / "settings.json"
HAND_MODEL_PATH = MODELS_DIR / "hand_landmarker.task"


# --------------------------------------------------------------------------- #
# Gesture library (metadata only; the classifier lives in gestures.py)
# --------------------------------------------------------------------------- #

GESTURES: dict[str, dict[str, Any]] = {
    "rock": {
        "name": "Rock Sign",
        "hint": "Index and pinky up, middle and ring down. Default arming pose.",
        "kind": "pose",
    },
    "open_palm": {
        "name": "Open Palm",
        "hint": "All five fingers spread.",
        "kind": "pose",
    },
    "fist": {
        "name": "Fist",
        "hint": "Closed hand, thumb tucked.",
        "kind": "pose",
    },
    "peace": {
        "name": "V Sign",
        "hint": "Index + middle up, ring + pinky down.",
        "kind": "pose",
    },
    "thumbs_up": {
        "name": "Thumbs Up",
        "hint": "Thumb out, pointing up. Hold to ramp.",
        "kind": "hold",
    },
    "thumbs_down": {
        "name": "Thumbs Down",
        "hint": "Thumb out, pointing down. Hold to ramp.",
        "kind": "hold",
    },
    "thumb_left": {
        "name": "Thumb Left",
        "hint": "Fist with the thumb stuck out to the left.",
        "kind": "pose",
    },
    "thumb_right": {
        "name": "Thumb Right",
        "hint": "Fist with the thumb stuck out to the right.",
        "kind": "pose",
    },
    "point_up": {
        "name": "Index Up",
        "hint": "Only the index finger up.",
        "kind": "pose",
    },
    "ok_sign": {
        "name": "OK Sign",
        "hint": "Thumb and index form a circle, other fingers up.",
        "kind": "pose",
    },
    "three": {
        "name": "Three Fingers",
        "hint": "Index, middle and ring up.",
        "kind": "pose",
    },
    "swipe_left": {
        "name": "Swipe Left",
        "hint": "Move an open palm quickly to the left.",
        "kind": "motion",
    },
    "swipe_right": {
        "name": "Swipe Right",
        "hint": "Move an open palm quickly to the right.",
        "kind": "motion",
    },
    "swipe_up": {
        "name": "Swipe Up",
        "hint": "Move an open palm quickly upward.",
        "kind": "motion",
    },
    "swipe_down": {
        "name": "Swipe Down",
        "hint": "Move an open palm quickly downward.",
        "kind": "motion",
    },
}

# Actions the user can bind to a gesture.
ACTIONS: dict[str, dict[str, Any]] = {
    "none": {"name": "Nothing", "category": "General"},
    "media.play_pause": {"name": "Play / Pause", "category": "Media"},
    "media.next": {"name": "Next Track", "category": "Media"},
    "media.prev": {"name": "Previous Track", "category": "Media"},
    "media.mute": {"name": "Mute", "category": "Media"},
    "media.volume_up": {"name": "Volume Up", "category": "Media"},
    "media.volume_down": {"name": "Volume Down", "category": "Media"},
    "system.copy": {"name": "Copy", "category": "System"},
    "system.paste": {"name": "Paste", "category": "System"},
    "system.undo": {"name": "Undo", "category": "System"},
    "system.redo": {"name": "Redo", "category": "System"},
    "system.show_desktop": {"name": "Show Desktop", "category": "System"},
    "system.alt_tab": {"name": "Switch App (Alt+Tab)", "category": "System"},
    "system.task_manager": {"name": "Task Manager", "category": "System"},
    "system.screenshot": {"name": "Screenshot Snipping", "category": "System"},
    "system.lock": {"name": "Lock Screen", "category": "System"},
    "app.launch": {"name": "Launch App...", "category": "Apps"},
}


DEFAULT_SETTINGS: dict[str, Any] = {
    "camera": {
        "color_width": 1280,
        "color_height": 720,
        "depth_width": 848,
        "depth_height": 480,
        "fps": 30,
        "mirror": True,
    },
    "detection": {
        "min_hand_detection_confidence": 0.5,
        "min_hand_presence_confidence": 0.5,
        "min_tracking_confidence": 0.45,
        "max_hands": 2,
        "min_distance_m": 0.20,
        "max_distance_m": 2.00,
    },
    "engine": {
        "arm_mode": "pose",            # "pose" | "always"
        "arm_pose": "rock",
        "arm_hold_ms": 550,
        "auto_disarm_ms": 6000,
        "pose_threshold": 0.55,
        "stability_frames": 5,
        "fire_hold_ms": 400,           # how long a gesture must be held to fire
        "volume_hold_ms": 300,         # delay before the volume ramp starts
        "cooldown_ms": 450,
        "volume_ramp_interval_ms": 110,
        "volume_step": 2,
        "depth_gating": True,
        "dial_enabled": True,          # pinch-and-rotate volume dial
        "dial_degrees_per_step": 6.0,   # wrist rotation per volume tick
        "dial_invert": False,
        "swipe_enabled": True,
        "swipe_pose": "open_palm",     # pose required to start a swipe ("" = any)
        "swipe_window_ms": 320,
        "swipe_min_distance": 1.3,     # hand lengths (palm length = 1.0)
        "swipe_cooldown_ms": 600,
        "chord_enabled": True,
        "chord_cooldown_ms": 900,
    },
    "safety": {
        "practice_mode": True,         # True = log only, never send keys
    },
    "ui": {
        "always_on_top": False,
        "start_minimized": False,
        "guide_seen": False,
    },
    "autostart": False,
    "profiles": [],
    "macros": [],
    "sounds": [],
    "custom_gestures": [],
    "chords": [
        {"id": "both_palms", "left": "open_palm", "right": "open_palm",
         "name": "Both Palms"},
        {"id": "fist_and_palm", "left": "fist", "right": "open_palm",
         "name": "Fist + Palm"},
        {"id": "both_fists", "left": "fist", "right": "fist",
         "name": "Both Fists"},
    ],
    "soundboard": {
        "volume": 0.8,
        "mic_route": True,        # play into the virtual cable so calls hear it
        "monitor": True,          # also play on your speakers
        "output_device": "",      # "" = system default speakers
        "cable_device": "",       # "" = auto-detect "CABLE Input"
        "max_voices": 8,
    },
    "cursor": {
        "enabled": False,
        "one_euro_min_cutoff": 0.35,   # lower = steadier at rest, laggier
        "one_euro_beta": 0.08,         # higher = follows fast movement more closely
        "gain": 1.0,                   # >1 amplifies hand movement
        "region_x0": 0.18,
        "region_x1": 0.82,
        "region_y0": 0.18,
        "region_y1": 0.82,
        "pinch_enter": 0.40,           # pinch distance that starts a click
        "pinch_exit": 0.55,            # ...and the looser one that ends it
        "drag_hold_ms": 400,           # hold past this to drag instead of click
        "click_cooldown_ms": 320,
        "virtual_screen": True,        # span every monitor, not just the primary
    },
    "bindings": [
        {"gesture": "peace", "action": "media.play_pause"},
        {"gesture": "thumbs_up", "action": "media.volume_up"},
        {"gesture": "thumbs_down", "action": "media.volume_down"},
        {"gesture": "thumb_left", "action": "media.prev"},
        {"gesture": "thumb_right", "action": "media.next"},
        {"gesture": "point_up", "action": "media.mute"},
    ],
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in override.items():
        if key in out and isinstance(out[key], dict) and isinstance(value, dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


class Settings:
    """Dict-backed settings with dotted access: settings.get("engine.arm_hold_ms")."""

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.data = _deep_merge(DEFAULT_SETTINGS, data or {})
        # Runtime-only: which profile the foreground app selected.
        self.active_profile = "default"

    @classmethod
    def load(cls, path: Path = SETTINGS_PATH) -> "Settings":
        if path.exists():
            try:
                return cls(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass
        return cls()

    def save(self, path: Path = SETTINGS_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    # -- convenience ------------------------------------------------------ #

    @property
    def bindings(self) -> list[dict[str, str]]:
        return self.data.get("bindings", [])

    def binding_for(self, gesture: str, profile_id: str | None = None) -> str | None:
        row = self.binding_row(gesture, profile_id)
        return row.get("action") if row else None

    def rows_for(self, profile_id: str | None = None) -> list[dict[str, str]]:
        """Binding list for a profile; None means "the active profile"."""
        target = profile_id if profile_id is not None else self.active_profile
        if not target or target == "default":
            return self.bindings
        profile = self.profile_by_id(target)
        if profile is None:
            return self.bindings
        return profile.setdefault("bindings", [])

    def binding_row(self, gesture: str, profile_id: str | None = None) -> dict[str, str] | None:
        rows = self.rows_for(profile_id)
        for row in rows:
            if row.get("gesture") == gesture:
                return row
        # Profile bindings fall back to the default set.
        if rows is not self.bindings:
            for row in self.bindings:
                if row.get("gesture") == gesture:
                    return row
        return None

    def binding_target(self, gesture: str, profile_id: str | None = None) -> str | None:
        row = self.binding_row(gesture, profile_id)
        return row.get("target") if row else None

    def set_binding(self, gesture: str, action: str | None, target: str | None = None,
                    profile_id: str | None = None) -> None:
        rows = self.rows_for(profile_id)
        row = next((r for r in rows if r.get("gesture") == gesture), None)
        if action in (None, "", "none"):
            if row is not None:
                rows.remove(row)
            return
        if row is None:
            row = {"gesture": gesture}
            rows.append(row)
        row["action"] = action
        if target:
            row["target"] = target
        else:
            row.pop("target", None)

    # -- profiles --------------------------------------------------------- #

    @property
    def profiles(self) -> list[dict[str, Any]]:
        return self.data.setdefault("profiles", [])

    def profile_by_id(self, profile_id: str) -> dict[str, Any] | None:
        for profile in self.profiles:
            if profile.get("id") == profile_id:
                return profile
        return None

    def add_profile(self, name: str, match: str) -> dict[str, Any]:
        import uuid

        profile = {
            "id": uuid.uuid4().hex[:10],
            "name": name.strip() or "Profile",
            "match": match.strip(),
            "bindings": [],
        }
        self.profiles.append(profile)
        return profile

    def remove_profile(self, profile_id: str) -> None:
        self.data["profiles"] = [p for p in self.profiles if p.get("id") != profile_id]
        if self.active_profile == profile_id:
            self.active_profile = "default"

    def action_label(self, action_id: str | None) -> str:
        if not action_id:
            return "Unmapped"
        if action_id.startswith("macro.play:"):
            macro = self.macro(action_id.split(":", 1)[1])
            return f"Play: {macro['name']}" if macro else "Missing macro"
        if action_id.startswith("sound.play:"):
            sound = self.sound(action_id.split(":", 1)[1])
            return f"Sound: {sound['name']}" if sound else "Missing sound"
        return ACTIONS.get(action_id, {}).get("name", action_id)

    # -- macros ----------------------------------------------------------- #

    @property
    def macros(self) -> list[dict[str, Any]]:
        return self.data.setdefault("macros", [])

    def macro(self, macro_id: str) -> dict[str, Any] | None:
        for macro in self.macros:
            if macro.get("id") == macro_id:
                return macro
        return None

    def add_macro(self, macro: dict[str, Any]) -> None:
        self.macros.append(macro)

    def remove_macro(self, macro_id: str) -> None:
        self.data["macros"] = [m for m in self.macros if m.get("id") != macro_id]
        action = f"macro.play:{macro_id}"
        self.data["bindings"] = [row for row in self.bindings if row.get("action") != action]

    # -- sounds ----------------------------------------------------------- #

    @property
    def sounds(self) -> list[dict[str, Any]]:
        return self.data.setdefault("sounds", [])

    def sound(self, sound_id: str) -> dict[str, Any] | None:
        for sound in self.sounds:
            if sound.get("id") == sound_id:
                return sound
        return None

    def add_sound(self, sound: dict[str, Any]) -> None:
        self.sounds.append(sound)

    def remove_sound(self, sound_id: str) -> None:
        self.data["sounds"] = [s for s in self.sounds if s.get("id") != sound_id]
        action = f"sound.play:{sound_id}"
        self.data["bindings"] = [row for row in self.bindings if row.get("action") != action]

    def gesture_label(self, gesture_id: str | None) -> str:
        if not gesture_id:
            return "—"
        if gesture_id.startswith("chord:"):
            chord_id = gesture_id.split(":", 1)[1]
            for chord in self.chords:
                if chord.get("id") == chord_id:
                    return chord.get("name", chord_id)
            return "Missing chord"
        if gesture_id.startswith("custom:"):
            gesture = self.custom_gesture(gesture_id.split(":", 1)[1])
            return gesture.get("name", "custom") if gesture else "Missing gesture"
        return GESTURES.get(gesture_id, {}).get("name", gesture_id)

    # -- chords / custom gestures ----------------------------------------- #

    @property
    def chords(self) -> list[dict[str, Any]]:
        return self.data.setdefault("chords", [])

    @property
    def custom_gestures(self) -> list[dict[str, Any]]:
        return self.data.setdefault("custom_gestures", [])

    def custom_gesture(self, gesture_id: str) -> dict[str, Any] | None:
        for gesture in self.custom_gestures:
            if gesture.get("id") == gesture_id:
                return gesture
        return None

    def add_custom_gesture(self, gesture: dict[str, Any]) -> None:
        self.custom_gestures.append(gesture)

    def remove_custom_gesture(self, gesture_id: str) -> None:
        self.data["custom_gestures"] = [
            g for g in self.custom_gestures if g.get("id") != gesture_id
        ]
        self.data["bindings"] = [
            row for row in self.bindings
            if row.get("gesture") != f"custom:{gesture_id}"
        ]


def available_actions(settings: Settings) -> dict[str, dict[str, Any]]:
    """Static action catalogue plus one entry per saved macro and sound."""
    actions: dict[str, dict[str, Any]] = {key: dict(meta) for key, meta in ACTIONS.items()}
    for macro in settings.macros:
        actions[f"macro.play:{macro.get('id')}"] = {
            "name": f"Play: {macro.get('name', 'macro')}",
            "category": "Macros",
        }
    for sound in settings.sounds:
        actions[f"sound.play:{sound.get('id')}"] = {
            "name": f"Sound: {sound.get('name', 'sound')}",
            "category": "Sounds",
        }
    return actions


def available_gestures(settings: Settings) -> dict[str, dict[str, Any]]:
    """Static gesture library plus two-hand chords and learned gestures."""
    gestures: dict[str, dict[str, Any]] = {key: dict(meta) for key, meta in GESTURES.items()}
    for chord in settings.chords:
        left = settings.gesture_label(chord.get("left"))
        right = settings.gesture_label(chord.get("right"))
        gestures[f"chord:{chord.get('id')}"] = {
            "name": chord.get("name", "chord"),
            "hint": f"Two hands: {left} + {right}.",
            "kind": "chord",
        }
    for custom in settings.custom_gestures:
        gestures[f"custom:{custom.get('id')}"] = {
            "name": custom.get("name", "custom gesture"),
            "hint": "Learned from your own recording.",
            "kind": "custom",
        }
    return gestures
