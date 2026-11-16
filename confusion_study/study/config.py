"""Every setting of the study in one place. Change values here, not in the code.

Keep these the same for every participant: a change in layout or timing is a
change in the data. Each session saves a copy of these values in meta.json.
"""

# --- reading screen ---------------------------------------------------------
FONT_NAME = "arial"            # a system font; falls back to pygame's default
FONT_SIZE = 30                 # px
LINE_SPACING = 2.2             # line pitch = FONT_SIZE * LINE_SPACING (= 66 px)
TEXT_WIDTH = 1500              # px, max width of a text line
TEXT_TOP = 170                 # px from the top of the screen to the first line
BACKGROUND = (247, 247, 245)   # off-white. Nothing on screen may be green:
TEXT_COLOR = (25, 25, 25)      # the gaze capture looks for the green Ghost bubble.
MUTED_COLOR = (120, 120, 120)

# --- keys ------------------------------------------------------------------
CONFUSED_KEY = "c"
NEXT_KEY = "space"
ABORT_KEYS = ("ctrl", "q")     # experimenter: Ctrl+Q saves and quits
PAUSE_KEY = "f9"               # experimenter: pause + calibration check at the next paragraph

# --- timing ----------------------------------------------------------------
MIN_READ_S = 2.0               # Space is ignored this long after a paragraph appears
BREAK_S = 60                   # halfway break
BEEP_ON_CONFUSED = True        # short sound when C is pressed (no visual change on screen)

# --- trigger-point windows (used by build_windows.py) -----------------------
WINDOW_S = 5.0                 # gaze window before a C press (IJCAI 2016)
DROP_BEFORE_PRESS_S = 1.0      # removed from the end of the window (eye movement of pressing)

# --- calibration check (start, after the break, end) -----------------------
VALIDATION_GRID = [(x, y) for y in (0.12, 0.5, 0.88) for x in (0.1, 0.5, 0.9)]
VALIDATION_SETTLE_S = 0.8      # ignore gaze while the eyes move to the dot
VALIDATION_COLLECT_S = 1.2     # then average gaze for this long
# Vertical error must stay below this share of the line pitch, or we cannot
# tell which line the reader is on.
VALIDATION_MAX_DY_SHARE = 0.5

# --- gaze capture ----------------------------------------------------------
CAPTURE_BACKEND = "mss"        # "mss" (fast), "dxcam" (fastest, optional install), "pyautogui" (old pipeline)
FLUSH_EVERY_S = 1.0

# --- materials -------------------------------------------------------------
# Subset of materials/study_items.json used in the session (24 main paragraphs).
# Chosen so mean words per paragraph and mean FK grade are close to the full set:
#   articles  Ele 101.4 words / 8.75 grade (full 103.5 / 8.59),
#             Adv 126.7 words / 11.21 grade (full 127.9 / 11.27);
#   excerpts  67.1 words / 14.06 grade (full 67.2 / 14.16).
# Set both to None to use every item again (8 articles + 16 excerpts = 48 paragraphs).
# Order of ONESTOP_ARTICLES matters: list A reads the first half at Elementary and
# the second half at Advanced; list B the other way round. The two pairs are
# matched on length and grade.
ONESTOP_ARTICLES = ["A01", "A27", "A08", "A10"]
SPECIALIST_IDS = ["SP-MED-1", "SP-MED-2", "SP-LAW-2", "SP-LAW-4",
                  "SP-PHI-1", "SP-PHI-2", "SP-ECO-1", "SP-ECO-4"]
