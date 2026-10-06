"""Quality check for a recorded session - run it right after collect.py.

    python check_session.py                      # newest folder in recordings/
    python check_session.py recordings/P01_T01_20261101-101500

Prints PASS / WARN / FAIL per check and saves them as qc.json in the session
folder. FAIL = re-record (after recalibrating); WARN = note it in the session
log and decide. Thresholds are the constants below - change them in one place.
"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

from gaze_core import MAX_SAMPLE_GAP
from sessions import RECORDINGS

MIN_DURATION_S = 60
GAZE_HZ_WARN, GAZE_HZ_FAIL = 20, 10
BUBBLE_FOUND_WARN, BUBBLE_FOUND_FAIL = 0.75, 0.50
LOST_TIME_WARN, LOST_TIME_FAIL = 0.10, 0.25     # share of the session in gaps > MAX_SAMPLE_GAP
FIX_IN_AOI_WARN, FIX_IN_AOI_FAIL = 0.80, 0.60   # low = calibration drift or wrong AOIs
AOI_LINES_RANGE = (5, 35)
EDGE_PX = 40                                     # AOIs this close to top/bottom = browser bar / taskbar


def check(folder):
    meta = json.load(open(os.path.join(folder, "meta.json")))
    gaze = pd.read_csv(os.path.join(folder, "gaze.csv"))
    fix = pd.read_csv(os.path.join(folder, "fixations.csv"), keep_default_na=False)  # keep "None" as text
    clicks = pd.read_csv(os.path.join(folder, "clicks.csv"))
    aoi = pd.read_csv(os.path.join(folder, "aoi.csv"))
    results = []

    def add(name, status, detail):
        results.append({"check": name, "status": status, "detail": detail})

    def grade(value, warn, fail, higher_is_better=True):
        if higher_is_better:
            return "FAIL" if value < fail else "WARN" if value < warn else "PASS"
        return "FAIL" if value > fail else "WARN" if value > warn else "PASS"

    dur = meta["duration_s"]
    add("duration", "PASS" if dur >= MIN_DURATION_S else "WARN", f"{dur:.0f} s")
    add("gaze rate", grade(meta["gaze_hz"], GAZE_HZ_WARN, GAZE_HZ_FAIL),
        f"{meta['gaze_hz']} Hz gaze ({meta['capture_hz']} Hz capture)")
    found = meta["frames_with_bubble"] / max(meta["frames"], 1)
    add("bubble found", grade(found, BUBBLE_FOUND_WARN, BUBBLE_FOUND_FAIL),
        f"{found:.0%} of frames (low: looked away, blinks, bubble off, calibration lost)")

    gaps = np.diff(gaze.t.to_numpy()) if len(gaze) > 1 else np.array([])
    long_gaps = gaps[gaps > MAX_SAMPLE_GAP]
    lost = long_gaps.sum() / dur if dur else 1.0
    add("tracking lost", grade(lost, LOST_TIME_WARN, LOST_TIME_FAIL, higher_is_better=False),
        f"{lost:.0%} of the session in {len(long_gaps)} gaps > {MAX_SAMPLE_GAP} s"
        + (f", longest {long_gaps.max():.1f} s" if len(long_gaps) else ""))

    in_aoi = (fix.aoi != "None").mean() if len(fix) else 0.0
    add("fixations on text", grade(in_aoi, FIX_IN_AOI_WARN, FIX_IN_AOI_FAIL),
        f"{in_aoi:.0%} of {len(fix)} fixations inside an AOI line")

    n_aoi = len(aoi)
    edge = int(((aoi.y1 < EDGE_PX) | (aoi.y2 > meta["screen_px"][1] - EDGE_PX)).sum())
    ok_range = AOI_LINES_RANGE[0] <= n_aoi <= AOI_LINES_RANGE[1]
    add("AOIs", "PASS" if ok_range and edge == 0 else "WARN",
        f"{n_aoi} lines, {edge} touching the top/bottom edge - open aoi_debug.png to check")

    if len(clicks) == 0:
        add("clicks", "WARN", "no confusion clicks - session gives no positive labels")
    else:
        t0, t1 = gaze.t.min(), gaze.t.max()
        outside = int(((clicks.t < t0) | (clicks.t > t1)).sum())
        stale = int((pd.to_numeric(clicks.gaze_age_s, errors="coerce") > 1.0).sum())
        add("clicks", "WARN" if outside or stale else "PASS",
            f"{len(clicks)} clicks, {outside} outside the gaze recording, {stale} with gaze older than 1 s")

    scale = meta.get("display_scale_percent")
    add("display scaling", "PASS" if scale in (100, None) else "WARN", f"{scale}% (protocol: 100%)")

    others = [json.load(open(p)) for p in glob.glob(os.path.join(RECORDINGS, "*", "meta.json"))
              if os.path.dirname(p) != os.path.normpath(folder)]
    sizes = {tuple(m["screen_px"]) for m in others}
    same = not sizes or sizes == {tuple(meta["screen_px"])}
    add("same screen as other sessions", "PASS" if same else "WARN",
        f"{meta['screen_px']}" + ("" if same else f" vs {sorted(sizes)}"))
    return meta, results


if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder = os.path.normpath(sys.argv[1])
    else:
        folders = sorted(glob.glob(os.path.join(RECORDINGS, "*", "meta.json")), key=os.path.getmtime)
        if not folders:
            sys.exit("no sessions in recordings/")
        folder = os.path.dirname(folders[-1])

    meta, results = check(folder)
    print(f"Session {meta['session']}  (participant {meta['participant']}, text {meta['text']})")
    for r in results:
        print(f"  [{r['status']:<4}] {r['check']:<30} {r['detail']}")
    statuses = {r["status"] for r in results}
    overall = "FAIL" if "FAIL" in statuses else "WARN" if "WARN" in statuses else "PASS"
    print(f"Overall: {overall}" + ("  -> recalibrate and re-record this text" if overall == "FAIL" else ""))
    with open(os.path.join(folder, "qc.json"), "w") as f:
        json.dump({"overall": overall, "checks": results}, f, indent=2)
