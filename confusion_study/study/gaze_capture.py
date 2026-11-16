"""Gaze sources. All write gaze.csv with the same columns and clock.

    tobii  : screenshots of the Tobii Ghost bubble, in a separate process so the
             reading screen never waits for a screenshot (the real study)
    mouse  : the mouse pointer stands in for gaze (rehearse the session without a tracker)
    sim    : a fake reader that moves along the text lines (testing only)

Clock: every file in a session uses time.perf_counter() as `t`. On Windows this
is the same system-wide counter in both processes, so gaze and key presses line
up to well under a millisecond. meta.json stores one (perf_counter, wall clock)
pair to convert `t` to a date and time.
"""
import csv
import math
import multiprocessing as mp
import os
import random
import sys
import time

GAZE_COLUMNS = ["t", "x", "y", "found"]

# shared array slots
_X, _Y, _T, _FRAMES, _FOUND, _READY, _ERR = range(7)


def set_dpi_aware():
    """Use physical pixels, so screenshots, the window and gaze share one coordinate system."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def display_scale_percent():
    try:
        import ctypes
        return ctypes.windll.shcore.GetScaleFactorForDevice(0)
    except Exception:
        return None


def _make_grabber(backend):
    import cv2
    import numpy as np
    pc = time.perf_counter
    if backend == "mss":
        import mss
        sct = mss.mss()
        mon = sct.monitors[1]  # primary monitor

        def grab():
            t0 = pc()
            img = sct.grab(mon)
            t1 = pc()
            frame = cv2.cvtColor(np.asarray(img), cv2.COLOR_BGRA2BGR)
            return frame, (t0 + t1) / 2
        return grab
    if backend == "dxcam":
        import dxcam
        cam = dxcam.create(output_color="BGR")

        def grab():
            t0 = pc()
            frame = cam.grab()
            t1 = pc()
            return frame, (t0 + t1) / 2  # frame is None when the screen did not change
        return grab
    if backend == "pyautogui":
        import pyautogui

        def grab():
            t0 = pc()
            img = pyautogui.screenshot()
            t1 = pc()
            return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR), (t0 + t1) / 2
        return grab
    raise ValueError(f"unknown capture backend {backend!r}")


def _capture_main(path, stop, shared, backend, flush_every, scale):
    """Runs in its own process: grab screen, find bubble, write a row per frame."""
    set_dpi_aware()
    try:
        from study.gaze_core import detect_green_bubble
        grab = _make_grabber(backend)
    except Exception as e:  # report to the main process instead of dying silently
        shared[_ERR] = 1
        print(f"[gaze] capture could not start: {e!r}", file=sys.stderr, flush=True)
        return
    sx, sy = scale
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(GAZE_COLUMNS)
        last_flush = time.perf_counter()
        shared[_READY] = 1
        while not stop.is_set():
            frame, t = grab()
            if frame is None:
                time.sleep(0.001)
                continue
            shared[_FRAMES] += 1
            pos = detect_green_bubble(frame)
            if pos:
                x, y = pos[0] * sx, pos[1] * sy
                shared[_X], shared[_Y], shared[_T] = x, y, t
                shared[_FOUND] += 1
                w.writerow([f"{t:.6f}", f"{x:.0f}", f"{y:.0f}", 1])
            else:
                w.writerow([f"{t:.6f}", "", "", 0])
            if t - last_flush > flush_every:
                f.flush()
                last_flush = t


class GazeSource:
    """Common interface. latest() -> (x, y, age_s) or None."""
    name = "none"

    def start(self, folder, screen_size):
        self.t_start = time.perf_counter()

    def stop(self):
        self.t_stop = time.perf_counter()
        return {}

    def latest(self):
        return None

    def tick(self, now):
        pass

    # hints for the simulated reader; ignored by real sources
    def on_layout(self, lines):
        pass

    def on_target(self, xy):
        pass


class TobiiGhostSource(GazeSource):
    name = "tobii"

    def __init__(self, backend, flush_every=1.0):
        self.backend = backend
        self.flush_every = flush_every

    def start(self, folder, screen_size):
        super().start(folder, screen_size)
        ctx = mp.get_context("spawn")
        self.shared = ctx.Array("d", [math.nan, math.nan, 0.0, 0, 0, 0, 0], lock=False)
        self.stop_ev = ctx.Event()
        self.proc = ctx.Process(target=_capture_main, daemon=True, args=(
            os.path.join(folder, "gaze.csv"), self.stop_ev, self.shared, self.backend,
            self.flush_every, (1.0, 1.0)))
        self.proc.start()
        t0 = time.time()
        while not self.shared[_READY] and not self.shared[_ERR] and time.time() - t0 < 20:
            time.sleep(0.05)
        if not self.shared[_READY]:
            self.stop()
            raise RuntimeError(f"gaze capture did not start (backend {self.backend}); see the console")

    def stop(self):
        super().stop()
        if getattr(self, "proc", None) and self.proc.is_alive():
            self.stop_ev.set()
            self.proc.join(5)
            if self.proc.is_alive():
                self.proc.terminate()
        dur = self.t_stop - self.t_start
        frames, found = int(self.shared[_FRAMES]), int(self.shared[_FOUND])
        return {"frames": frames, "frames_with_bubble": found,
                "capture_hz": round(frames / dur, 1) if dur else None,
                "gaze_hz": round(found / dur, 1) if dur else None}

    def latest(self):
        t = self.shared[_T]
        if not t:
            return None
        return self.shared[_X], self.shared[_Y], time.perf_counter() - t

    def live_stats(self):
        dur = time.perf_counter() - self.t_start
        return {"capture_hz": self.shared[_FRAMES] / dur, "gaze_hz": self.shared[_FOUND] / dur,
                "alive": self.proc.is_alive()}


class _MainProcessSource(GazeSource):
    """Sources sampled from the main loop (mouse, sim)."""
    rate_hz = 60

    def start(self, folder, screen_size):
        super().start(folder, screen_size)
        self.f = open(os.path.join(folder, "gaze.csv"), "w", newline="")
        self.w = csv.writer(self.f)
        self.w.writerow(GAZE_COLUMNS)
        self.next_t = 0.0
        self.last = None
        self.frames = 0
        self.last_flush = time.perf_counter()

    def _sample(self, now):
        raise NotImplementedError

    def tick(self, now):
        if now < self.next_t:
            return
        self.next_t = now + 1.0 / self.rate_hz
        xy = self._sample(now)
        self.frames += 1
        if xy is None:
            self.w.writerow([f"{now:.6f}", "", "", 0])
            return
        self.last = (xy[0], xy[1], now)
        self.w.writerow([f"{now:.6f}", f"{xy[0]:.0f}", f"{xy[1]:.0f}", 1])
        if now - self.last_flush > 1.0:
            self.f.flush()
            self.last_flush = now

    def latest(self):
        if not self.last:
            return None
        return self.last[0], self.last[1], time.perf_counter() - self.last[2]

    def stop(self):
        super().stop()
        self.f.close()
        dur = self.t_stop - self.t_start
        return {"frames": self.frames, "frames_with_bubble": self.frames,
                "capture_hz": round(self.frames / dur, 1) if dur else None,
                "gaze_hz": round(self.frames / dur, 1) if dur else None}


class MouseSource(_MainProcessSource):
    name = "mouse"

    def _sample(self, now):
        import pygame
        return pygame.mouse.get_pos()


class SimulatedReader(_MainProcessSource):
    """Moves word by word along the current text, with noise, some re-reading and
    slower reading on some lines. Only for testing the software end to end."""
    name = "sim"
    rate_hz = 30

    def __init__(self, seed=1):
        self.rng = random.Random(seed)
        self.path = []      # list of (x, y, duration)
        self.idx = 0
        self.until = 0.0
        self.center = (960, 540)

    def start(self, folder, screen_size):
        super().start(folder, screen_size)
        self.center = (screen_size[0] / 2, screen_size[1] / 2)

    def on_layout(self, lines):
        path = []
        for li, line in enumerate(lines):
            for (word, x0, x1) in line["words"]:
                path.append(((x0 + x1) / 2, (line["band_y0"] + line["band_y1"]) / 2, self.rng.uniform(0.18, 0.32)))
            if li > 0 and self.rng.random() < 0.25:  # jump back to the previous line and re-read a bit
                prev = lines[li - 1]["words"]
                for (word, x0, x1) in prev[len(prev) // 2:]:
                    path.append(((x0 + x1) / 2, (lines[li - 1]["band_y0"] + lines[li - 1]["band_y1"]) / 2, 0.3))
        self.path, self.idx, self.until = path, 0, 0.0

    def on_target(self, xy):
        self.path, self.idx, self.until = [(xy[0] + 6, xy[1] - 4, 99.0)], 0, 0.0

    def _sample(self, now):
        if not self.path:
            x, y = self.center
        else:
            if now >= self.until:
                if self.until:
                    self.idx = min(self.idx + 1, len(self.path) - 1)
                self.until = now + self.path[self.idx][2]
            x, y, _ = self.path[self.idx]
        if self.rng.random() < 0.03:
            return None  # blink / lost frame
        return x + self.rng.gauss(0, 8), y + self.rng.gauss(0, 6)


def make_source(kind, backend="mss", flush_every=1.0, seed=1):
    if kind == "tobii":
        return TobiiGhostSource(backend, flush_every)
    if kind == "mouse":
        return MouseSource()
    if kind == "sim":
        return SimulatedReader(seed)
    if kind == "none":
        return GazeSource()
    raise ValueError(kind)
