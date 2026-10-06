"""Where each recorded session's raw files are.

The previous intern's 20 sessions (data_logs/, 11-13 July 2025) all wrote their
fixations into ONE appended data_logs/fixation.csv, but kept per-session raw
gaze, click and AOI files - those are what we rebuild from. Each session was a
different page of text, so session id doubles as text id for now. Who read
them is not recorded and nobody knows (possibly one reader): participant
"unknown".

New sessions recorded with collect.py are found automatically in recordings/.
"group" says which dataset a session belongs to: "old2025" (the 20 sessions of
Experiments 1-2), "repro" (s21) or "new".
"""
import datetime
import glob
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data_logs")
RECORDINGS = os.path.join(HERE, "recordings")


def _old_session(n):
    aoi = f"aoi_lines_{n}.csv" if n >= 11 else ("aoi_lines.csv" if n <= 2 else f"aoi_lines{n}.csv")
    return {
        "session": f"s{n:02d}", "group": "old2025", "participant": "unknown", "text": f"s{n:02d}",
        "gaze": os.path.join(D, "gaze.csv" if n == 1 else f"gaze_{n}.csv"),
        "clicks": os.path.join(D, "popup_yes_clicks", f"yes_click_log_{n}.csv"),
        "aoi": os.path.join(D, aoi),
    }


SESSIONS = [_old_session(n) for n in range(1, 21)] + [
    {   # first reproduction run on the new PC (README stages 3-7), 2026-10-06
        "session": "s21", "group": "repro", "participant": "unknown", "text": "s21",
        "gaze": os.path.join(HERE, "demo_video_logs", "gaze.csv"),
        "clicks": os.path.join(HERE, "demo_video_logs", "popup_yes_clicks", "yes_click_log1.csv"),
        "aoi": os.path.join(HERE, "demo_video_logs", "aoi_lines_session1.csv"),
    },
]

for _meta_path in sorted(glob.glob(os.path.join(RECORDINGS, "*", "meta.json"))):
    _dir = os.path.dirname(_meta_path)
    with open(_meta_path) as _f:
        _meta = json.load(_f)
    SESSIONS.append({
        "session": _meta["session"], "group": "new",
        "participant": _meta["participant"], "text": _meta["text"],
        "gaze": os.path.join(_dir, "gaze.csv"),
        "clicks": os.path.join(_dir, "clicks.csv"),
        "aoi": os.path.join(_dir, "aoi.csv"),
    })


def to_seconds(timestamps):
    """'YYYY-mm-dd HH:MM:SS.ffffff' local-time strings -> float seconds since epoch.

    The capture scripts write local wall-clock time, so the strings are read as
    local time - this matches the true epoch 't' column collect.py also writes.
    (Reading them as UTC put every time 5.5 h off in India.) Done per value with
    datetime, not pandas, whose datetime unit (us/ns) varies between versions.
    """
    return np.array([datetime.datetime.fromisoformat(str(ts)).timestamp() for ts in timestamps])


def load_aois(path):
    a = pd.read_csv(path)
    return {r.AOI_ID: (r.x1, r.y1, r.x2, r.y2) for r in a.itertuples()}


def aoi_of(x, y, aois):
    return next((k for k, (x1, y1, x2, y2) in aois.items() if x1 <= x <= x2 and y1 <= y <= y2), "None")
