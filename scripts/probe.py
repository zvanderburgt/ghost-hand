"""Headless probe: verify camera + hand tracking without any UI.

    python scripts/probe.py [--frames 90] [--save]

Prints per-frame scores for the detected hand and writes debug/probe.png so the
landmarks can be eyeballed even without the app running.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gr.actions import ActionBus  # noqa: E402
from gr.camera import CameraError, RealSenseCamera  # noqa: E402
from gr.config import DEBUG_DIR, GESTURES, Settings  # noqa: E402
from gr.draw import draw_hand, draw_hud  # noqa: E402
from gr.gestures import GestureEngine  # noqa: E402
from gr.hands import HandTracker  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=90)
    ap.add_argument("--save", action="store_true", help="write debug/probe.png")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    s = Settings.load()
    cam = RealSenseCamera(
        color_size=(s.get("camera.color_width"), s.get("camera.color_height")),
        depth_size=(s.get("camera.depth_width"), s.get("camera.depth_height")),
        fps=s.get("camera.fps"),
        mirror=s.get("camera.mirror"),
    )

    print("Starting camera...")
    try:
        cam.start()
    except CameraError as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"Camera: {cam.intrinsics_note}, serial={cam.serial}")

    probe = {"fn": None}
    tracker = HandTracker(
        max_hands=s.get("detection.max_hands"),
        min_detection=s.get("detection.min_hand_detection_confidence"),
        min_presence=s.get("detection.min_hand_presence_confidence"),
        min_tracking=s.get("detection.min_tracking_confidence"),
        depth_probe=lambda x, y: probe["fn"](x, y) if probe["fn"] else None,
    )
    engine = GestureEngine(s)
    bus = ActionBus(s, log=print)

    print(f"Model loaded. Tracking {args.frames} frames...\n")

    detected = 0
    best_snapshot = None
    best_hand = None
    best_label = None
    t_start = time.perf_counter()

    try:
        for i in range(args.frames):
            frame = cam.poll()
            if frame is None:
                print("frame timeout")
                continue
            probe["fn"] = lambda x, y: frame.depth_at(x, y, radius=6)

            hands = tracker.process(frame.color, frame.timestamp_ms)
            probe["fn"] = None
            state = engine.update(hands, time.perf_counter() * 1000)

            if hands:
                detected += 1
                hand = max(hands, key=lambda h: h.scale_px)
                if best_hand is None or hand.scale_px > best_hand.scale_px:
                    best_hand = hand
                    best_label = state.stable_label or state.label
                    img = frame.color.copy()
                    if hand is not None:
                        draw_hand(img, hand, best_label)
                    best_snapshot = img

            if not args.quiet and (i % 10 == 0 or state.fired):
                lbl = state.stable_label or state.label or "-"
                conf = state.stable_confidence if state.stable_label else state.confidence
                top = sorted(state.scores.items(), key=lambda kv: -kv[1])[:3]
                top_s = "  ".join(f"{k}={v:.2f}" for k, v in top)
                print(
                    f"[{i:03d}] hands={len(hands)} label={lbl:<12} conf={conf:.2f} "
                    f"dist={state.distance_m if state.distance_m is None else round(state.distance_m, 2)} "
                    f"armed={state.armed} | {top_s}"
                )
                if state.fired:
                    gid = state.fired[0]
                    action = s.binding_for(gid)
                    print(f"        >>> FIRED {GESTURES[gid]['name']} -> {s.action_label(action)}")
                    bus.fire(action or "none")
    finally:
        elapsed = time.perf_counter() - t_start
        cam.stop()
        tracker.close()

    fps = args.frames / max(elapsed, 1e-6)
    print(f"\nFrames with a hand: {detected}/{args.frames}  (~{fps:.1f} fps loop)")
    print(f"Inference: {tracker.inference_ms:.1f} ms/frame")

    if args.save:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        out = DEBUG_DIR / "probe.png"
        if best_snapshot is None:
            frame = None
            print("No hand seen - nothing to save.")
        else:
            cv2.putText(best_snapshot, f"best hand  scale={best_hand.scale_px:.0f}px",
                        (12, best_snapshot.shape[0] - 16),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.imwrite(str(out), best_snapshot)
            print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
