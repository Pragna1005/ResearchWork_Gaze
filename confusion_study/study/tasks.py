"""The parts of a session, in the order of the protocol slide."""
import random
import statistics
import time

import pygame

from study import config as C
from study.layout import line_at, word_at

# --------------------------------------------------------------------------
# 1. Pre-questionnaire
# --------------------------------------------------------------------------

def questionnaire(ui, logs, topics):
    logs.event("questionnaire", "start")
    a = {}
    ui.pause_screen("Welcome, and thank you for taking part.\n\nFirst, a few short questions about you. "
                    "Answer with the keyboard.\n\nPress Space to start.", tag="q_intro")
    a["age"] = ui.text_input("How old are you?", tag="q_age", allowed_chars="0123456789", max_len=3)
    g, _ = ui.choice("Gender", ["Female", "Male", "Other", "Prefer not to say"], tag="q_gender")
    a["gender"] = ["female", "male", "other", "not_said"][g]
    a["field_of_study"] = ui.text_input("What is your field of study? (e.g. Computer Science, Economics)", tag="q_field")
    a["degree_year"] = ui.text_input("Which degree and year are you in? (e.g. B.Tech 3rd year)", tag="q_year")
    a["first_language"] = ui.text_input("What is your first (native) language?", tag="q_l1")
    a["english_start_age"] = ui.text_input("At what age did you start learning English?", tag="q_l2age",
                                           allowed_chars="0123456789", max_len=2)
    r, _ = ui.choice("How well do you read in English?",
                     ["Poorly", "Fairly", "Well", "Very well", "Like a native speaker"], tag="q_l2read")
    a["english_reading_self_rating_1to5"] = r + 1
    r, _ = ui.choice("How often do you read English texts that are not for your coursework (news, books, articles)?",
                     ["Rarely or never", "A few times a month", "About once a week", "A few times a week", "Every day"],
                     tag="q_habit")
    a["english_reading_frequency_1to5"] = r + 1
    v, _ = ui.choice("Do you wear glasses or contact lenses right now?",
                     ["No", "Glasses", "Contact lenses"], tag="q_vision")
    a["vision_correction"] = ["none", "glasses", "contacts"][v]
    a["prior_knowledge_1to5"], a["interest_1to5"] = {}, {}
    for key, label in topics:
        k, _ = ui.choice(f"How much do you already know about: {label}?",
                         ["Nothing", "A little", "Some", "Quite a lot", "A great deal (I study or work in it)"],
                         tag="q_know")
        a["prior_knowledge_1to5"][key] = k + 1
        i, _ = ui.choice(f"How interested are you in: {label}?",
                         ["Not at all", "A little", "Somewhat", "Quite", "Very"], tag="q_interest")
        a["interest_1to5"][key] = i + 1
    logs.event("questionnaire", "end")
    return a


# --------------------------------------------------------------------------
# 2. LexTALE (Lemhoefer & Broersma 2012), English version, fixed order
# --------------------------------------------------------------------------
LEXTALE_PRACTICE = [("platery", 0), ("denial", 1), ("generic", 1)]
LEXTALE_ITEMS = [
    ("mensible", 0), ("scornful", 1), ("stoutly", 1), ("ablaze", 1), ("kermshaw", 0), ("moonlit", 1),
    ("lofty", 1), ("hurricane", 1), ("flaw", 1), ("alberation", 0), ("unkempt", 1), ("breeding", 1),
    ("festivity", 1), ("screech", 1), ("savoury", 1), ("plaudate", 0), ("shin", 1), ("fluid", 1),
    ("spaunch", 0), ("allied", 1), ("slain", 1), ("recipient", 1), ("exprate", 0), ("eloquence", 1),
    ("cleanliness", 1), ("dispatch", 1), ("rebondicate", 0), ("ingenious", 1), ("bewitch", 1), ("skave", 0),
    ("plaintively", 1), ("kilp", 0), ("interfate", 0), ("hasty", 1), ("lengthy", 1), ("fray", 1),
    ("crumper", 0), ("upkeep", 1), ("majestic", 1), ("magrity", 0), ("nourishment", 1), ("abergy", 0),
    ("proom", 0), ("turmoil", 1), ("carbohydrate", 1), ("scholar", 1), ("turtle", 1), ("fellick", 0),
    ("destription", 0), ("cylinder", 1), ("censorship", 1), ("celestial", 1), ("rascal", 1), ("purrage", 0),
    ("pulsh", 0), ("muddy", 1), ("quirty", 0), ("pudour", 0), ("listless", 1), ("wrought", 1),
]
assert len(LEXTALE_ITEMS) == 60 and sum(w for _, w in LEXTALE_ITEMS) == 40


