# Reading-confusion study: data collection software

Runs one participant's whole session, as planned on the "Data collection plan" slides:
questionnaire → LexTALE → calibration check → practice → 24 paragraphs (C = confused,
Space = next, a question after each news paragraph, a break halfway) → confirm the C presses.
Gaze comes from the Tobii Ghost bubble, captured the same way as `CONFUSION/collect.py`
(same `gaze_core.py`), in a separate process so the reading screen never waits.

## 1. Install (once, on the lab PC with the Tobii)

1. Python 3.10 or newer, then in this folder:
   ```
   pip install -r requirements.txt
   ```
2. Windows display settings: **1920×1080, scaling 100%** (same as the old protocol).
3. Tobii Ghost: preview ON, solid, colour `#CC10F61F` (as in `PROTOCOL.md`). Nothing else on screen may be green.
4. Check the paragraphs fit this screen: `python preview_materials.py` (writes `previews/*.png`).

## 2. Rehearse before the first participant

```
python run_session.py --participant TEST --gaze mouse
```
The mouse stands in for gaze. Go through everything once yourself; `TEST` can be reused.
Then do a short real run with the tracker and check the gaze rate:
```
python run_session.py --participant TEST --skip questionnaire,lextale,practice --max-trials 4
python check_session.py
```
`gaze rate` should be 20 Hz or more. If gaze is never found, try `--backend pyautogui`
(slower, but exactly what the old pipeline used) or `--backend dxcam` (after `pip install dxcam`).

## 3. Each session

1. Consent form signed. Use ids P01, P02, …; keep the id-to-name list on paper, never in this folder.
2. Seat the participant about 60 cm away. **Calibrate in Tobii Experience.**
3. Start: double-click `run_session.bat` (asks for the id), or
   ```
   python run_session.py --participant P01
   ```
4. The participant does the questionnaire and LexTALE alone. Stay for the **calibration check**:
   the screen shows the error per dot and says OK / NOT OK. If NOT OK: recalibrate in
   Tobii Experience (Alt+Tab), come back, press **R** to repeat. **Enter** continues.
5. Read the instructions on screen together. Don't talk during reading.
6. The break and the second calibration check come automatically halfway.
7. After the final screen, run `python check_session.py` (the .bat does this).

| Experimenter key | What it does |
|---|---|
| **Ctrl+Q** | Stop and save everything so far (session marked as stopped early); continue later with `--resume` (below) |
| **F9** | Pause after the current paragraph → recalibrate → calibration check → continue |
| **R / Enter** | On the calibration-check result screen: repeat / continue |

Participant keys: **C** confused, **Space** next paragraph, **1–4** answers, **Y/N** in LexTALE.

### Continuing a stopped session

