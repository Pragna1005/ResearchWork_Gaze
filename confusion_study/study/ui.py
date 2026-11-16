"""Window, drawing and keyboard input (pygame).

The window is a borderless window the size of the screen, not exclusive
full screen, so the Tobii Ghost overlay stays visible to the screen capture.
"""
import os
import time

import pygame

from study import config as C
from study.layout import wrap


class Abort(Exception):
    """Experimenter pressed Ctrl+Q."""


KEY_ALIASES = {"[1]": "1", "[2]": "2", "[3]": "3", "[4]": "4", "[5]": "5", "[6]": "6",
               "[7]": "7", "[8]": "8", "[9]": "9", "[0]": "0", "enter": "return", "keypad enter": "return"}


class UI:
    def __init__(self, size=None, windowed=False):
        os.environ.setdefault("SDL_VIDEO_WINDOW_POS", "0,0")
        pygame.init()
        if size is None:
            size = pygame.display.get_desktop_sizes()[0]
        flags = 0 if windowed else pygame.NOFRAME
        self.screen = pygame.display.set_mode(size, flags)
        pygame.display.set_caption("Reading study")
        self.w, self.h = self.screen.get_size()
        self.clock = pygame.time.Clock()
        self.font_path = pygame.font.match_font(C.FONT_NAME)
        self.font = self._font(C.FONT_SIZE)
        self.small = self._font(24)
        self.big = self._font(36)
        self.pitch = int(round(C.FONT_SIZE * C.LINE_SPACING))
        self.left = max(40, (self.w - C.TEXT_WIDTH) // 2)
        self.text_width = min(C.TEXT_WIDTH, self.w - 2 * self.left)
        self.beep = self._make_beep()
        self.pause_requested = False
        self.auto = None  # set by tests: an object that answers instead of a person
        pygame.key.set_repeat()  # no auto-repeat: holding C gives one press

    def _font(self, size):
        return pygame.font.Font(self.font_path, size) if self.font_path else pygame.font.Font(None, size)

    def _make_beep(self):
        if not C.BEEP_ON_CONFUSED:
            return None
        try:
            import numpy as np
            pygame.mixer.init(44100, -16, 1)
            t = np.arange(int(44100 * 0.06)) / 44100
            wave = (0.25 * 32767 * np.sin(2 * np.pi * 700 * t) * np.hanning(len(t))).astype(np.int16)
            return pygame.mixer.Sound(buffer=wave.tobytes())
        except Exception:
            return None

    # --- drawing ------------------------------------------------------------
    def clear(self):
        self.screen.fill(C.BACKGROUND)

    def flip(self):
        pygame.display.flip()
        return time.perf_counter()

    def layout(self, text, top=None, font=None, pitch=None, left=None, width=None):
        return wrap(font or self.font, text, self.left if left is None else left, C.TEXT_TOP if top is None else top,
                    width or self.text_width, pitch or self.pitch)

    def draw_lines(self, lines, font=None, color=None):
        font = font or self.font
        for ln in lines:
            self.screen.blit(font.render(ln["text"], True, color or C.TEXT_COLOR), (ln["x0"], ln["y0"]))

    def message(self, text, top=None, size=28, spacing=1.6, color=None, width=1300):
        """Draw a block of (multi-paragraph) text; returns the y below it."""
        font = self._font(size)
        pitch = int(size * spacing)
        left = (self.w - min(width, self.w - 80)) // 2
        y = top if top is not None else 120
        for para in text.split("\n"):
            if not para.strip():
                y += pitch // 2
                continue
            lines = wrap(font, para, left, y, min(width, self.w - 80), pitch)
            self.draw_lines(lines, font, color)
            y += pitch * len(lines)
        return y

    def footer(self, text):
        surf = self.small.render(text, True, C.MUTED_COLOR)
        self.screen.blit(surf, ((self.w - surf.get_width()) // 2, self.h - 70))

    def dot(self, x, y):
        pygame.draw.circle(self.screen, (200, 30, 30), (int(x), int(y)), 14)
        pygame.draw.circle(self.screen, (20, 20, 20), (int(x), int(y)), 4)

    # --- input --------------------------------------------------------------
    def poll(self, tag=""):
        """Return a list of (key_name, unicode, t) since the last call. Handles Ctrl+Q and F9."""
        out = []
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                raise Abort()
            if ev.type == pygame.KEYDOWN:
                t = time.perf_counter()
                name = KEY_ALIASES.get(pygame.key.name(ev.key), pygame.key.name(ev.key))
                if name == "q" and ev.mod & pygame.KMOD_CTRL:
                    raise Abort()
                if name == C.PAUSE_KEY:
                    self.pause_requested = True
                out.append((name, ev.unicode, t))
        if self.auto is not None:
            out.extend(self.auto.keys(tag))
        return out

    def wait_key(self, allowed, tag="", gaze=None, redraw=None):
        """Block until one of `allowed` is pressed. Returns (key, t)."""
        while True:
            now = time.perf_counter()
            if gaze is not None:
                gaze.tick(now)
            if redraw:
                redraw(now)
            for name, uni, t in self.poll(tag):
                if name in allowed:
                    return name, t
            self.clock.tick(250)

    def text_input(self, prompt, tag="", allowed_chars=None, max_len=60, gaze=None, hint=""):
        """Type a short answer, Enter to confirm. Returns the string."""
        value = ""
        pygame.key.start_text_input()
        try:
            while True:
                self.clear()
                y = self.message(prompt, top=200)
                box = pygame.Rect(self.w // 2 - 400, y + 40, 800, 60)
                pygame.draw.rect(self.screen, (255, 255, 255), box)
                pygame.draw.rect(self.screen, (60, 60, 60), box, 2)
                self.screen.blit(self.big.render(value + "|", True, C.TEXT_COLOR), (box.x + 12, box.y + 8))
                self.footer(hint or "Type your answer, then press Enter")
                self.flip()
                if self.auto is not None:
                    return self.auto.text(tag)
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        raise Abort()
                    if ev.type == pygame.KEYDOWN:
                        if pygame.key.name(ev.key) == "q" and ev.mod & pygame.KMOD_CTRL:
                            raise Abort()
                        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                            return value.strip()
                        if ev.key == pygame.K_BACKSPACE:
                            value = value[:-1]
                    if ev.type == pygame.TEXTINPUT:
                        ch = ev.text
                        if allowed_chars is None or all(c in allowed_chars for c in ch):
                            value = (value + ch)[:max_len]
                if gaze is not None:
                    gaze.tick(time.perf_counter())
                self.clock.tick(60)
        finally:
            pygame.key.stop_text_input()

    def choice(self, prompt, options, tag="", footer=None):
        """Numbered options, answered with keys 1..n. Returns (index, t)."""
        self.clear()
        y = self.message(prompt, top=180)
        y += 30
        for i, opt in enumerate(options):
            y = self.message(f"{i + 1}.   {opt}", top=y + 8, size=28, width=1100)
        self.footer(footer or f"Press a number key (1-{len(options)})")
        self.flip()
        key, t = self.wait_key([str(i + 1) for i in range(len(options))], tag)
        return int(key) - 1, t

    def pause_screen(self, text, keys=("space",), tag=""):
        self.clear()
        self.message(text, top=180)
        self.flip()
        return self.wait_key(list(keys), tag)

    def close(self):
        pygame.quit()
