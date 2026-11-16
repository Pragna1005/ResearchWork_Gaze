"""End-to-end test without a person or a tracker: a scripted 'participant'
answers every screen while the simulated reader produces gaze.

    python tests/test_full_session.py
"""
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from study import config as C  # noqa: E402

# short timings so the test runs in a minute or two
C.BREAK_S = 1
C.VALIDATION_SETTLE_S = 0.15
C.VALIDATION_COLLECT_S = 0.25
C.MIN_READ_S = 0.3


class Participant:
    """Reads each paragraph for ~1.5-2.5 s, presses C on harder ones more often."""

    def __init__(self, seed=0, read_s=(1.7, 2.4)):
        self.rng = random.Random(seed)
        self.read_s = read_s
        self.tag, self.t0, self.plan = None, 0, []

    def keys(self, tag):
        now = time.perf_counter()
        if tag != self.tag or not self.plan:
            # a new screen, or the same kind of screen again (the next word, the next paragraph)
            self.tag, self.t0 = tag, now
            self.plan = self._plan(tag)
        out = []
        while self.plan and now - self.t0 >= self.plan[0][0]:
            out.append((self.plan.pop(0)[1], "", now))
        return out

    def _plan(self, tag):
        r = self.rng
        if tag == "reading":
            end = r.uniform(*self.read_s)
            steps = [(t, "c") for t in sorted(r.uniform(0.5 * end, 0.9 * end) for _ in range(r.choice([0, 0, 0, 1, 1, 2])))]
            return steps + [(end, "space")]
        if tag == "lex_item":
            return [(0.01, r.choice("yyyn"))]
        if tag in ("question", "q_gender", "q_l2read", "q_habit", "q_vision", "q_know", "q_interest", "confirm_reason"):
            return [(0.01, str(r.randint(1, 4)))]
        if tag == "confirm_yes":
            return [(0.01, r.choice("1113"))]
        if tag.startswith("val_result"):
            return [(0.01, "return")]
        if tag == "end":
            return [(0.05, "return")]
        if tag in ("val_dot", "marker", "break"):
            return []
        return [(0.02, "space")]

    def text(self, tag):
        return {"q_age": "22", "q_l2age": "5", "confirm_lines": str(self.rng.randint(1, 4))}.get(tag, "test answer")


if __name__ == "__main__":
    import run_session
    if "--long" in sys.argv:  # a few paragraphs read at a realistic pace (6-10 s), to test the windows
        folder = run_session.main(["--participant", "TEST", "--gaze", "sim", "--size", "1920x1080",
                                   "--skip", "questionnaire,lextale,practice", "--max-trials", "8"],
                                  auto=Participant(read_s=(6, 10)))
    else:
        folder = run_session.main(["--participant", "TEST", "--gaze", "sim", "--size", "1920x1080"], auto=Participant())
    print("session folder:", folder)
