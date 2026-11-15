"""Gesture classification, arming and hold-to-ramp volume.

The classifier is deliberately rule-based: it reads finger extension and thumb
direction from the 21 MediaPipe landmarks.  That means no training data, it
works for either hand, and every score is inspectable in the preview window.
"""

from __future__ import annotations

import math
import time
from collections import Counter, deque
from dataclasses import dataclass, field

import numpy as np

from .config import GESTURES
from .custom import descriptor as shape_descriptor
from .custom import match_score
from .hands import MIDDLE_MCP, PINKY_MCP, THUMB_MCP, WRIST, Hand

# landmark triples: (mcp, pip, dip, tip)
FINGER_CHAINS = {
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}
POSE_IDS = list(GESTURES.keys())

# ---- thumb tuning knobs ------------------------------------------------- #
# Protrusion is measured in palm widths. A comfortable thumb gesture clears the
# palm edge by roughly 0.15-0.20, so full confidence must arrive well before
# that - requiring 0.40 forced people to hyperextend the thumb.
THUMB_PROTRUSION_START = 0.05   # below this, treat as not protruding at all
THUMB_PROTRUSION_SPAN = 0.12    # full confidence at START + SPAN (0.17)

# How hard a protruding thumb suppresses "fist". High, so fists give way
# decisively instead of lingering near the thumb poses.
FIST_THUMB_PENALTY = 0.9

# Actions that repeat while the gesture is held instead of firing once.
RAMP_ACTIONS = frozenset({"media.volume_up", "media.volume_down"})


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return lo if v < lo else hi if v > hi else v


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _unit(a, b) -> tuple[float, float]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1e-6
    return dx / n, dy / n


def _angle_score(angle_deg: float, target_deg: float, falloff: float = 65.0) -> float:
    """1.0 when the direction matches the target, 0.0 when it's 90-ish deg off."""
    d = abs(((angle_deg - target_deg + 180.0) % 360.0) - 180.0)
    return _clamp((90.0 - d) / (90.0 - falloff + 1e-6))


@dataclass
class Features:
    ext: dict[str, float]
    thumb_dir: tuple[float, float]
    thumb_angle: float
    thumb_dy: float
    thumb_out_left: float
    thumb_out_right: float
    index_dir: tuple[float, float]
    index_angle: float
    scale: float
    palm_width: float
    pinch_ratio: float
    middle_pinch_ratio: float

    @property
    def others_curl(self) -> float:
        return float(np.mean([1.0 - self.ext[f] for f in ("index", "middle", "ring", "pinky")]))

    @property
    def others_ext(self) -> float:
        return float(np.mean([self.ext[f] for f in ("index", "middle", "ring", "pinky")]))

    @property
    def finger_count(self) -> int:
        return sum(1 for f in ("index", "middle", "ring", "pinky") if self.ext[f] > 0.6)


