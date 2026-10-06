"""Check that gaze_core.FixationDetector reproduces what the original cnn.py logged.

Runs the detector over the 20 old sessions' raw gaze files and matches the
result against data_logs/fixation.csv (the fixations cnn.py wrote live).
cnn.py reset on every frame without a bubble; gaze.csv only shows those as a
longer time gap, so for this check the gap limit is set to ~1.7 frame intervals
(the corrected pipeline uses gaze_core.MAX_SAMPLE_GAP instead).

    python validate_gaze_core.py
"""
import numpy as np
import pandas as pd

from gaze_core import fixations_from_gaze
from sessions import D, SESSIONS, to_seconds

LEGACY_GAP_FRAMES = 1.7

old = pd.read_csv(f"{D}/fixation.csv", usecols=range(11))  # first 11 cols are the same in every row
old["start_s"] = to_seconds(old.start_time)

n_old = n_new = n_found = n_same = 0
for s in (s for s in SESSIONS if s["group"] == "old2025"):
    g = pd.read_csv(s["gaze"])
    t = to_seconds(g.timestamp)
    new = pd.DataFrame(fixations_from_gaze(t, g.gaze_x, g.gaze_y,
                                           max_gap=LEGACY_GAP_FRAMES * np.median(np.diff(t))))
    o = old[(old.start_s >= t.min()) & (old.start_s <= t.max())]
    n_old += len(o)
    n_new += len(new)
    for r in o.itertuples():
        d = np.abs(new.start_ts.to_numpy() - r.start_s)
        if d.min() < 0.01:
            n_found += 1
            k = d.argmin()
            n_same += (new.fix_x[k] == r.fix_x and new.fix_y[k] == r.fix_y
                       and abs(new.duration[k] - r.duration) < 0.002)

print(f"original cnn.py fixations : {n_old}")
print(f"rebuilt by gaze_core      : {n_new}")
print(f"original ones reproduced  : {n_found} ({n_found / n_old:.1%}), "
      f"identical position+duration: {n_same}")
