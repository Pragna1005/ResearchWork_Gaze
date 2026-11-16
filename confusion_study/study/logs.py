"""CSV/JSON writers. Every row is flushed at once, so a crash loses nothing."""
import csv
import datetime
import json
import os
import time


class CsvLog:
    def __init__(self, path, columns):
        self.columns = columns
        self.f = open(path, "w", newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, fieldnames=columns, extrasaction="ignore")
        self.w.writeheader()
        self.f.flush()

    def write(self, **row):
        for k, v in row.items():
            if isinstance(v, float):
                row[k] = f"{v:.6f}" if k == "t" or k.endswith("_t") else round(v, 4)
        self.w.writerow(row)
        self.f.flush()

    def close(self):
        self.f.close()


class SessionLogs:
    def __init__(self, folder):
        self.folder = folder
        j = lambda n: os.path.join(folder, n)
        self.events = CsvLog(j("events.csv"), ["t", "wall", "phase", "event", "trial", "item_id", "detail"])
        self.trials = CsvLog(j("trials.csv"), [
            "trial", "phase", "half", "block", "item_id", "kind", "level", "article", "p_index", "topic",
            "n_words", "fk_grade", "on_t", "off_t", "reading_s", "n_presses", "press_times",
            "question", "options_shown", "correct_option", "answer_option", "answer_correct", "answer_rt_s"])
        self.presses = CsvLog(j("presses.csv"), [
            "t", "trial", "item_id", "kind", "level", "s_into_paragraph", "gaze_x", "gaze_y", "gaze_age_s",
            "line_under_gaze", "word_under_gaze"])
        self.layout = CsvLog(j("layout_words.csv"), [
            "trial", "item_id", "line", "word_index", "word", "x0", "x1", "y0", "y1", "band_y0", "band_y1"])
        self.lextale = CsvLog(j("lextale.csv"), ["n", "item", "is_word", "practice", "response", "correct", "rt_s", "t"])
        self.validation = CsvLog(j("validation.csv"), [
            "run", "attempt", "dot", "target_x", "target_y", "n_samples", "gaze_x", "gaze_y", "dx", "dy", "error_px"])
        self.confirm = CsvLog(j("confirmations.csv"), [
            "trial", "item_id", "kind", "level", "n_presses", "confused", "lines_reported", "reason_code", "reason", "t"])

    def event(self, phase, event, trial="", item_id="", **detail):
        now = time.perf_counter()
        self.events.write(t=now, wall=datetime.datetime.now().isoformat(timespec="milliseconds"), phase=phase,
                          event=event, trial=trial, item_id=item_id,
                          detail=json.dumps(detail, ensure_ascii=False) if detail else "")
        return now

    def layout_rows(self, trial, item_id, lines):
        for ln in lines:
            for j, (word, x0, x1) in enumerate(ln["words"]):
                self.layout.write(trial=trial, item_id=item_id, line=ln["index"], word_index=j, word=word,
                                  x0=x0, x1=x1, y0=ln["y0"], y1=ln["y1"], band_y0=ln["band_y0"], band_y1=ln["band_y1"])

    def close(self):
        for log in (self.events, self.trials, self.presses, self.layout, self.lextale, self.validation, self.confirm):
            log.close()


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