def _point_in_triangle(p, a, b, c) -> bool:
    """Barycentric point-in-triangle test (2D)."""
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = sign(p, a, b)
    d2 = sign(p, b, c)
    d3 = sign(p, c, a)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def extract_features(hand: Hand) -> Features | None:
    px = hand.px
    wrist = px[WRIST]
    scale = _dist(wrist, px[MIDDLE_MCP])
    if scale < 1e-3:
        return None
    palm_width = _dist(px[5], px[PINKY_MCP]) or scale

    ext: dict[str, float] = {}
    for name in ("index", "middle", "ring", "pinky"):
        _, _, _, tip = FINGER_CHAINS[name]
        pip = FINGER_CHAINS[name][1]
        d_tip = _dist(px[tip], wrist)
        d_pip = _dist(px[pip], wrist) or 1e-6
        ratio = d_tip / d_pip
        # Fully extended reads ~1.5-1.8x, curled ~0.9-1.1x.
        ext[name] = _clamp((ratio - 1.04) / 0.38)

    # Thumb extension: two independent cues, because a crossing thumb has no
    # usable "distance from the palm edge".
    #  1) how far the tip strays from the pinky MCP, relative to palm width
    spread = _dist(px[4], px[PINKY_MCP]) / palm_width
    spread_score = _clamp((spread - 0.85) / 0.45)
    #  2) how straight the proximal+distal segments are (folded thumbs bend)
    chain = _dist(px[2], px[3]) + _dist(px[3], px[4])
    straight = _dist(px[2], px[4]) / (chain or 1e-6)
    straight_score = _clamp((straight - 0.70) / 0.25)
    # A thumb whose tip sits inside the palm triangle is tucked, whatever else
    # the geometry says.
    tucked = _point_in_triangle(px[4], wrist, px[5], px[PINKY_MCP])
    ext["thumb"] = 0.0 if tucked else max(spread_score, straight_score)

    thumb_dir = _unit(px[THUMB_MCP], px[4])
    index_dir = _unit(px[5], px[8])
    thumb_angle = math.degrees(math.atan2(thumb_dir[1], thumb_dir[0]))
    index_angle = math.degrees(math.atan2(index_dir[1], index_dir[0]))
    pinch_ratio = _dist(px[4], px[8]) / scale
    middle_pinch_ratio = _dist(px[4], px[12]) / scale

    # How far the thumb tip sticks out of the palm, in palm widths.
    #   thumb_dy       > 0  tip above the index knuckle  (thumb up)
    #   thumb_out_left > 0  tip sticks out past the palm's left edge
    #   thumb_out_right> 0  tip sticks out past the palm's right edge
    # Pitch matters because a fist's thumb rests *over* the fingers and points
    # upward, so direction alone cannot tell it apart from a thumbs up.
    palm_left = min(px[5][0], px[PINKY_MCP][0])
    palm_right = max(px[5][0], px[PINKY_MCP][0])
    thumb_dy = (px[5][1] - px[4][1]) / palm_width
    thumb_out_left = (palm_left - px[4][0]) / palm_width
    thumb_out_right = (px[4][0] - palm_right) / palm_width

    return Features(
        ext=ext,
        thumb_dir=thumb_dir,
        thumb_angle=thumb_angle,
        thumb_dy=thumb_dy,
        thumb_out_left=thumb_out_left,
        thumb_out_right=thumb_out_right,
        index_dir=index_dir,
        index_angle=index_angle,
        scale=scale,
        palm_width=palm_width,
        pinch_ratio=pinch_ratio,
        middle_pinch_ratio=middle_pinch_ratio,
    )


def _ramp(value: float, start: float, span: float) -> float:
    return _clamp((value - start) / span)


def _axis_dominance(primary: float, other: float) -> float:
    """1.0 when `primary` clearly dominates `other`, 0.0 when it does not.

    Needed because a thumb pointing up also sits slightly to one side; without
    this, diagonal thumbs satisfy two directions at once and ties resolve
    arbitrarily.
    """
    if primary <= 0:
        return 0.0
    return _clamp(0.5 + (primary - abs(other)) / (0.6 * primary))


def _pointing(protrusion: float, component: float, other: float) -> float:
    """Score for a thumb sticking out of the palm in one cardinal direction.

    `component` / `other` are components of the thumb's *unit* direction vector,
    so they are scale-free and describe which way the thumb points.
    `protrusion` is how far the tip clears the palm in that direction, which
    decides how confident we are.
    """
    if component <= 0.0:
        return 0.0
    ramp = _ramp(protrusion, THUMB_PROTRUSION_START, THUMB_PROTRUSION_SPAN)
    return ramp * _axis_dominance(component, other)


