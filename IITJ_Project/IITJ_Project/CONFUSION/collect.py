"""Record one reading session: Ghost-bubble gaze, fixations and confusion clicks.

Replaces cnn.py (which contained no CNN). Fixes from README §10.9 / §11:
  * one new folder per session, named participant_text_datetime - nothing is
    ever appended to an older session's files
  * the AOIs are captured inside the session (with a countdown), so the AOI
    file always belongs to the recording
  * fixations come from gaze_core (corrected regression / saccade timing,
    blink-tolerant), the same code used to rebuild the old sessions
  * leaner capture loop: no fixed sleep and no per-frame printing (~2x the
    sampling rate of cnn.py); the achieved rate is saved in meta.json
  * every row carries t = seconds since epoch, so no timestamp parsing is needed
  * stop key is Ctrl+Q (a plain 'q' typed anywhere used to end the recording)
Scanpath PNGs are no longer drawn live; they can be rendered from gaze.csv.

    python collect.py --participant P01 --text T01
    python collect.py --participant P01 --text T01 --aoi test_data_logs/aoi_lines_test2.csv

Then: page on screen and calibrated, ESC to start, click "Yes (Confused)" when
confused, Ctrl+Q to stop. Output: recordings/<participant>_<text>_<datetime>/
"""
import argparse
import csv
import ctypes
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import tkinter as tk

import cv2
import keyboard
import numpy as np
import pyautogui

import gaze_core
from aoi import capture_aois
from gaze_core import FIXATION_COLUMNS, FixationDetector, detect_green_bubble
from sessions import aoi_of, load_aois

HERE = os.path.dirname(os.path.abspath(__file__))
RECORDINGS = os.path.join(HERE, "recordings")
START_KEY = "esc"
STOP_KEY = "ctrl+q"


def stamp(t):
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S.%f")


