"""Rebuild corrected per-session fixation files from the raw gaze logs.

For every session in sessions.py, runs gaze_core's fixation detector over the
raw gaze.csv and writes  processed/<session>/fixations.csv  (one file per
session - never appended). Each fixation also gets the AOI line it landed on
(as one 'aoi' column, not one-hot) - kept for analysis, NOT as a model feature.

    python rebuild_fixations.py
"""
import os

import pandas as pd

from gaze_core import FIXATION_COLUMNS, fixations_from_gaze
from sessions import HERE, SESSIONS, aoi_of, load_aois, to_seconds

OUT = os.path.join(HERE, "processed")

summary = []
for s in SESSIONS:
    g = pd.read_csv(s["gaze"])
    t = to_seconds(g.timestamp)
    fx = pd.DataFrame(fixations_from_gaze(t, g.gaze_x, g.gaze_y), columns=FIXATION_COLUMNS)
    aois = load_aois(s["aoi"])
    fx.insert(0, "session", s["session"])
    fx["aoi"] = [aoi_of(x, y, aois) for x, y in zip(fx.fix_x, fx.fix_y)]

    os.makedirs(os.path.join(OUT, s["session"]), exist_ok=True)
    fx.to_csv(os.path.join(OUT, s["session"], "fixations.csv"), index=False)

    dur = t.max() - t.min()
    summary.append({
        "session": s["session"], "minutes": round(dur / 60, 1), "gaze_hz": round(len(g) / dur, 1),
        "fixations": len(fx),
        "regr_legacy": int(fx.regression_flag_legacy.sum()),
        "regr_new": int(fx.regression_flag.sum()),
        "regr_leftward": int((fx.regression_type == "leftward").sum()),
        "regr_upward": int((fx.regression_type == "upward").sum()),
        "sacc_dur_legacy_med": round(fx.saccade_before_duration_legacy.iloc[1:].median(), 3),
        "sacc_dur_new_med": round(fx.saccade_before_duration.iloc[1:].median(), 3),
    })

summary = pd.DataFrame(summary)
summary.to_csv(os.path.join(OUT, "rebuild_summary.csv"), index=False)
pd.set_option("display.width", 200)
print(summary.to_string(index=False))