def score_poses(f: Features) -> dict[str, float]:
    """Fuzzy-logic scoring: min() is AND, max() is OR.

    Independent scorers made contradictory poses score high at the same time
    (fist 75% while pointing), so each pose *requires* its defining fingers to
    be extended and the others to be curled.

    Directional thumb poses additionally require the thumb tip to protrude past
    the palm in that direction, with that axis dominant. Angle alone is not
    enough: a left-pointing thumb that tilts upward used to score 1.0 for both
    thumb_left and thumbs_up.
    """
    e = f.ext
    i, m, r, p, t = (e["index"], e["middle"], e["ring"], e["pinky"], e["thumb"])
    all_curl = min(1.0 - i, 1.0 - m, 1.0 - r, 1.0 - p)
    all_ext = min(i, m, r, p)
    index_up = _angle_score(f.index_angle, -90.0)

    up = _pointing(f.thumb_dy, -f.thumb_dir[1], abs(f.thumb_dir[0]))
    down = _pointing(-f.thumb_dy, f.thumb_dir[1], abs(f.thumb_dir[0]))
    left = _pointing(f.thumb_out_left, -f.thumb_dir[0], abs(f.thumb_dir[1]))
    right = _pointing(f.thumb_out_right, f.thumb_dir[0], abs(f.thumb_dir[1]))
    protruding = max(up, down, left, right)

    thumb_conf = 0.35 + 0.65 * t

    scores = {
        # all four fingers out; thumb adds confidence but isn't required
        "open_palm": all_ext * (0.55 + 0.45 * t),
        # everything closed and the thumb not sticking out in any direction
        "fist": all_curl * (1.0 - FIST_THUMB_PENALTY * protruding),
        # index + middle out, ring + pinky in
        "peace": min(i, m) * (1.0 - max(r, p)),
        # index + pinky out, middle + ring in (default arming pose)
        "rock": min(i, p) * (1.0 - max(m, r)),
        # index, middle, ring out, pinky in
        "three": min(i, m, r) * (1.0 - p),
        # only the index out and pointing up
        "point_up": i * (1.0 - max(m, r, p)) * index_up,
        "thumbs_up": t * all_curl * thumb_conf * up,
        "thumbs_down": t * all_curl * thumb_conf * down,
        "thumb_left": t * all_curl * thumb_conf * left,
        "thumb_right": t * all_curl * thumb_conf * right,
    }

    # thumb + index touching, remaining three out
    pinch = _clamp((0.62 - f.pinch_ratio) / 0.35)
    scores["ok_sign"] = pinch * min(m, r, p)

    return {k: _clamp(v) for k, v in scores.items()}


class ChordDetector:
    """Two-hand chords: both hands must hold a stable pose at the same time."""

    def __init__(self, settings) -> None:
        self.s = settings
        self._history: list[deque[str | None]] = [deque(maxlen=5), deque(maxlen=5)]
        self._latched: str | None = None
        self._cooldown_until = 0.0

    def reset(self) -> None:
        for history in self._history:
            history.clear()
        self._latched = None

    @staticmethod
    def _label(hand: Hand, threshold: float, disabled: set[str] | None = None) -> str | None:
        features = extract_features(hand)
        if features is None or features.scale < 18.0:
            return None
        scores = score_poses(features)
        for gesture_id in disabled or ():
            scores.pop(gesture_id, None)
        if not scores:
            return None
        label, confidence = max(scores.items(), key=lambda kv: kv[1])
        return label if confidence >= threshold else None

    def update(self, hands: list[Hand], now_ms: float, threshold: float) -> str | None:
        if not bool(self.s.get("engine.chord_enabled", True)):
            return None
        if len(hands) < 2:
            self.reset()
            return None

        disabled = set(self.s.disabled_gestures)
        labels: list[str] = []
        for index in range(2):
            history = self._history[index]
            history.append(self._label(hands[index], threshold, disabled))
            counts = Counter(item for item in history if item)
            if not counts:
                continue
            label, count = counts.most_common(1)[0]
            if count >= 3:
                labels.append(label)

        if len(labels) < 2:
            return None

        pair = tuple(sorted(labels))
        match: str | None = None
        for chord in self.s.chords:
            wanted = tuple(sorted((chord.get("left"), chord.get("right"))))
            if wanted == pair:
                match = f"chord:{chord.get('id')}"
                break

        if match is None:
            self._latched = None
            return None

        if match != self._latched and now_ms >= self._cooldown_until:
            self._latched = match
            self._cooldown_until = now_ms + float(
                self.s.get("engine.chord_cooldown_ms", 900)
            )
            return match
        return None


