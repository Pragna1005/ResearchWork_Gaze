"""Experiment 1 (README §11): label fixations by TIME before a confusion click.

The old label.py marked every fixation that ever landed on a clicked AOI line
as confused, for the whole session (README §10.2) - labelling by place. Here a
fixation is confused iff it overlaps the window [click - W, click] for some
click in the same session. W = 5, 10, 15 s is the sensitivity check; 15 s
matches cnn.py's scanpath segments. The old place-based rule is also applied
to the same fixations (label_aoi_legacy) so the two can be compared.

Reads processed/<session>/fixations.csv (run rebuild_fixations.py first).
Writes processed/<session>/fixations_labeled.csv and processed/label_summary.csv.

    python label.py
"""
import os

import pandas as pd

from sessions import HERE, SESSIONS, to_seconds

WINDOWS = (5, 10, 15)  # seconds before the click
OUT = os.path.join(HERE, "processed")


def time_window_labels(start, end, clicks, w):
    """1 where the fixation [start, end] overlaps any [click - w, click]."""
    lab = pd.Series(0, index=start.index)
    for c in clicks:
        lab[(end >= c - w) & (start <= c)] = 1
    return lab


rows = []
for s in SESSIONS:
    fx = pd.read_csv(os.path.join(OUT, s["session"], "fixations.csv"))
    clicks_df = pd.read_csv(s["clicks"])
    clicks = to_seconds(clicks_df.timestamp)

    for w in WINDOWS:
        fx[f"label_t{w}"] = time_window_labels(fx.start_ts, fx.end_ts, clicks, w)
    clicked_aois = set(clicks_df.AOI_ID.dropna().astype(str)) - {"None"}
    fx["label_aoi_legacy"] = fx.aoi.isin(clicked_aois).astype(int)

    fx.to_csv(os.path.join(OUT, s["session"], "fixations_labeled.csv"), index=False)
    rows.append({"session": s["session"], "clicks": len(clicks), "fixations": len(fx),
                 **{f"pos_t{w}": int(fx[f"label_t{w}"].sum()) for w in WINDOWS},
                 "pos_aoi_legacy": int(fx.label_aoi_legacy.sum())})

summary = pd.DataFrame(rows)
summary.to_csv(os.path.join(OUT, "label_summary.csv"), index=False)
pd.set_option("display.width", 200)
print(summary.to_string(index=False))
n = summary.fixations.sum()
for col in [f"pos_t{w}" for w in WINDOWS] + ["pos_aoi_legacy"]:
    print(f"{col:>15}: {summary[col].sum():4d} / {n} positive ({summary[col].sum() / n:.0%})")
