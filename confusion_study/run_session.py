"""Run one participant's session, start to finish.

    python run_session.py --participant P01                  # real study (Tobii Ghost)
    python run_session.py --participant TEST --gaze mouse    # rehearse without the tracker

Order (slide "Session protocol"): questionnaire -> LexTALE -> calibration check
-> instructions -> 3 practice paragraphs -> 24 paragraphs with a break and a
second calibration check halfway -> final calibration check -> confirm the C
presses -> end.

Experimenter keys:  Ctrl+Q = save and quit at any point
                    F9     = pause after the current paragraph (recalibrate, then check)
Output: data/<participant>_<date-time>/   Then run:  python check_session.py

Continue a session stopped with Ctrl+Q (or a crash):
    python run_session.py --participant P02 --resume
Writes a linked second part, data/<participant>_<date-time>_part2/ (meta.json ->
resume_of), and never changes the earlier folder. Same plan and order; starts
with a calibration check at the first paragraph without a saved trial row (a
paragraph cut off mid-way is read again). Questionnaire, LexTALE and practice
are skipped if an earlier part finished them. The break, final calibration
check and confirmation step (for the presses of all parts) still run.
"""
import argparse
import csv
import datetime
import glob
import json
import os
import platform
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from study import config as C  # noqa: E402
from study.gaze_capture import display_scale_percent, make_source, set_dpi_aware  # noqa: E402
from study.logs import SessionLogs, write_json  # noqa: E402
from study.materials import TOPICS, build_plan  # noqa: E402

DATA = os.path.join(HERE, "data")

RESUME_TEXT = ("Welcome back. We continue where we stopped.\n\n"
               "Remember: press C whenever you feel confused, and Space when you have finished a paragraph. "
               "Answer the questions with the number keys 1 to 4.\n\n"
               "Please keep your head still while reading.\n\nPress Space to continue.")


def config_snapshot():
    return {k: getattr(C, k) for k in dir(C) if k.isupper()}


