"""Shared gaze-processing code: green-bubble detection and fixation detection.

Before this module, the bubble detector and fixation logic were copy-pasted into
six scripts (README §10.8). This is the single place they live now.

Fixation rule (unchanged from cnn.py, README §6): gaze held within
GAZE_HOLD_RADIUS px of the point where the hold started, for >= GAZE_HOLD_TIME s.

Three measurement bugs are corrected here:
  * saccade_before_duration (README §10.5): was  this.start - prev.START
    (start-to-start, so it contained the whole previous fixation); now
    this.start - prev.END.
  * regression_flag (README §10.5): was only "moved upward"; now "moved leftward
    on the same line OR moved up to an earlier line".
  * Dropouts: cnn.py reset on ANY frame without a bubble, so a single missed
    screenshot (a blink, a flicker) silently discarded the fixation in progress.
    Now only a gap longer than MAX_SAMPLE_GAP ends it.
The old definitions are kept as *_legacy columns so old and new can be compared.

Caution: at 5-20 Hz a real saccade (20-80 ms) falls between two samples, so
saccade_before_duration is really the time between two fixations (including
gaze that never settled), not a saccade's duration (README §10.4).
validate_gaze_core.py shows this module reproduces the original cnn.py output.
"""
import math

import cv2
import numpy as np

# --- green bubble (Tobii Ghost, #CC10F61F solid) ------------------------------
MIN_BUBBLE_AREA = 250
BUBBLE_RADIUS_RANGE = (10, 80)
HSV_LOWER = np.array([55, 180, 180])
HSV_UPPER = np.array([70, 255, 255])

# --- fixation detection (same values as cnn.py / test.py) ---------------------
GAZE_HOLD_RADIUS = 25      # px
GAZE_HOLD_TIME = 0.25      # s
# A gap between gaze samples longer than this ends the current fixation
# (bubble lost: looked away, long blink). Shorter gaps are tolerated; a blink
# lasts ~0.1-0.4 s.
MAX_SAMPLE_GAP = 0.5       # s

# --- regression definition (new, README §10.5) --------------------------------
LINE_Y_TOLERANCE = 25      # px; about half the measured line pitch (~49 px)
REGRESSION_MIN_DX = 25     # px leftward to count as a same-line regression

FIXATION_COLUMNS = [
    "fix_x", "fix_y", "start_ts", "end_ts", "duration", "dispersion", "n_samples",
    "saccade_before_duration", "saccade_dx", "saccade_dy", "saccade_amplitude",
    "regression_flag", "regression_type",
    "saccade_before_duration_legacy", "regression_flag_legacy",
]


def detect_green_bubble(frame_bgr):
    """Return (x, y) of the Ghost bubble in a BGR screenshot, or None."""
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
    mask = cv2.erode(mask, None, iterations=1)
    mask = cv2.dilate(mask, None, iterations=1)
    mask = cv2.GaussianBlur(mask, (7, 7), 0)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        if cv2.contourArea(cnt) > MIN_BUBBLE_AREA:
            (x, y), radius = cv2.minEnclosingCircle(cnt)
            if BUBBLE_RADIUS_RANGE[0] < radius < BUBBLE_RADIUS_RANGE[1]:
                return int(x), int(y)
    return None


def classify_regression(dx, dy):
    """Return 'leftward', 'upward' or '' for the jump (dx, dy) between two fixations.

    A return sweep to the next line (left AND down) is normal reading, not a
    regression, so it is excluded by requiring the jump to stay on the same line.
    """
    if dy < -LINE_Y_TOLERANCE:
        return "upward"
    if abs(dy) <= LINE_Y_TOLERANCE and dx < -REGRESSION_MIN_DX:
        return "leftward"
    return ""


class FixationDetector:
    """Feed gaze samples one by one; collects finished fixations in .fixations.

    Works the same live (capture scripts) and offline (rebuilding from gaze.csv):
    only feed it frames where the bubble was found; gaps are handled inside.
    """

    def __init__(self, max_gap=MAX_SAMPLE_GAP):
        self.max_gap = max_gap
        self._last_t = None
        self.fixations = []
        self._hold_start = None
        self._hold_pos = None
        self._in_fixation = False
        self._points = []
        self._prev = None  # last finished fixation

    def bubble_lost(self):
        # Same as cnn.py: a fixation in progress is dropped, not saved.
        self._hold_start = None
        self._hold_pos = None
        self._in_fixation = False
        self._points = []

    def add(self, t, x, y):
        """Add one gaze sample (t in seconds). Returns the fixation dict if one just ended."""
        if self._last_t is not None and t - self._last_t > self.max_gap:
            self.bubble_lost()
        self._last_t = t
        if self._hold_pos is None:
            self._hold_start, self._hold_pos, self._points = t, (x, y), []
            return None
        if math.hypot(x - self._hold_pos[0], y - self._hold_pos[1]) <= GAZE_HOLD_RADIUS:
            if not self._in_fixation and t - self._hold_start >= GAZE_HOLD_TIME:
                self._in_fixation = True
                self._points = [(x, y)]
            elif self._in_fixation:
                self._points.append((x, y))
            return None
        finished = self._finish(t) if self._in_fixation else None
        self._in_fixation = False
        self._hold_start, self._hold_pos, self._points = t, (x, y), []
        return finished

    def _finish(self, end_t):
        fx, fy = self._hold_pos  # cnn.py logs the hold anchor as the fixation position
        mx = sum(p[0] for p in self._points) / len(self._points)
        my = sum(p[1] for p in self._points) / len(self._points)
        fix = {
            "fix_x": fx, "fix_y": fy,
            "start_ts": self._hold_start, "end_ts": end_t,
            "duration": end_t - self._hold_start,
            "dispersion": max(math.hypot(px - mx, py - my) for px, py in self._points),
            # samples after the fixation was confirmed, i.e. excluding its first
            # GAZE_HOLD_TIME s (as in cnn.py; dispersion uses the same samples)
            "n_samples": len(self._points),
        }
        prev = self._prev
        if prev is None:
            fix.update(saccade_before_duration=0.0, saccade_dx=0, saccade_dy=0,
                       saccade_amplitude=0.0, regression_flag=0, regression_type="",
                       saccade_before_duration_legacy=0.0, regression_flag_legacy=0)
        else:
            dx, dy = fx - prev["fix_x"], fy - prev["fix_y"]
            rtype = classify_regression(dx, dy)
            fix.update(
                saccade_before_duration=fix["start_ts"] - prev["end_ts"],
                saccade_dx=dx, saccade_dy=dy, saccade_amplitude=math.hypot(dx, dy),
                regression_flag=int(bool(rtype)), regression_type=rtype,
                saccade_before_duration_legacy=fix["start_ts"] - prev["start_ts"],
                regression_flag_legacy=int(bool(prev["fix_y"]) and fy < prev["fix_y"]),
            )
        self._prev = fix
        self.fixations.append(fix)
        return fix


def fixations_from_gaze(times, xs, ys, max_gap=MAX_SAMPLE_GAP):
    """Offline: run the detector over a recorded gaze stream (times in seconds)."""
    det = FixationDetector(max_gap)
    for t, x, y in zip(times, xs, ys):
        det.add(t, x, y)
    return det.fixations