def lextale(ui, logs):
    logs.event("lextale", "start")
    ui.pause_screen(
        "Word test\n\nYou will see a string of letters. Decide whether it is an existing English word.\n\n"
        "Press Y if it is an English word, or N if it is not.\n\n"
        "If you are sure the word exists, even if you don't know exactly what it means, press Y. "
        "If you are not sure it exists, press N.\n\n"
        "British spelling is used (\"colour\", not \"color\"). There is no time limit.\n\n"
        "The first 3 are practice. Press Space to start.", tag="lex_intro")
    corr_w = corr_n = 0
    n = 0
    for practice, items in ((1, LEXTALE_PRACTICE), (0, LEXTALE_ITEMS)):
        for word, is_word in items:
            n += 1
            ui.clear()
            surf = ui._font(56).render(word, True, C.TEXT_COLOR)
            ui.screen.blit(surf, ((ui.w - surf.get_width()) // 2, ui.h // 2 - 60))
            ui.footer("Y = yes, a word        N = no, not a word")
            t_on = ui.flip()
            key, t = ui.wait_key(["y", "n"], tag="lex_item")
            resp = 1 if key == "y" else 0
            ok = int(resp == is_word)
            if not practice:
                corr_w += ok and is_word
                corr_n += ok and not is_word
            logs.lextale.write(n=n, item=word, is_word=is_word, practice=practice, response=resp, correct=ok,
                               rt_s=t - t_on, t=t)
            ui.clear()
            ui.flip()
            time.sleep(0.25)
    score = (corr_w / 40 * 100 + corr_n / 20 * 100) / 2
    logs.event("lextale", "end", score=score)
    return {"correct_words": int(corr_w), "correct_nonwords": int(corr_n), "score_percent": round(score, 2)}


# --------------------------------------------------------------------------
# 3. Calibration check (Tobii calibration itself is done in Tobii Experience)
# --------------------------------------------------------------------------

def calibration_check(ui, gaze, logs, run):
    attempt = 0
    while True:
        attempt += 1
        ui.pause_screen("Calibration check\n\nA red dot will appear in different places. "
                        "Look straight at the centre of each dot until it moves.\n\nPress Space to start.",
                        tag="val_intro")
        logs.event("validation", "start", run=run, attempt=attempt)
        pts = C.VALIDATION_GRID[:]
        random.Random(attempt).shuffle(pts)
        rows = []
        for i, (fx, fy) in enumerate(pts):
            tx, ty = fx * ui.w, fy * ui.h
            gaze.on_target((tx, ty))
            ui.clear()
            ui.dot(tx, ty)
            t_on = ui.flip()
            samples, seen = [], set()
            while True:
                now = time.perf_counter()
                gaze.tick(now)
                ui.poll("val_dot")
                if now - t_on > C.VALIDATION_SETTLE_S + C.VALIDATION_COLLECT_S:
                    break
                g = gaze.latest()
                if now - t_on > C.VALIDATION_SETTLE_S and g and g[2] < 0.1:
                    key = round(now - g[2], 4)  # one entry per gaze sample, not per screen refresh
                    if key not in seen:
                        seen.add(key)
                        samples.append((g[0], g[1]))
                ui.clock.tick(250)
            if samples:
                gx = statistics.median(s[0] for s in samples)
                gy = statistics.median(s[1] for s in samples)
                dx, dy = gx - tx, gy - ty
                err = (dx * dx + dy * dy) ** 0.5
            else:
                gx = gy = dx = dy = err = None
            rows.append({"dot": i, "target_x": round(tx), "target_y": round(ty), "n_samples": len(samples),
                         "gaze_x": gx, "gaze_y": gy, "dx": dx, "dy": dy, "error_px": err})
            logs.validation.write(run=run, attempt=attempt, **rows[-1])
        ok_rows = [r for r in rows if r["error_px"] is not None]
        mean_err = statistics.mean(r["error_px"] for r in ok_rows) if ok_rows else None
        mean_dy = statistics.mean(abs(r["dy"]) for r in ok_rows) if ok_rows else None
        limit = C.VALIDATION_MAX_DY_SHARE * ui.pitch
        good = mean_dy is not None and mean_dy < limit and len(ok_rows) == len(rows)
        result = {"run": run, "attempt": attempt, "mean_error_px": mean_err, "mean_abs_dy_px": mean_dy,
                  "dots_with_gaze": len(ok_rows), "dots": len(rows), "line_pitch_px": ui.pitch, "ok": good}
        logs.event("validation", "result", **result)
        # results screen for the experimenter
        ui.clear()
        for r in rows:
            ui.dot(r["target_x"], r["target_y"])
            if r["gaze_x"] is not None:
                pygame.draw.circle(ui.screen, (30, 60, 200), (int(r["gaze_x"]), int(r["gaze_y"])), 8, 3)
                pygame.draw.line(ui.screen, (30, 60, 200), (r["target_x"], r["target_y"]), (int(r["gaze_x"]), int(r["gaze_y"])), 2)
        verdict = "OK" if good else "NOT OK: recalibrate in Tobii Experience, then press R"
        txt = (f"Calibration check ({run}, attempt {attempt}): {verdict}\n"
               f"Mean error {mean_err:.0f} px, mean vertical error {mean_dy:.0f} px "
               f"(must be below {limit:.0f} px, half the line pitch). Gaze found at {len(ok_rows)}/{len(rows)} dots."
               if ok_rows else f"Calibration check ({run}): NO GAZE. Is the Ghost bubble on? Recalibrate, then press R.")
        ui.message(txt, top=ui.h // 2 - 60, size=26)
        ui.footer("Experimenter: R = repeat the check     Enter = continue")
        ui.flip()
        key, _ = ui.wait_key(["r", "return"], tag="val_result_ok" if good else "val_result_bad")
        logs.event("validation", "decision", run=run, attempt=attempt, decision=key)
        if key == "return":
            return result


# --------------------------------------------------------------------------
# 4. Reading
# --------------------------------------------------------------------------
READING_INSTRUCTIONS = (
    "Reading\n\n"
    "You will read short paragraphs, one at a time. Read each one normally, at your own pace, "
    "as if you were reading an article.\n\n"
    "Press C whenever you feel confused: for example, you don't know a word, you can't follow a sentence, "
    "or you lose the thread. Then keep reading.\n\n"
    "Press C as often or as rarely as you really feel confused. It is fine not to press it at all. "
    "You will hear a short beep when you press it.\n\n"
    "When you have finished a paragraph, press Space.\n\n"
    "After some paragraphs there is a question. Answer it with the number keys 1 to 4.\n\n"
    "Please keep your head still while reading.\n\n"
    "We start with 3 practice paragraphs. Press Space to begin.")


def start_marker(ui, gaze, logs, trial, lines):
    """A small dot where the first line starts, for 0.6 s: puts the eyes at the start of the text
    and measures drift before every paragraph."""
    x, y = lines[0]["x0"] - 22, (lines[0]["y0"] + lines[0]["y1"]) / 2
    gaze.on_target((x, y))
    ui.clear()
    pygame.draw.circle(ui.screen, (60, 60, 60), (int(x), int(y)), 7)
    t_on = ui.flip()
    g = None
    while time.perf_counter() - t_on < 0.6:
        now = time.perf_counter()
        gaze.tick(now)
        ui.poll("marker")
        g = gaze.latest()
        ui.clock.tick(250)
    logs.event(trial["phase"], "start_marker", trial["trial"], trial["item_id"], target=[round(x), round(y)],
               gaze=[round(g[0]), round(g[1])] if g and g[2] < 0.2 else None)


def read_paragraph(ui, gaze, logs, trial):
    lines = ui.layout(trial["text"])
    logs.layout_rows(trial["trial"], trial["item_id"], lines)
    start_marker(ui, gaze, logs, trial, lines)
    gaze.on_layout(lines)
    ui.clear()
    ui.draw_lines(lines)
    t_on = ui.flip()
    logs.event(trial["phase"], "paragraph_on", trial["trial"], trial["item_id"], n_lines=len(lines))
    presses = []
    while True:
        now = time.perf_counter()
        gaze.tick(now)
        done = False
        for key, _, t in ui.poll("reading"):
            if key == C.CONFUSED_KEY:
                if ui.beep:
                    ui.beep.play()
                g = gaze.latest()
                gx, gy, age = (g if g else (None, None, None))
                li = line_at(lines, gx, gy) if g else None
                wi = word_at(lines, gx, gy) if g else None
                presses.append(t)
                logs.presses.write(t=t, trial=trial["trial"], item_id=trial["item_id"], kind=trial["kind"],
                                   level=trial["level"], s_into_paragraph=t - t_on,
                                   gaze_x=round(gx) if g else "", gaze_y=round(gy) if g else "",
                                   gaze_age_s=age if g else "", line_under_gaze="" if li is None else li,
                                   word_under_gaze="" if wi is None else wi)
                logs.event(trial["phase"], "confused_press", trial["trial"], trial["item_id"], line=li)
            elif key == C.NEXT_KEY:
                if t - t_on >= C.MIN_READ_S:
                    done = True
                    break
                logs.event(trial["phase"], "next_too_early", trial["trial"], trial["item_id"], s=round(t - t_on, 3))
        if done:
            break
        ui.clock.tick(250)
    ui.clear()
    t_off = ui.flip()
    logs.event(trial["phase"], "paragraph_off", trial["trial"], trial["item_id"])
    return {"on_t": t_on, "off_t": t_off, "reading_s": t_off - t_on, "presses": presses, "lines": lines}


def ask_question(ui, logs, trial):
    q = trial["question"]
    order = trial["option_order"]
    shown = [q["options"][i] for i in order]
    correct_pos = order.index(q["correct"])
    logs.event(trial["phase"], "question_on", trial["trial"], trial["item_id"])
    ui.clear()
    t_on = time.perf_counter()
    idx, t = ui.choice(q["text"], shown, tag="question")
    logs.event(trial["phase"], "answer", trial["trial"], trial["item_id"], position=idx + 1, correct=idx == correct_pos)
    return {"question": q["text"], "options_shown": " | ".join(shown), "correct_option": correct_pos + 1,
            "answer_option": idx + 1, "answer_correct": int(idx == correct_pos), "answer_rt_s": t - t_on}


def run_trial(ui, gaze, logs, trial):
    r = read_paragraph(ui, gaze, logs, trial)
    row = {k: trial.get(k, "") for k in ("trial", "phase", "half", "block", "item_id", "kind", "level", "article",
                                         "p_index", "topic", "n_words", "fk_grade")}
    row.update(on_t=r["on_t"], off_t=r["off_t"], reading_s=r["reading_s"], n_presses=len(r["presses"]),
               press_times=" ".join(f"{p - r['on_t']:.3f}" for p in r["presses"]))
    if trial.get("question"):
        row.update(ask_question(ui, logs, trial))
    logs.trials.write(**row)
    ui.clear()
    ui.flip()
    time.sleep(0.3)
    return {"trial": trial, "presses": r["presses"], "lines": r["lines"], "row": row}


def take_break(ui, gaze, logs, seconds):
    logs.event("break", "start")
    t0 = time.perf_counter()
    while True:
        now = time.perf_counter()
        gaze.tick(now)
        left = seconds - (now - t0)
        if left <= 0:
            break
        ui.poll("break")
        ui.clear()
        ui.message(f"Halfway! Take a short break.\n\nYou can look away from the screen and relax your eyes.\n\n"
                   f"{int(left) + 1} s", top=300)
        ui.flip()
        ui.clock.tick(10)
    ui.pause_screen("The break is over. Please sit as you did before.\n\nPress Space when you are ready.", tag="break_end")
    logs.event("break", "end")


# --------------------------------------------------------------------------
# 5. Confirm the presses
# --------------------------------------------------------------------------
REASONS = ["A word I did not know", "A sentence I could not follow", "I did not have the background knowledge",
           "I lost track / my attention drifted", "Something else"]


def confirm_presses(ui, gaze, logs, results):
    pressed = [r for r in results if r["presses"]]
    logs.event("confirm", "start", n=len(pressed))
    if not pressed:
        return
    ui.pause_screen(f"Almost done.\n\nYou pressed C on {len(pressed)} paragraph(s). "
                    "We will show each of them again with line numbers, and ask a few quick questions.\n\n"
                    "Press Space to start.", tag="confirm_intro")
    for r in pressed:
        tr, lines = r["trial"], r["lines"]

        def draw(prompt):
            ui.clear()
            ui.message(prompt, top=30, size=26, width=1700)
            ui.draw_lines(lines)
            for ln in lines:
                s = ui.small.render(str(ln["index"] + 1), True, C.MUTED_COLOR)
                ui.screen.blit(s, (ln["x0"] - 50, ln["y0"] + 4))

        n = len(r["presses"])
        draw(f"You pressed C {n} time(s) on this paragraph. Were you confused while reading it?   "
             "1 = Yes     2 = No, I pressed by mistake     3 = Not sure")
        ui.flip()
        k, _ = ui.wait_key(["1", "2", "3"], tag="confirm_yes")
        confused = {"1": "yes", "2": "no", "3": "not_sure"}[k]
        lines_rep, reason_code = "", ""
        if confused != "no":
            draw("Which line(s) confused you? Type the line numbers (e.g. 3 5), then Enter. "
                 "Just press Enter if you don't remember.")
            ui.flip()
            lines_rep = _typed_numbers(ui, draw, "confirm_lines")
            draw("What confused you?   " + "   ".join(f"{i + 1} = {x}" for i, x in enumerate(REASONS)))
            ui.flip()
            k, _ = ui.wait_key([str(i + 1) for i in range(len(REASONS))], tag="confirm_reason")
            reason_code = int(k)
        t = logs.event("confirm", "answer", tr["trial"], tr["item_id"], confused=confused, lines=lines_rep)
        logs.confirm.write(trial=tr["trial"], item_id=tr["item_id"], kind=tr["kind"], level=tr["level"], n_presses=n,
                           confused=confused, lines_reported=lines_rep, reason_code=reason_code,
                           reason=REASONS[reason_code - 1] if reason_code else "", t=t)


def _typed_numbers(ui, draw, tag):
    if ui.auto is not None:
        return ui.auto.text(tag)
    value = ""
    while True:
        for name, uni, _ in ui.poll(tag):
            if name == "return":
                return " ".join(value.split())
            if name == "backspace":
                value = value[:-1]
            elif uni and (uni.isdigit() or uni == " "):
                value += uni
        draw("Which line(s) confused you? Type the line numbers (e.g. 3 5), then Enter. "
             "Just press Enter if you don't remember.")
        s = ui.big.render("Lines: " + value + "|", True, C.TEXT_COLOR)
        ui.screen.blit(s, (ui.left, ui.h - 110))
        ui.flip()
        ui.clock.tick(60)