@dataclass
class EngineState:
    hands: list[Hand] = field(default_factory=list)
    primary: Hand | None = None
    features: Features | None = None
    scores: dict[str, float] = field(default_factory=dict)
    label: str | None = None
    confidence: float = 0.0
    stable_label: str | None = None
    stable_confidence: float = 0.0
    hold_ms: int = 0
    armed: bool = False
    arm_progress: float = 0.0
    arm_mode: str = "pose"
    fired: list[str] = field(default_factory=list)
    ramp_active: bool = False
    dial_active: bool = False
    dial_degrees: float = 0.0
    pointer: tuple[float, float] | None = None
    pointer_pinch: bool = False
    pointer_pinch_ratio: float = 1.0
    pointer_middle_pinch: float = 1.0
    pointer_scroll_mode: bool = False
    pointer_scroll_y: float = 0.5
    distance_m: float | None = None
    gated: bool = False
    note: str = ""

    @property
    def label_key(self) -> str | None:
        return self.stable_label or self.label


class GestureEngine:
    def __init__(self, settings) -> None:
        self.s = settings
        self.history: deque[str | None] = deque(maxlen=max(3, int(settings.get("engine.stability_frames", 5))))
        self.stable: str | None = None
        self.stable_conf = 0.0
        self.stable_since = 0.0
        self.armed = False
        self.arm_since: float | None = None
        self.force_armed = False
        self.last_hand_ms = 0.0
        self.last_fire_ms = 0.0
        self.fired_latch: str | None = None
        self.ramp_active = False
        self.ramp_accum_ms = 0.0
        self._last_ramp_ms = 0.0
        self._pending_ramp_ticks = 0

        # rotary dial state
        self.dial_active = False
        self.dial_angle = 0.0
        self.dial_accum = 0.0
        self.dial_degrees = 0.0
        self._dial_grip_frames = 0
        self._dial_release_ms = 0.0
        self._pending_dial_ticks = 0

        # swipe tracking: (timestamp_ms, palm_x, palm_y)
        self._path: deque[tuple[float, float, float]] = deque(maxlen=32)
        self._swipe_cooldown_until = 0.0
        self._pose_suppress_until = 0.0
        self.chords = ChordDetector(settings)

    # ------------------------------------------------------------------ #

    def set_armed(self, armed: bool, source: str = "manual") -> None:
        self.armed = armed
        self.force_armed = armed
        if not armed:
            self.arm_since = None

    def _disarm(self) -> None:
        self.armed = False
        self.arm_since = None
        self.force_armed = False

    # ------------------------------------------------------------------ #

    def update(self, hands: list[Hand], now_ms: float) -> EngineState:
        state = EngineState(hands=hands, arm_mode=self.s.get("engine.arm_mode", "pose"))
        threshold = float(self.s.get("engine.pose_threshold", 0.55))
        max_dist = float(self.s.get("detection.max_distance_m", 2.0))
        min_dist = float(self.s.get("detection.min_distance_m", 0.2))
        depth_gating = bool(self.s.get("engine.depth_gating", True))

        hand = self._pick_hand(hands)
        state.primary = hand

        if hand is None:
            self.ramp_active = False
            self.ramp_accum_ms = 0.0
            self._last_ramp_ms = 0.0
            self._path.clear()
            self._push_history(None)
            self._update_stability(now_ms, threshold)
            state.note = "No hand"
            if self.armed and not self.force_armed:
                if now_ms - self.last_hand_ms > float(self.s.get("engine.auto_disarm_ms", 6000)):
                    self._disarm()
                    state.note = "Auto-disarmed (no hand)"
            state.armed = self.armed
            state.stable_label = self.stable
            state.hold_ms = int(now_ms - self.stable_since) if self.stable else 0
            return state

        self.last_hand_ms = now_ms
        state.distance_m = hand.palm_depth_m
        features = extract_features(hand)
        state.features = features

        if features is None or features.scale < 18.0:
            state.note = "Hand too small / unclear"
            state.gated = True
            self._push_history(None)
            self._update_stability(now_ms, threshold)
            state.armed = self.armed
            return state

        if depth_gating and hand.palm_depth_m is not None:
            if not (min_dist <= hand.palm_depth_m <= max_dist):
                state.note = f"Hand outside range ({hand.palm_depth_m:.2f} m)"
                state.gated = True
                self._push_history(None)
                self._update_stability(now_ms, threshold)
                state.armed = self.armed
                return state

        scores = score_poses(features)
        state.scores = scores

        # Learned hand shapes become extra scored poses, so they flow through
        # the same stability, arming and hold logic as the built-ins.
        custom_gestures = self.s.custom_gestures
        if custom_gestures:
            sample = shape_descriptor(hand)
            for learned in custom_gestures:
                template = learned.get("template")
                if template is None:
                    continue
                value = match_score(template, sample)
                if value > 0.0:
                    scores[f"custom:{learned.get('id')}"] = value

        # Gestures switched off in Tuning can never win. Applied after custom
        # gestures are scored, and the arming pose is exempt so the app cannot
        # be locked out of arming itself.
        arm_pose = self.s.get("engine.arm_pose", "rock")
        for gesture_id in self.s.disabled_gestures:
            if gesture_id != arm_pose:
                scores.pop(gesture_id, None)
        # Track the palm for swipe detection. A large jump means the dominant
        # hand changed (e.g. a second hand came up), not a swipe - start over.
        palm_x, palm_y = hand.px[9][0], hand.px[9][1]
        if self._path:
            _, last_x, last_y = self._path[-1]
            if math.hypot(palm_x - last_x, palm_y - last_y) > 1.2 * max(1.0, features.scale):
                self._path.clear()
        self._path.append((now_ms, palm_x, palm_y))

        # ---- point-and-pinch cursor ---------------------------------- #
        # Only an extended index activates the pointer, so the other gestures
        # keep working while cursor mode is on.
        if bool(self.s.get("cursor.enabled", False)):
            others = max(features.ext["middle"], features.ext["ring"], features.ext["pinky"])
            if features.ext["index"] > 0.60 and others < 0.45:
                state.pointer = (hand.landmarks[8][0], hand.landmarks[8][1])
                state.pointer_pinch_ratio = features.pinch_ratio
                state.pointer_middle_pinch = features.middle_pinch_ratio
                state.pointer_pinch = features.pinch_ratio < 0.45
        label, conf = max(scores.items(), key=lambda kv: kv[1])
        if conf < threshold:
            label, conf = None, conf if label else 0.0
        state.label = label
        state.confidence = conf

        fired: list[str] = []
        self._push_history(label)
        self._update_stability(now_ms, threshold)
        state.stable_label = self.stable

        # Peace sign while cursor mode is on becomes scroll instead of a button.
        if bool(self.s.get("cursor.enabled", False)) and self.stable == "peace":
            state.pointer_scroll_mode = True
            state.pointer_scroll_y = hand.landmarks[8][1]

        if self.stable and self.stable_since:
            state.hold_ms = int(now_ms - self.stable_since)
        elif self.stable:
            state.hold_ms = 0

        # ---- arming -------------------------------------------------- #
        arm_mode = state.arm_mode
        arm_pose = self.s.get("engine.arm_pose", "open_palm")
        arm_hold = float(self.s.get("engine.arm_hold_ms", 550))

        if arm_mode == "always" or self.force_armed:
            self.armed = True
            state.arm_progress = 1.0
        elif arm_mode == "pose":
            if self.stable == arm_pose:
                if self.arm_since is None:
                    self.arm_since = now_ms
                progress = (now_ms - self.arm_since) / max(1.0, arm_hold)
                state.arm_progress = _clamp(progress)
                if progress >= 1.0 and not self.armed:
                    self.armed = True
                    state.note = "Armed"
            else:
                self.arm_since = None
                state.arm_progress = 0.0

        if self.armed and not self.force_armed and arm_mode == "pose":
            if now_ms - self.last_hand_ms > float(self.s.get("engine.auto_disarm_ms", 6000)):
                self._disarm()
                state.note = "Auto-disarmed"

        state.armed = self.armed

        # ---- swipes --------------------------------------------------- #
        swipe = self._detect_swipe(state, now_ms, features.scale)
        if swipe:
            fired.append(swipe)
            # A swipe is a deliberate motion, so don't also fire the pose that
            # was held while the hand moved.
            self.fired_latch = self.stable
            self._pose_suppress_until = now_ms + 260.0
            self._path.clear()

        # ---- two-hand chords ----------------------------------------- #
        chord = self.chords.update(hands, now_ms, threshold) if self.armed else None
        if not self.armed:
            self.chords.reset()
        if chord:
            fired.append(chord)
            self.fired_latch = self.stable
            self._pose_suppress_until = now_ms + 300.0

        # ---- rotary dial (pinch a knob, turn the wrist) --------------- #
        state.dial_active = False
        dial_enabled = bool(self.s.get("engine.dial_enabled", True))
        grip = dial_enabled and self.armed and self._is_dial_grip(features)
        self._dial_grip_frames = self._dial_grip_frames + 1 if grip else 0

        if self._dial_grip_frames >= 3:
            vx = hand.px[PINKY_MCP][0] - hand.px[5][0]
            vy = hand.px[PINKY_MCP][1] - hand.px[5][1]
            roll = math.degrees(math.atan2(vy, vx))
            if not self.dial_active:
                self.dial_active = True
                self.dial_angle = roll
                self.dial_accum = 0.0
                self.dial_degrees = 0.0
            else:
                delta = ((roll - self.dial_angle + 180.0) % 360.0) - 180.0
                self.dial_angle = roll
                # ignore sub-degree jitter and implausible jumps (tracking glitch)
                if 0.5 <= abs(delta) <= 40.0:
                    invert = bool(self.s.get("engine.dial_invert", False))
                    self.dial_accum += -delta if invert else delta
                    self.dial_degrees += -delta if invert else delta
                    step = max(1.0, float(self.s.get("engine.dial_degrees_per_step", 6.0)))
                    ticks = int(abs(self.dial_accum) / step)
                    if ticks:
                        direction = 1 if self.dial_accum > 0 else -1
                        self._pending_dial_ticks += direction * min(ticks, 5)
                        self.dial_accum -= direction * ticks * step
        else:
            if self.dial_active:
                self._dial_release_ms = now_ms
            self.dial_active = False
            self.dial_accum = 0.0

        state.dial_active = self.dial_active
        state.dial_degrees = self.dial_degrees
        dial_guard = self.dial_active or (now_ms - self._dial_release_ms) < 320.0

        # ---- firing -------------------------------------------------- #
        cooldown = float(self.s.get("engine.cooldown_ms", 450))
        fire_hold = float(self.s.get("engine.fire_hold_ms", 400))
        if self.stable != self.fired_latch:
            self.fired_latch = None

        bound_action = self.s.binding_for(self.stable) if self.stable else None
        if (
            self.armed
            and self.stable
            and not dial_guard
            and not state.pointer_scroll_mode
            and now_ms >= self._pose_suppress_until
            and state.pointer is None
            and bound_action not in (None, "none")
            and bound_action not in RAMP_ACTIONS
            and self.fired_latch != self.stable
            and state.hold_ms >= fire_hold
            and (now_ms - self.last_fire_ms) >= cooldown
        ):
            if not (arm_mode == "pose" and self.stable == arm_pose):
                fired.append(self.stable)
                self.fired_latch = self.stable
                self.last_fire_ms = now_ms

        # ---- continuous ramp ----------------------------------------- #
        # Only gestures bound to a repeatable action ramp, so removing the
        # volume binding genuinely stops the volume from changing.
        ramp_hold = float(self.s.get("engine.volume_hold_ms", 300))
        self.ramp_active = bool(
            not dial_guard
            and self.armed
            and self.stable
            and state.pointer is None
            and bound_action in RAMP_ACTIONS
            and state.hold_ms >= ramp_hold
        )

        if self.ramp_active:
            interval = max(30.0, float(self.s.get("engine.volume_ramp_interval_ms", 110)))
            if self._last_ramp_ms == 0.0:
                self._last_ramp_ms = now_ms
            elapsed = now_ms - self._last_ramp_ms
            self._last_ramp_ms = now_ms
            self.ramp_accum_ms += max(0.0, elapsed)
            while self.ramp_accum_ms >= interval:
                self.ramp_accum_ms -= interval
                self._pending_ramp_ticks = min(6, self._pending_ramp_ticks + 1)
        else:
            self.ramp_accum_ms = 0.0
            self._last_ramp_ms = 0.0

        state.ramp_active = self.ramp_active
        state.fired = fired

        # Arm-pose keeps the latch so it never fires an action.
        if fired and state.note == "":
            state.note = "Fired"
        return state

    # ------------------------------------------------------------------ #

    def take_ramp_ticks(self) -> int:
        n = self._pending_ramp_ticks
        self._pending_ramp_ticks = 0
        return n

    def take_dial_ticks(self) -> int:
        n = self._pending_dial_ticks
        self._pending_dial_ticks = 0
        return n

    def _detect_swipe(self, state: EngineState, now_ms: float, hand_scale: float) -> str | None:
        """Directional swipe from palm-centre displacement over a short window.

        Everything is measured in pixels so diagonals behave the way they look,
        and the distance threshold is scaled by hand size so it works at any
        range from the camera.
        """
        if not bool(self.s.get("engine.swipe_enabled", True)):
            return None
        if not self.armed or state.pointer is not None:
            return None

        required = self.s.get("engine.swipe_pose", "open_palm")
        if required and self.stable != required:
            return None
        if now_ms < self._swipe_cooldown_until:
            return None

        window = float(self.s.get("engine.swipe_window_ms", 320))
        samples = [p for p in self._path if now_ms - p[0] <= window]
        if len(samples) < 6:
            return None

        _, x0, y0 = samples[0]
        _, x1, y1 = samples[-1]
        dx, dy = x1 - x0, y1 - y0
        minimum = float(self.s.get("engine.swipe_min_distance", 1.3)) * max(1.0, hand_scale)
        if math.hypot(dx, dy) < minimum:
            return None

        # Require a clearly dominant axis so diagonals do nothing.
        if abs(dx) >= abs(dy) * 1.4:
            direction = "swipe_right" if dx > 0 else "swipe_left"
        elif abs(dy) >= abs(dx) * 1.4:
            direction = "swipe_down" if dy > 0 else "swipe_up"
        else:
            return None

        self._swipe_cooldown_until = now_ms + float(self.s.get("engine.swipe_cooldown_ms", 600))
        return direction

    def _is_dial_grip(self, f: Features) -> bool:
        """Thumb and index pinched together with the rest of the hand closed.

        Distinct from `ok_sign` (other fingers up) and from `fist` (no pinch),
        so grabbing the dial does not fire anything else. The thumb's own
        extension score is deliberately ignored: pinching tucks the tip into the
        palm, which the normal thumb rule reads as "not extended".
        """
        e = f.ext
        closed = min(1.0 - e["middle"], 1.0 - e["ring"], 1.0 - e["pinky"])
        return f.pinch_ratio < 0.45 and closed > 0.45 and e["index"] < 0.85

    def _pick_hand(self, hands: list[Hand]) -> Hand | None:
        if not hands:
            return None
        return max(hands, key=lambda h: h.scale_px)

    def _push_history(self, label: str | None) -> None:
        self.history.append(label)

    def _update_stability(self, now_ms: float, threshold: float) -> None:
        if not self.history:
            return
        counts: dict[str, int] = {}
        for item in self.history:
            if item is None:
                continue
            counts[item] = counts.get(item, 0) + 1
        if not counts:
            self._set_stable(None, 0.0, now_ms)
            return
        label, count = max(counts.items(), key=lambda kv: kv[1])
        needed = math.ceil(len(self.history) * 0.6)
        if count >= needed:
            self._set_stable(label, count / len(self.history), now_ms)
        else:
            self._set_stable(None, 0.0, now_ms)

    def _set_stable(self, label: str | None, conf: float, now_ms: float) -> None:
        if label != self.stable:
            self.stable = label
            self.stable_conf = conf
            self.stable_since = now_ms
            self.volume_accum_ms = 0.0
        else:
            self.stable_conf = conf
