"""Cut the labelled gaze windows (slide "Trigger point").

    python build_windows.py                     # all sessions in data/
    python build_windows.py data/P01_...        # one session

Confused    : the gaze from 5 s to 1 s before each C press (the last second is
              dropped: it holds the eye movement of pressing). 4 s long.
Not confused: one window of the same length per paragraph without a press,
              ending at a random point at least 5 s after the paragraph appeared.
Both kinds have the same length, so length cannot give the label away.
Practice paragraphs are left out. Presses the reader later marked as "pressed by
mistake" are kept but flagged (confirmed = no), so you can drop them.

Writes windows.csv (one row per window, with the dominant text line) and
window_gaze.csv (the gaze samples of every window) next to each session.
Features (fixations, regressions...) are the next step; gaze_core.py has the
fixation detector.
"""
import csv
import glob
import json
import os
import random
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from study import config as C  # noqa: E402


def rows(folder, name):
    with open(os.path.join(folder, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def session_folders(folder):
    """This folder plus the other parts of the same session (run_session.py --resume links them)."""
    def first_part(f):
        p = os.path.join(f, "meta.json")
        m = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        return m.get("first_part", os.path.basename(os.path.normpath(f)))
    root = first_part(folder)
    parent = os.path.dirname(os.path.normpath(folder))
    return [os.path.dirname(p) for p in sorted(glob.glob(os.path.join(parent, "*", "meta.json")))
            if first_part(os.path.dirname(p)) == root]


def build(folder):
    gaze = [(float(r["t"]), float(r["x"]), float(r["y"])) for r in rows(folder, "gaze.csv") if r["found"] == "1"]
    trials = [t for t in rows(folder, "trials.csv") if t["phase"] == "main"]
    presses = rows(folder, "presses.csv")
    words = rows(folder, "layout_words.csv")
    conf = {}
    for f in session_folders(folder):  # a resumed session confirms all its presses in the last part
        if os.path.exists(os.path.join(f, "confirmations.csv")):
            conf.update({c["trial"]: c["confused"] for c in rows(f, "confirmations.csv")})
    bands = {}
    for w in words:
        bands.setdefault(w["trial"], {})[int(w["line"])] = (float(w["band_y0"]), float(w["band_y1"]))
    rng = random.Random(os.path.basename(folder))
    pid = os.path.basename(folder).split("_")[0]
    meta_path = os.path.join(folder, "meta.json")
    part = json.load(open(meta_path, encoding="utf-8")).get("part", 1) if os.path.exists(meta_path) else 1
    wid_prefix = pid if part == 1 else f"{pid}-part{part}"  # a resumed session: window ids stay unique
    wins = []
    by_trial = {t["trial"]: t for t in trials}
    for p in presses:
        t = by_trial.get(p["trial"])
        if not t:
            continue
        end = float(p["t"]) - C.DROP_BEFORE_PRESS_S
        wins.append(dict(label=1, trial=t, end=end, press_t=float(p["t"]), confirmed=conf.get(p["trial"], ""),
                         line_at_press=p["line_under_gaze"]))
    for t in trials:
        if int(t["n_presses"]) == 0:
            on, off = float(t["on_t"]), float(t["off_t"])
            if off - on >= C.WINDOW_S + 0.5:
                end = rng.uniform(on + C.WINDOW_S, off)
                wins.append(dict(label=0, trial=t, end=end, press_t="", confirmed="", line_at_press=""))
    out, samples = [], []
    for i, w in enumerate(wins, start=1):
        t = w["trial"]
        start = max(w["end"] - (C.WINDOW_S - C.DROP_BEFORE_PRESS_S), float(t["on_t"]))
        g = [s for s in gaze if start <= s[0] <= w["end"]]
        lines = []
        for (gt, x, y) in g:
            for li, (y0, y1) in bands.get(t["trial"], {}).items():
                if y0 <= y < y1:
                    lines.append(li)
        dom = Counter(lines).most_common(1)[0][0] if lines else ""
        wid = f"{wid_prefix}-W{i:03d}"
        out.append({"window_id": wid, "participant": pid, "trial": t["trial"], "item_id": t["item_id"],
                    "level": t["level"], "label": w["label"], "confirmed": w["confirmed"],
                    "t_start": f"{start:.4f}", "t_end": f"{w['end']:.4f}", "press_t": w["press_t"],
                    "duration_s": round(w["end"] - start, 3), "n_samples": len(g),
                    # False when the press came less than 5 s after the paragraph appeared,
                    # so the window is cut short at the paragraph onset
                    "full_length": int(w["end"] - start >= C.WINDOW_S - C.DROP_BEFORE_PRESS_S - 0.01),
                    "dominant_line": dom, "line_at_press": w["line_at_press"]})
        samples += [{"window_id": wid, "t": f"{gt:.4f}", "x": x, "y": y} for gt, x, y in g]
    for name, data in (("windows.csv", out), ("window_gaze.csv", samples)):
        with open(os.path.join(folder, name), "w", newline="", encoding="utf-8") as f:
            if data:
                w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
                w.writeheader()
                w.writerows(data)
    pos = sum(o["label"] for o in out)
    print(f"{os.path.basename(folder)}: {pos} confused, {len(out) - pos} not-confused windows")
    return out


if __name__ == "__main__":
    folders = [os.path.normpath(a) for a in sys.argv[1:]] or sorted(
        os.path.dirname(p) for p in glob.glob(os.path.join(HERE, "data", "*", "meta.json")))
    allw = []
    for f in folders:
        allw += build(f)
    if len(folders) > 1:
        with open(os.path.join(HERE, "data", "all_windows.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(allw[0].keys()))
            w.writeheader()
            w.writerows(allw)
        print(f"all sessions -> data/all_windows.csv ({len(allw)} windows)")