def _read_csv(folder, name):
    p = os.path.join(folder, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def session_parts(pid):
    """The folders of this participant's latest session, first part first (follows meta resume_of)."""
    found = {}
    for p in glob.glob(os.path.join(DATA, f"{pid}_*", "meta.json")):
        m = _read_json(p)
        if m.get("participant") == pid:
            found[os.path.basename(os.path.dirname(p))] = (os.path.dirname(p), m)
    if not found:
        sys.exit(f"--resume: no session folder for {pid} in {DATA}")
    name = max(found, key=lambda n: (found[n][1].get("start_wall", ""), n))
    chain = []
    while name:
        if name not in found:
            sys.exit(f"--resume: {chain[0][0]} continues {name}, which is missing")
        chain.insert(0, found[name])
        name = found[name][1].get("resume_of")
    return chain


def _lines_from_layout(rows):
    """Rebuild the line dicts (as drawn) from layout_words.csv rows of one trial."""
    lines = {}
    for w in rows:
        li = int(w["line"])
        ln = lines.setdefault(li, {"index": li, "words": [], "y0": int(float(w["y0"])), "y1": int(float(w["y1"])),
                                   "band_y0": int(float(w["band_y0"])), "band_y1": int(float(w["band_y1"]))})
        ln["words"].append((int(w["word_index"]), w["word"], int(float(w["x0"])), int(float(w["x1"]))))
    out = []
    for li in sorted(lines):
        ln = lines[li]
        ln["words"] = [(w, x0, x1) for _, w, x0, x1 in sorted(ln["words"])]
        ln.update(text=" ".join(w for w, _, _ in ln["words"]), x0=ln["words"][0][1], x1=ln["words"][-1][2])
        out.append(ln)
    return out


def previous_state(chain, plan):
    """What the earlier part(s) finished: main trials (as results for the confirmation step), practice,
    questionnaire, LexTALE, confirmations."""
    by_id = {str(t["trial"]): t for t in plan["main"]}
    results, done, started, confirmed, practice, lextale, questionnaire = {}, set(), set(), set(), set(), None, False
    for folder, _ in chain:
        rows = _read_csv(folder, "trials.csv")
        layout = {}
        for w in _read_csv(folder, "layout_words.csv"):
            layout.setdefault(w["trial"], []).append(w)
        started |= {t for t in layout if t in by_id}
        for r in rows:
            if r["phase"] == "practice":
                practice.add(r["trial"])
            elif r["phase"] == "main" and r["trial"] in by_id:
                row = dict(r, n_presses=int(r["n_presses"]), reading_s=float(r["reading_s"]),
                           answer_correct=int(r["answer_correct"]) if r["answer_correct"] != "" else "")
                results[r["trial"]] = {"trial": by_id[r["trial"]], "presses": [None] * row["n_presses"],
                                       "lines": _lines_from_layout(layout.get(r["trial"], [])), "row": row}
                done.add(r["trial"])
        confirmed |= {c["trial"] for c in _read_csv(folder, "confirmations.csv")}
        questionnaire |= os.path.exists(os.path.join(folder, "questionnaire.json"))
        sp = os.path.join(folder, "summary.json")
        if os.path.exists(sp) and "lextale" in _read_json(sp):
            lextale = _read_json(sp)["lextale"]
    ordered = [results[str(t["trial"])] for t in plan["main"] if str(t["trial"]) in results]
    return {"results": ordered, "done": done, "reread": sorted(started - done, key=int), "confirmed": confirmed,
            "practice_done": len(practice) >= len(plan["practice"]), "questionnaire_done": questionnaire,
            "lextale": lextale}


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--participant", required=True, help="P01, P02, ... (never a name)")
    ap.add_argument("--gaze", choices=["tobii", "mouse", "sim"], default="tobii",
                    help="tobii = the study; mouse = rehearsal without a tracker; sim = software test")
    ap.add_argument("--backend", default=C.CAPTURE_BACKEND, choices=["mss", "dxcam", "pyautogui"])
    ap.add_argument("--skip", default="", help="comma list of parts to skip: questionnaire,lextale,practice,confirm")
    ap.add_argument("--max-trials", type=int, default=0, help="only for testing: stop after N main paragraphs")
    ap.add_argument("--windowed", action="store_true", help="window instead of full screen (testing only)")
    ap.add_argument("--size", default="", help="window size WxH (testing only)")
    ap.add_argument("--notes", default="", help="free text saved in meta.json")
    ap.add_argument("--allow-repeat", action="store_true", help="allow a second session for this participant id")
    ap.add_argument("--resume", action="store_true",
                    help="continue this participant's latest stopped session in a linked _partN folder")
    return ap.parse_args(argv)


def main(argv=None, auto=None):
    args = parse_args(argv)
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    pid = args.participant.strip()
    if not args.allow_repeat and pid.upper() != "TEST":
        done = [p for p in glob.glob(os.path.join(DATA, f"{pid}_*", "meta.json"))
                if json.load(open(p)).get("completed")]
        if done:
            sys.exit(f"{pid} already has a completed session ({os.path.dirname(done[0])}). "
                     "Use a new id, or --allow-repeat.")

    prev, chain = None, []
    if args.resume:
        chain = session_parts(pid)
        if chain[-1][1].get("completed"):
            sys.exit(f"--resume: {chain[-1][0]} is already completed")
        plan = _read_json(os.path.join(chain[0][0], "plan.json"))
        prev = previous_state(chain, plan)
        if len(prev["done"]) == len(plan["main"]) and prev["confirmed"] >= {
                str(r["trial"]["trial"]) for r in prev["results"] if r["presses"]}:
            sys.exit(f"--resume: every paragraph and confirmation of {pid} is already saved; nothing to resume")
        auto_skip = [k for k, done in (("questionnaire", prev["questionnaire_done"]), ("lextale", prev["lextale"]),
                                       ("practice", prev["practice_done"])) if done]
        skip |= set(auto_skip)
        remaining = [t["trial"] for t in plan["main"] if str(t["trial"]) not in prev["done"]]
        print(f"Resuming {pid} after {os.path.basename(chain[-1][0])}: {len(prev['done'])} of {len(plan['main'])} "
              f"paragraphs saved, continuing at trial {remaining[0] if remaining else '(none: confirmation step)'}")
        print(f"  skipped (done earlier): {', '.join(auto_skip) or 'nothing'}")
        if not prev["practice_done"]:
            print("  practice was not finished earlier" +
                  (": skipped because of --skip practice" if "practice" in skip else ": it runs now"
                   " (add --skip practice to leave it out)"))
        if prev["reread"]:
            print(f"  read again (stopped mid-way before): trial {', '.join(prev['reread'])}")

    set_dpi_aware()  # before the window opens: one pixel = one screenshot pixel
    stamp = f"{pid}_{datetime.datetime.now():%Y%m%d-%H%M%S}"
    part = len(chain) + 1
    folder = os.path.join(DATA, stamp if part == 1 else f"{stamp}_part{part}")
    os.makedirs(folder)
    if not args.resume:
        plan = build_plan(pid)
    write_json(os.path.join(folder, "plan.json"), plan)
    logs = SessionLogs(folder)

    from study.ui import UI, Abort
    from study import tasks
    size = tuple(int(v) for v in args.size.lower().split("x")) if args.size else None
    ui = UI(size=size, windowed=args.windowed)
    ui.auto = auto
    import pygame
    pygame.mouse.set_visible(args.gaze == "mouse")

    gaze = make_source(args.gaze, args.backend, C.FLUSH_EVERY_S, seed=plan["seed"])
    meta = {
        "participant": pid, "list": plan["list"], "seed": plan["seed"], "gaze_source": args.gaze,
        "capture_backend": args.backend if args.gaze == "tobii" else None, "notes": args.notes,
        "start_wall": datetime.datetime.now().isoformat(timespec="seconds"),
        "clock": {"perf_counter": time.perf_counter(), "wall_epoch": time.time()},
        "screen_px": [ui.w, ui.h], "display_scale_percent": display_scale_percent(),
        "font_file": ui.font_path, "line_pitch_px": ui.pitch, "text_left_px": ui.left, "text_width_px": ui.text_width,
        "config": config_snapshot(), "python": sys.version.split()[0], "os": platform.platform(),
        "completed": False, "aborted": False, "skipped": sorted(skip), "part": part,
    }
    prev_results = prev["results"] if prev else []
    if prev:
        first_left = next((t["trial"] for t in plan["main"] if str(t["trial"]) not in prev["done"]), None)
        meta.update(resume_of=os.path.basename(chain[-1][0]), first_part=os.path.basename(chain[0][0]),
                    resumed_at_trial=first_left, earlier_main_trials_done=len(prev["done"]),
                    reread_trials=[int(t) for t in prev["reread"]])
        old_screen = chain[-1][1].get("screen_px")
        if old_screen and list(old_screen) != [ui.w, ui.h]:
            print(f"WARNING: screen is {ui.w}x{ui.h}, the earlier part used {old_screen[0]}x{old_screen[1]}. "
                  "Text positions will differ between parts.", file=sys.stderr)
            meta["screen_differs_from_earlier_part"] = old_screen
    write_json(os.path.join(folder, "meta.json"), meta)
    summary = {"participant": pid, "list": plan["list"]}
    if prev:
        summary["parts"] = [os.path.basename(f) for f, _ in chain] + [os.path.basename(folder)]
        if prev["lextale"]:
            summary["lextale"] = prev["lextale"]  # copied from the earlier part
    results = []
    try:
        gaze.start(folder, (ui.w, ui.h))
        logs.event("session", "start", gaze=args.gaze)
        if prev:
            logs.event("session", "resume", resume_of=meta["resume_of"], part=part,
                       resumed_at_trial=meta["resumed_at_trial"], reread=meta["reread_trials"])

        if "questionnaire" not in skip:
            q = tasks.questionnaire(ui, logs, TOPICS)
            write_json(os.path.join(folder, "questionnaire.json"), q)
        if "lextale" not in skip:
            summary["lextale"] = tasks.lextale(ui, logs)
            write_json(os.path.join(folder, "summary.json"), summary)

        summary["validation"] = [tasks.calibration_check(ui, gaze, logs, "resume" if prev else "start")]
        if prev and "practice" in skip:
            ui.pause_screen(RESUME_TEXT, tag="resume_start")
        else:
            ui.pause_screen(tasks.READING_INSTRUCTIONS, tag="instructions")
            if "practice" not in skip:
                for tr in plan["practice"]:
                    tasks.run_trial(ui, gaze, logs, tr)
            ui.pause_screen("That was the practice.\n\nThe study now starts. It has two parts with a short break "
                            "in between.\n\nRemember: press C whenever you feel confused, Space when you have "
                            "finished a paragraph.\n\nPress Space to begin.", tag="main_start")

        todo = [t for t in plan["main"] if not prev or str(t["trial"]) not in prev["done"]]
        main_trials = todo[:args.max_trials] if args.max_trials else todo
        for tr in main_trials:
            if ui.pause_requested:
                ui.pause_requested = False
                logs.event("main", "experimenter_pause", tr["trial"])
                ui.pause_screen("Paused by the experimenter.\n\n(Experimenter: recalibrate in Tobii Experience "
                                "if needed, then press Space for a calibration check.)", tag="pause")
                summary["validation"].append(tasks.calibration_check(ui, gaze, logs, f"pause_before_{tr['trial']}"))
            results.append(tasks.run_trial(ui, gaze, logs, tr))
            if tr["trial"] == plan["break_after_trial"] and tr is not main_trials[-1]:
                tasks.take_break(ui, gaze, logs, C.BREAK_S)
                summary["validation"].append(tasks.calibration_check(ui, gaze, logs, "after_break"))
                ui.pause_screen("Second part. Press Space to continue.", tag="part2")

        summary["validation"].append(tasks.calibration_check(ui, gaze, logs, "end"))
        if "confirm" not in skip:
            confirmed = prev["confirmed"] if prev else set()
            tasks.confirm_presses(ui, gaze, logs, [r for r in prev_results + results
                                                   if str(r["trial"]["trial"]) not in confirmed])
        ui.pause_screen("Thank you! You have finished.\n\nPlease let the experimenter know.",
                        keys=("space", "return"), tag="end")
        logs.event("session", "end")
        meta["completed"] = True
    except Abort:
        meta["aborted"] = True
        logs.event("session", "aborted_by_experimenter")
    except Exception:
        meta["aborted"] = True
        meta["error"] = traceback.format_exc()
        with open(os.path.join(folder, "error.log"), "w") as f:
            f.write(meta["error"])
        print(meta["error"], file=sys.stderr)
    finally:
        try:
            meta["gaze"] = gaze.stop()
        except Exception as e:
            meta["gaze"] = {"error": repr(e)}
        meta["end_wall"] = datetime.datetime.now().isoformat(timespec="seconds")
        meta["main_trials_done"] = len(results)  # in this folder
        meta["main_trials_done_total"] = len(prev_results) + len(results)  # all parts of the session
        rows = [r["row"] for r in prev_results + results]
        by = {}
        for lvl in ("Ele", "Adv", "Spec"):
            rs = [r for r in rows if r["level"] == lvl]
            qs = [r for r in rs if r.get("answer_option")]
            by[lvl] = {"paragraphs": len(rs), "paragraphs_with_press": sum(r["n_presses"] > 0 for r in rs),
                       "presses": sum(r["n_presses"] for r in rs),
                       "question_accuracy": round(sum(r["answer_correct"] for r in qs) / len(qs), 3) if qs else None,
                       "mean_reading_s": round(sum(r["reading_s"] for r in rs) / len(rs), 1) if rs else None}
        summary["by_level"] = by
        write_json(os.path.join(folder, "summary.json"), summary)
        write_json(os.path.join(folder, "meta.json"), meta)
        logs.close()
        ui.close()
    status = "COMPLETED" if meta["completed"] else "STOPPED EARLY (data so far is saved)"
    print(f"[{status}] {folder}")
    if meta.get("gaze"):
        print(f"  gaze: {meta['gaze']}")
    print("  next: python check_session.py")
    return folder


if __name__ == "__main__":
    main()
