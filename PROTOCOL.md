# Recording protocol — Experiment 3 (Tobii track)

Checklist for running reading sessions with `CONFUSION/collect.py`. Follow it the same way for every participant: differences in procedure become differences in the data. Background and reasons: `README.md` §6 (Stage 4), §10, §11.

---

## A. Once, before the study

- [ ] **Ethics / consent:** participants are recorded (gaze only, no video). Use your institute's consent process and form before the first session.
- [ ] **Texts:** choose ≥ 3 texts of graded difficulty and give each a fixed id. Each must fit **one full screen (F11) without scrolling**, about 15–25 lines, with **nothing green** on the page. Save them as local files (PDF/HTML) so every participant sees the identical page at the same zoom.

  | Text id | Difficulty | Source / file | Zoom % |
  |---|---|---|---|
  | T01 | easy (e.g. a children's story) | | |
  | T02 | medium (e.g. a news / encyclopedia article) | | |
  | T03 | hard (e.g. a technical textbook page) | | |

- [ ] **One fixed setup for all sessions:** same PC, monitor, resolution (1920×1080), Windows display scaling **100%**, same desk, chair and lighting. Tracker centred on the bottom bezel. `check_session.py` warns if the screen setup changes.
- [ ] **Participant ids:** P01, P02, … Keep the id → name list on paper or offline, **never in the repo**.
- [ ] **Text order:** rotate so no text is always read first or last (fatigue and practice effects):

  | Participant | Order |
  |---|---|
  | P01, P04, P07, P10 | T01 → T02 → T03 |
  | P02, P05, P08, P11 | T02 → T03 → T01 |
  | P03, P06, P09, P12 | T03 → T01 → T02 |

## B. Per participant (≈ 20 min)

1. [ ] Consent signed. Note the participant id on the session log (section D).
2. [ ] Seat at ~60 cm, centred, comfortable; ask them to keep their head fairly still.
3. [ ] **Calibrate** in Tobii Experience (Settings → Calibration). Tobii Ghost: preview ON, solid, `#CC10F61F`.
4. [ ] Check: the green bubble follows their gaze to all four screen corners and the centre. If not, recalibrate.
5. [ ] **Read the instructions aloud, word for word:**

   > "You will read three short texts on the screen, one at a time. Read each at your normal pace, as if you were studying it. Whenever you feel confused — you don't understand what you just read, or you lose the thread — click the 'Yes (Confused)' button in the bottom-right corner, then keep reading. Click as often or as rarely as you really feel confused; there are no right or wrong answers, and it is fine not to click at all. Please don't scroll, and try to keep your head still. Tell me when you have finished a text."

6. [ ] Optional practice: one short text that is not part of the study, so they can try the button once.

## C. Per text

1. [ ] Open the text full screen (**F11**) at its fixed zoom. **Wait until the "press Esc to exit full screen" banner has disappeared.** Close other windows; nothing green on screen.
2. [ ] In the terminal (in `IITJ_Project/IITJ_Project/CONFUSION`):
   ```
   python collect.py --participant P01 --text T01
   ```
3. [ ] During the 5-second countdown, switch to the text and don't move anything. The AOIs are captured.
4. [ ] Press **ESC** to start. The participant reads and clicks when confused. Don't talk to them.
5. [ ] When they say they're done: **Ctrl+Q** to stop.
6. [ ] Immediately run the quality check and open the AOI image:
   ```
   python check_session.py
   ```
   - **PASS** → continue.
   - **WARN** → write the reason on the session log; continue unless it says the AOIs are wrong.
   - **FAIL** → recalibrate (B.3–B.4) and record this text again (a new folder is created; note the failed one on the log).
7. [ ] Ask: "How difficult was this text, from 1 (very easy) to 5 (very hard)?" Write it on the session log.
8. [ ] ~1 minute break before the next text. Recalibrate if they moved, stood up, or the bubble looked off.

## D. Session log (paper or a spreadsheet, kept with the consent forms)

| Date | Participant | Text | Order | Session folder | QC result | Difficulty 1–5 | Notes (recalibrated? interruptions?) |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## E. After each day

- [ ] `python rebuild_fixations.py` and `python label.py`: new sessions are picked up automatically from `recordings/`.
- [ ] Commit the new `recordings/` folders on the `intern-work` branch (raw data is small; it is the ground truth for every later analysis).
- [ ] Copy the session log into the repo **without names** (participant ids only).