def display_scale_percent():
    try:
        return ctypes.windll.shcore.GetScaleFactorForDevice(0)
    except Exception:
        return None


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE,
                              capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--participant", required=True, help="e.g. P01 (no names - keep a separate key)")
    ap.add_argument("--text", required=True, help="e.g. T01, the id of the page being read")
    ap.add_argument("--aoi", help="reuse this AOI csv instead of capturing new AOIs")
    ap.add_argument("--aoi-delay", type=float, default=5, help="countdown before the AOI screenshot")
    ap.add_argument("--notes", default="", help="free text saved in meta.json")
    args = ap.parse_args()

    session_id = f"{args.participant}_{args.text}_{datetime.datetime.now():%Y%m%d-%H%M%S}"
    out = os.path.join(RECORDINGS, session_id)
    os.makedirs(out)  # fails if it exists: never overwrite a session

    if args.aoi:
        shutil.copy(args.aoi, os.path.join(out, "aoi.csv"))
    else:
        capture_aois(args.aoi_delay, os.path.join(out, "aoi.csv"), os.path.join(out, "aoi_debug.png"))
    aois = load_aois(os.path.join(out, "aoi.csv"))

    screen_w, screen_h = pyautogui.size()
    img_h, img_w = np.array(pyautogui.screenshot()).shape[:2]
    sx, sy = screen_w / img_w, screen_h / img_h  # screenshot px -> screen px (differs if scaling != 100%)

    gaze_f = open(os.path.join(out, "gaze.csv"), "w", newline="")
    fix_f = open(os.path.join(out, "fixations.csv"), "w", newline="")
    click_f = open(os.path.join(out, "clicks.csv"), "w", newline="")
    gaze_csv, fix_csv, click_csv = csv.writer(gaze_f), csv.writer(fix_f), csv.writer(click_f)
    gaze_csv.writerow(["gaze_x", "gaze_y", "timestamp", "t"])
    fix_csv.writerow(FIXATION_COLUMNS + ["aoi"])
    click_csv.writerow(["timestamp", "gaze_x", "gaze_y", "AOI_ID", "t", "gaze_age_s"])

    state = {"last_gaze": None, "last_gaze_t": None, "clicks": 0, "recording": False}

    def on_yes():
        if not state["recording"]:
            return
        now = time.time()
        g = state["last_gaze"]
        x, y = g if g else ("", "")
        age = round(now - state["last_gaze_t"], 3) if g else ""
        click_csv.writerow([stamp(now), x, y, aoi_of(x, y, aois) if g else "None", f"{now:.6f}", age])
        click_f.flush()
        state["clicks"] += 1
        status.config(text=f"Recording - {state['clicks']} click(s)")
        print(f"[CLICK] {state['clicks']} at {stamp(now)}")

    root = tk.Tk()
    root.title("Gaze Capture")
    w, h = 220, 120
    root.geometry(f"{w}x{h}+{screen_w - w - 20}+{screen_h - h - 80}")  # bottom-right, above taskbar
    root.configure(bg="white")
    root.attributes("-topmost", True)
    status = tk.Label(root, text=f"Press {START_KEY.upper()} to start", bg="white")
    status.pack(pady=10)
    tk.Button(root, text="Yes (Confused)", width=18, command=on_yes).pack(pady=5)

    print(f"[INFO] session {session_id}")
    print(f"[INFO] {START_KEY.upper()} = start, {STOP_KEY.upper()} = stop")
    while not keyboard.is_pressed(START_KEY):
        if keyboard.is_pressed(STOP_KEY):
            print("[INFO] stopped before starting - nothing recorded")
            root.destroy()
            return
        root.update()
        time.sleep(0.02)

    status.config(text="Recording - 0 click(s)")
    state["recording"] = True
    detector = FixationDetector()
    t_start = time.time()
    frames = found = 0
    try:
        while not keyboard.is_pressed(STOP_KEY):
            frame = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
            now = time.time()
            frames += 1
            pos = detect_green_bubble(frame)
            if pos:
                found += 1
                x, y = int(pos[0] * sx), int(pos[1] * sy)
                state["last_gaze"], state["last_gaze_t"] = (x, y), now
                gaze_csv.writerow([x, y, stamp(now), f"{now:.6f}"])
                fix = detector.add(now, x, y)
                if fix:
                    fix_csv.writerow([fix[c] for c in FIXATION_COLUMNS] + [aoi_of(fix["fix_x"], fix["fix_y"], aois)])
                    fix_f.flush()
            if frames % 100 == 0:
                print(f"\r[REC] {now - t_start:6.1f} s, {frames / (now - t_start):4.1f} frames/s, "
                      f"bubble in {found / frames:.0%}", end="", flush=True)
            root.update()
    except KeyboardInterrupt:
        pass
    finally:
        t_end = time.time()
        root.destroy()
        for f in (gaze_f, fix_f, click_f):
            f.close()

    dur = t_end - t_start
    meta = {
        "session": session_id, "participant": args.participant, "text": args.text, "notes": args.notes,
        "start": stamp(t_start), "end": stamp(t_end), "duration_s": round(dur, 1),
        "frames": frames, "frames_with_bubble": found,
        "capture_hz": round(frames / dur, 1), "gaze_hz": round(found / dur, 1),
        "clicks": state["clicks"], "fixations": len(detector.fixations), "aoi_lines": len(aois),
        "aoi_source": args.aoi or "captured at session start",
        "screen_px": [screen_w, screen_h], "screenshot_px": [img_w, img_h],
        "display_scale_percent": display_scale_percent(),
        "gaze_core": {k: getattr(gaze_core, k) for k in
                      ("GAZE_HOLD_RADIUS", "GAZE_HOLD_TIME", "MAX_SAMPLE_GAP", "LINE_Y_TOLERANCE", "REGRESSION_MIN_DX")},
        "git_commit": git_commit(), "python": sys.version.split()[0], "os": platform.platform(),
    }
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\n[DONE] {dur:.0f} s, gaze {meta['gaze_hz']} Hz (capture {meta['capture_hz']} Hz), "
          f"{meta['fixations']} fixations, {meta['clicks']} clicks -> {out}")


if __name__ == "__main__":
    main()