If you stopped with Ctrl+Q (e.g. to recalibrate) or the program crashed:
```
python run_session.py --participant P02 --resume
```
- Writes a **new, linked folder** `data/P02_<date-time>_part2/`; the earlier folder is never changed. `meta.json` of the new part has `resume_of`, `first_part`, `resumed_at_trial` and `reread_trials`.
- Same plan and order (read from the first part's `plan.json`). Starts with a calibration check, then continues at the first paragraph that has no saved row. A paragraph cut off mid-way is read again from the start; its old presses stay in the earlier folder but are not used.
- Questionnaire, LexTALE and practice are skipped if an earlier part finished them (practice runs if it was never finished; add `--skip practice` to leave it out).
- The break (if not reached yet), final calibration check and the confirmation step for the presses of **all** parts run as usual. `summary.json` of the last part covers the whole session.
- Can be repeated (`_part3`, …). `check_session.py` shows earlier parts as WARN "continued in …"; `build_windows.py` keeps window ids unique (`P02-part2-W001`) and takes the confirmations from the last part.

## 4. After sessions

```
python check_session.py data/P01_...     # quality report, saved as qc.json
python build_windows.py                  # labelled 4-s gaze windows for all sessions -> data/all_windows.csv
```

## 5. What is saved (`data/<id>_<date-time>/`)

| File | Contents |
|---|---|
| `gaze.csv` | every captured frame: `t`, `x`, `y`, `found` (1 = bubble found) |
| `events.csv` | everything that happened on screen, with `t` |
| `trials.csv` | one row per paragraph: item, level (Ele / Adv / Spec), on/off time, reading time, presses, question, answer |
| `presses.csv` | every C press: time, gaze at that moment, line and word under the gaze |
| `layout_words.csv` | position of every word and line on screen, per paragraph (to map gaze to text) |
| `confirmations.csv` | the reader's own check of each pressed paragraph: confused yes/no/not sure, which lines, why |
| `questionnaire.json`, `lextale.csv` | answers; LexTALE score is in `summary.json` |
| `validation.csv` | calibration checks: target, measured gaze, error per dot |
| `plan.json` | this participant's paragraph order, list A/B and seed |
| `meta.json`, `summary.json` | settings, screen, gaze rate, completed or not; presses and accuracy per level |
| `windows.csv`, `window_gaze.csv` | after `build_windows.py`: labelled windows and their gaze samples |

**Clock:** `t` is `time.perf_counter()` in every file (the same counter in both processes on
Windows), so gaze and key presses line up directly. `meta.json → clock` converts it to a date and time.

## 6. Design details, and where they differ from the slides

- **Items used:** 4 of the 8 OneStop articles (A01, A27, A08, A10 → 16 paragraphs) and 8 of the 16 excerpts (2 per domain: SP-MED-1/2, SP-LAW-2/4, SP-PHI-1/2, SP-ECO-1/4), chosen so mean length and FK grade match the full set. The list is in `study/config.py` (`ONESTOP_ARTICLES`, `SPECIALIST_IDS`); `study_items.json` still holds every item. Set both to `None` to go back to all 48 paragraphs.
- **Lists A/B:** odd participant numbers read A01 and A27 as Elementary and A08 and A10 as Advanced; even numbers the other way round. Nobody sees both versions of an article.
- **Order:** the four paragraphs of an article stay together and in order; reading paragraph 3 of a news story before paragraph 1 would be confusing for the wrong reason. Each half of the session has 1 Elementary article, 1 Advanced article and 4 excerpts (one per domain), so difficulty isn't tied to tiredness. Which article and which excerpt of each pair is in the first half is counterbalanced by participant number (exactly balanced over every 16 consecutive ids, e.g. P01–P16); within a half, the blocks (articles and excerpts) are shuffled, seeded by the id, so the order can be reproduced. `python tests/test_plan.py` checks these rules and prints the counts.
- **Specialist excerpts:** from medicine, law, philosophy and **economics** (OpenStax). The slides list literature; no openly licensed literature text could be fetched. Swap them by editing `materials/build_materials.py`.
- **Questions:** the first of OneStopQA's three questions, after each OneStop paragraph (none after excerpts). The four options are shuffled on screen; the correct one is logged.
- **Extra measurements beyond the slides:**
  - a small dot before each paragraph, which shows where the first line starts and measures drift;
  - a 9-dot calibration check at the start, after the break and at the end;
  - "which line?" in the confirmation step, which tests whether gaze finds the right line.
- **Length:** 24 paragraphs (about 2,300–2,400 words) plus 16 questions. Time the pilot.

## 7. Materials (`materials/`)

`study_items.json` holds every text, unmodified, with its source, licence, word count and
readability grade. `build_materials.py` documents how it was built. Credits are in `materials/SOURCES.md`.

## 8. For developers

- All settings are in `study/config.py`: font, spacing, keys and timings. Keep them fixed once the study starts.
- `python tests/test_plan.py` checks the trial-list design (24 items, levels, halves, lists A/B, balance) in a few seconds.
- `python tests/test_full_session.py` runs a full session with a scripted participant and a simulated reader. Add `--long` for realistic reading times. No screen or tracker is needed.
- The bubble detector and fixation code are a copy of `CONFUSION/gaze_core.py` from the main repo.
