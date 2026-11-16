"""Test run_session.py --resume with a scripted participant and simulated gaze.

    python tests/test_resume.py

Everything is written to a temporary folder (not data/).
  A. Stopped during the first calibration check (after questionnaire and LexTALE),
     then resumed: practice runs, questionnaire and LexTALE do not.
  B. Stopped mid-paragraph at trial 5 (with a C press), resumed, stopped again
     mid-paragraph at trial 16, resumed again: three linked parts.
Checks: same plan and order, every paragraph saved exactly once, earlier folders
unchanged, one break, calibration checks, confirmations for the presses of all
parts, unique window ids, check_session status.
"""
import csv
import glob
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
from test_full_session import Participant  # noqa: E402  (also sets short timings, dummy video)

import build_windows  # noqa: E402
import check_session  # noqa: E402
import run_session  # noqa: E402
from study.ui import Abort  # noqa: E402


class Aborter(Participant):
    """Like Participant, but presses Ctrl+Q on the n-th screen with this tag (after a C press if reading)."""

    def __init__(self, tag, n, **kw):
        super().__init__(**kw)
        self.abort_tag, self.n, self.seen = tag, n, 0

    def _plan(self, tag):
        if tag == self.abort_tag:
            self.seen += 1
            if self.seen == self.n:
                return [(0.4, "c"), (0.7, "__abort__")] if tag == "reading" else [(0.0, "__abort__")]
        return super()._plan(tag)

    def keys(self, tag):
        out = super().keys(tag)
        if any(k == "__abort__" for k, _, _ in out):
            raise Abort()
        return out


