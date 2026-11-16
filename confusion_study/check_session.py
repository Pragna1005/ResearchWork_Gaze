"""Quality check - run right after each session.

    python check_session.py                 # newest folder in data/
    python check_session.py data/P01_20261110-101500

PASS / WARN / FAIL per check, saved as qc.json in the session folder.
FAIL = the session cannot be used as it is (note it; usually re-run with a new id).
"""
import csv
import glob
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

GAZE_HZ_WARN, GAZE_HZ_FAIL = 20, 10
FOUND_WARN, FOUND_FAIL = 0.75, 0.50
LOST_GAP_S = 0.5
LOST_WARN, LOST_FAIL = 0.10, 0.25
PRESS_LINE_WARN = 0.70        # share of presses where gaze was on a text line
DRIFT_WARN_PX = 60            # median distance between gaze and the start-of-paragraph dot


def read_csv(folder, name):
    p = os.path.join(folder, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check(folder):
    meta = json.load(open(os.path.join(folder, "meta.json"), encoding="utf-8"))
    summary = json.load(open(os.path.join(folder, "summary.json"), encoding="utf-8")) \
        if os.path.exists(os.path.join(folder, "summary.json")) else {}
    gaze = read_csv(folder, "gaze.csv")
    trials = [t for t in read_csv(folder, "trials.csv") if t["phase"] == "main"]
    presses = read_csv(folder, "presses.csv")
    events = read_csv(folder, "events.csv")
    out = []

    def add(name, status, detail):
        out.append({"check": name, "status": status, "detail": detail})

    def grade(v, warn, fail, higher_better=True):
        if higher_better:
            return "FAIL" if v < fail else "WARN" if v < warn else "PASS"
        return "FAIL" if v > fail else "WARN" if v > warn else "PASS"

    plan_path = os.path.join(folder, "plan.json")
    planned = len(json.load(open(plan_path, encoding="utf-8"))["main"]) if os.path.exists(plan_path) else None
    done = meta.get("main_trials_done", 0)
    total = meta.get("main_trials_done_total", done)
    detail = f"{total}" + (f" of {planned}" if planned else "") + " main paragraphs read"
    if meta.get("part", 1) > 1:
        detail += f" ({done} in this part {meta['part']}, which continues {meta.get('resume_of')})"
    resumed_in = [os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(DATA, "*", "meta.json"))
                  if json.load(open(p, encoding="utf-8")).get("resume_of") == os.path.basename(os.path.normpath(folder))]
    if meta.get("completed"):
        status = "PASS"
    elif resumed_in:
        status, detail = "WARN", detail + f" - stopped early, continued in {', '.join(resumed_in)}"
    else:
        status, detail = "FAIL", detail + " - session stopped early (python run_session.py --participant "\
                                          f"{meta['participant']} --resume to continue)"
    add("completed", status, detail)

    if gaze:
        t = [float(r["t"]) for r in gaze]
        found_t = [float(r["t"]) for r in gaze if r["found"] == "1"]
        dur = t[-1] - t[0] if len(t) > 1 else 0
        hz = len(found_t) / dur if dur else 0
        add("gaze rate", grade(hz, GAZE_HZ_WARN, GAZE_HZ_FAIL), f"{hz:.1f} Hz with bubble ({len(t) / dur:.1f} Hz capture)" if dur else "no data")
        share = len(found_t) / len(t)
        add("bubble found", grade(share, FOUND_WARN, FOUND_FAIL), f"{share:.0%} of frames")
        lost = sum(b - a for a, b in zip(found_t, found_t[1:]) if b - a > LOST_GAP_S)
        add("tracking lost", grade(lost / dur if dur else 1, LOST_WARN, LOST_FAIL, False),
            f"{lost / dur:.0%} of the session in gaps > {LOST_GAP_S} s" if dur else "")
    else:
        add("gaze rate", "FAIL", "gaze.csv missing or empty")

    for v in summary.get("validation", []):
        if not v:
            continue
        status = "PASS" if v.get("ok") else "WARN"
        if v.get("mean_abs_dy_px") is None:
            status, detail = "FAIL", "no gaze during the check"
        else:
            detail = (f"mean error {v['mean_error_px']:.0f} px, vertical {v['mean_abs_dy_px']:.0f} px "
                      f"(limit {C_LIMIT(meta):.0f}), {v['dots_with_gaze']}/{v['dots']} dots, attempt {v['attempt']}")
        add(f"calibration check ({v['run']})", status, detail)

    drift = []
    for e in events:
        if e["event"] == "start_marker" and e["detail"]:
            d = json.loads(e["detail"])
            if d.get("gaze"):
                drift.append(((d["gaze"][0] - d["target"][0]) ** 2 + (d["gaze"][1] - d["target"][1]) ** 2) ** 0.5)
    if drift:
        med = statistics.median(drift)
        add("drift (start-of-paragraph dot)", "PASS" if med < DRIFT_WARN_PX else "WARN",
            f"median {med:.0f} px over {len(drift)} paragraphs")

    main_ids = {t["trial"] for t in trials}
    mp = [p for p in presses if p["trial"] in main_ids]
    if not mp:
        add("C presses", "WARN", "no presses in the main part: this reader gives no confused samples")
    else:
        on_line = sum(p["line_under_gaze"] != "" for p in mp) / len(mp)
        by = {}
        for t in trials:
            by.setdefault(t["level"], [0, 0])
            by[t["level"]][0] += 1
            by[t["level"]][1] += int(t["n_presses"]) > 0
        rates = ", ".join(f"{k} {v[1]}/{v[0]}" for k, v in sorted(by.items()))
        add("C presses", "PASS", f"{len(mp)} presses; paragraphs with a press: {rates}")
        add("gaze on a line at press", "PASS" if on_line >= PRESS_LINE_WARN else "WARN",
            f"{on_line:.0%} of presses (low = calibration off or reader looked away)")

    qs = [t for t in trials if t["answer_option"]]
    if qs:
        acc = sum(int(t["answer_correct"]) for t in qs) / len(qs)
        add("comprehension", "PASS" if acc >= 0.5 else "WARN", f"{acc:.0%} correct over {len(qs)} questions (chance 25%)")
    too_fast = [t for t in trials if float(t["reading_s"]) < 0.08 * float(t["n_words"])]
    add("reading speed", "PASS" if len(too_fast) <= 2 else "WARN",
        f"{len(too_fast)} paragraphs read faster than ~750 words/min (skimming or skipping?)")
    if "lextale" in summary:
        add("LexTALE", "PASS", f"{summary['lextale']['score_percent']}%")
    scale = meta.get("display_scale_percent")
    add("display scaling", "PASS" if scale in (100, None) else "WARN", f"{scale}% (must be 100%)")
    others = [json.load(open(p, encoding="utf-8")) for p in glob.glob(os.path.join(DATA, "*", "meta.json"))
              if os.path.dirname(os.path.normpath(p)) != os.path.normpath(folder)]
    sizes = {tuple(m["screen_px"]) for m in others}
    same = not sizes or sizes == {tuple(meta["screen_px"])}
    add("same screen as other sessions", "PASS" if same else "WARN", str(meta["screen_px"]))
    return meta, out


def C_LIMIT(meta):
    return meta["config"]["VALIDATION_MAX_DY_SHARE"] * meta["line_pitch_px"]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        folder = os.path.normpath(sys.argv[1])
    else:
        metas = sorted(glob.glob(os.path.join(DATA, "*", "meta.json")), key=os.path.getmtime)
        if not metas:
            sys.exit("no sessions in data/")
        folder = os.path.dirname(metas[-1])
    meta, res = check(folder)
    print(f"Session {os.path.basename(folder)}  (participant {meta['participant']}, list {meta['list']}, gaze {meta['gaze_source']})")
    for r in res:
        print(f"  [{r['status']:<4}] {r['check']:<36} {r['detail']}")
    st = {r["status"] for r in res}
    overall = "FAIL" if "FAIL" in st else "WARN" if "WARN" in st else "PASS"
    print(f"Overall: {overall}")
    with open(os.path.join(folder, "qc.json"), "w") as f:
        json.dump({"overall": overall, "checks": res}, f, indent=2)