def csv_rows(folder, name):
    with open(os.path.join(folder, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def meta(folder):
    with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
        return json.load(f)


def fingerprint(folder):
    out = {}
    for p in sorted(glob.glob(os.path.join(folder, "*"))):
        with open(p, "rb") as f:
            out[os.path.basename(p)] = hashlib.sha1(f.read()).hexdigest()
    return out


def run(pid, auto, extra=()):
    return run_session.main(["--participant", pid, "--gaze", "sim", "--size", "1920x1080", *extra], auto=auto)


def check_whole_session(folders, plan):
    # same plan in every part
    for f in folders[1:]:
        with open(os.path.join(f, "plan.json"), encoding="utf-8") as fh:
            assert json.load(fh) == plan, f"plan differs in {f}"
    # every main paragraph saved exactly once, in plan order across the parts
    saved = [r["trial"] for f in folders for r in csv_rows(f, "trials.csv") if r["phase"] == "main"]
    assert saved == [str(t["trial"]) for t in plan["main"]], saved
    # links
    for i, f in enumerate(folders[1:], start=2):
        m = meta(f)
        assert m["part"] == i and m["resume_of"] == os.path.basename(folders[i - 2])
        assert m["first_part"] == os.path.basename(folders[0]) and f.endswith(f"_part{i}")
    last = meta(folders[-1])
    assert last["completed"] and last["main_trials_done_total"] == len(plan["main"])
    # one break, in the part that read trial break_after_trial
    breaks = [f for f in folders for e in csv_rows(f, "events.csv") if e["phase"] == "break" and e["event"] == "start"]
    assert len(breaks) == 1, breaks
    # confirmations (all in the last part) cover the pressed paragraphs of every part
    pressed = {r["trial"] for f in folders for r in csv_rows(f, "trials.csv")
               if r["phase"] == "main" and int(r["n_presses"]) > 0}
    confirmed = [c["trial"] for f in folders for c in csv_rows(f, "confirmations.csv")]
    assert sorted(confirmed, key=int) == sorted(pressed, key=int), (confirmed, pressed)
    # summary of the last part covers the whole session
    with open(os.path.join(folders[-1], "summary.json"), encoding="utf-8") as fh:
        s = json.load(fh)
    assert sum(v["paragraphs"] for v in s["by_level"].values()) == len(plan["main"])
    assert "lextale" in s
    # windows: unique ids, and part-1 presses get their confirmation from the last part
    wins = [w for f in folders for w in build_windows.build(f)]
    assert len({w["window_id"] for w in wins}) == len(wins)
    assert all(w["confirmed"] != "" for w in wins if w["label"] == 1)
    for i, f in enumerate(folders):
        _, res = check_session.check(f)
        st = {r["check"]: r["status"] for r in res}["completed"]
        assert st == ("PASS" if i == len(folders) - 1 else "WARN"), (f, st)
    return s


def scenario_a(tmp):
    print("\n=== A: stopped during the first calibration check")
    pid = "P92"
    f1 = run(pid, Aborter("val_dot", 1))
    assert meta(f1)["aborted"] and os.path.exists(os.path.join(f1, "questionnaire.json"))
    fp1 = fingerprint(f1)
    f2 = run(pid, Participant(seed=2), ["--resume"])
    assert fingerprint(f1) == fp1, "part 1 was changed"
    ev = {(e["phase"], e["event"]) for e in csv_rows(f2, "events.csv")}
    assert ("questionnaire", "start") not in ev and ("lextale", "start") not in ev, "questionnaire/LexTALE ran again"
    practice = [r for r in csv_rows(f2, "trials.csv") if r["phase"] == "practice"]
    assert len(practice) == 3, "practice should run: part 1 never reached it"
    runs = [e["detail"] for e in csv_rows(f2, "events.csv") if e["phase"] == "validation" and e["event"] == "start"]
    assert '"resume"' in runs[0], runs[0]
    with open(os.path.join(f1, "plan.json"), encoding="utf-8") as fh:
        s = check_whole_session([f1, f2], json.load(fh))
    print(f"ok   A: 2 parts, {sum(v['paragraphs'] for v in s['by_level'].values())} paragraphs, "
          f"validation runs {[v['run'] for v in s['validation']]}")


def scenario_b(tmp):
    print("\n=== B: stopped mid-paragraph twice (trial 5, then trial 16)")
    pid = "P91"
    # part 1: 3 practice + trials 1-4, Ctrl+Q while reading trial 5 (the 8th reading screen)
    f1 = run(pid, Aborter("reading", 8))
    assert meta(f1)["main_trials_done"] == 4
    assert any(p["trial"] == "5" for p in csv_rows(f1, "presses.csv")), "expected a press on the cut-off trial"
    fp1 = fingerprint(f1)
    # part 2: trials 5-15 (+ break after 12), Ctrl+Q while reading trial 16 (the 12th reading screen)
    f2 = run(pid, Aborter("reading", 12, seed=3), ["--resume"])
    m2 = meta(f2)
    assert m2["resumed_at_trial"] == 5 and m2["reread_trials"] == [5] and m2["main_trials_done"] == 11, m2
    assert not [r for r in csv_rows(f2, "trials.csv") if r["phase"] == "practice"], "practice ran again"
    fp2 = fingerprint(f2)
    # part 3: trials 16-24, final check, confirmations
    f3 = run(pid, Participant(seed=4), ["--resume"])
    assert fingerprint(f1) == fp1 and fingerprint(f2) == fp2, "an earlier part was changed"
    m3 = meta(f3)
    assert m3["resumed_at_trial"] == 16 and m3["reread_trials"] == [16] and m3["main_trials_done"] == 9, m3
    with open(os.path.join(f1, "plan.json"), encoding="utf-8") as fh:
        s = check_whole_session([f1, f2, f3], json.load(fh))
    # nothing left to resume
    try:
        run(pid, Participant(), ["--resume"])
        raise AssertionError("a completed session was resumed")
    except SystemExit as e:
        assert "completed" in str(e), e
    print(f"ok   B: 3 parts; validation runs per part: "
          f"{[[v['run'] for v in json.load(open(os.path.join(f, 'summary.json'), encoding='utf-8'))['validation']] for f in (f1, f2, f3)]}")


if __name__ == "__main__":
    tmp = tempfile.mkdtemp(prefix="resume_test_")
    run_session.DATA = check_session.DATA = tmp
    try:
        scenario_a(tmp)
        scenario_b(tmp)
        print("\nall resume tests passed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
