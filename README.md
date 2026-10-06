# Gaze-Based Confusion Detection — Handover & Runbook

**Project:** Detecting reader confusion from eye movements (Tobii eye tracker) while reading text on screen.
**Lab:** Ubiquitous & Systems Research, IIT Jodhpur
**This document:** everything the next intern needs to reproduce the setup from zero, run every experiment exactly as the previous intern did, understand the known problems, and run the next set of experiments.

Read this top to bottom once before touching anything. The stages are in the exact order you must do them.

---

## 1. What this project is

The system shows a reader a page of text, records where their eyes go, converts the gaze stream into **fixations** (eyes holding still on a spot) and **saccades/regressions** (jumps, especially backward jumps), and tries to detect the moments the reader is **confused** — either with hand-written rules or with a trained ML model (Random Forest / XGBoost). Ground-truth confusion labels come from the reader clicking a "Yes (Confused)" popup while reading.

**Current status (August 2026):** the full pipeline runs end-to-end and there are working demos, but the trained model has a known label/feature-leakage flaw (§10) that means it learned *screen positions of confusing lines*, not *eye-movement signatures of confusion*. Fixing that is the first item of the next experiment plan (§11). Do not present the current model's accuracy as a result.

**There are two tracking methods in this repo.** This README covers the **Tobii track**. A second intern built a **webcam-only track** (MediaPipe iris tracking in the browser, no eye tracker hardware) — it lives in [`WEBCAM/`](WEBCAM/README.md) with its own runbook, a feature-parity analysis against this pipeline (which Tobii features the webcam can and cannot reproduce — saccades, AOIs, pupil), and its own task list. Read this document first, then that one.

### How gaze reaches Python (important — read this first)

The code does **not** use the Tobii SDK. Instead:

1. **Tobii Ghost** (a Tobii overlay app) draws a solid green bubble on screen at your gaze point, in a specific green: `#CC10F61F`.
2. Every Python capture script takes rapid full-screen screenshots with `pyautogui` and finds that green bubble with OpenCV color filtering (HSV hue 55–70).
3. The bubble's pixel position = the gaze point.

Consequences you must respect:

- **Nothing else green may be on screen** during recording (no green UI, wallpapers, or highlighted text), or detection jumps to it.
- **Never change the bubble color/shape** in Tobii Ghost — the HSV range in every script is tuned to `#CC10F61F`, solid.
- Effective sampling is limited by screenshot speed (~10–20 Hz in practice, vs the tracker's native 60+ Hz). This is a known limitation (§10.4).

---

## 2. Repository map

The code and data ship as a Git LFS zip. After cloning and unzipping (§3, step 3) you have:

```
IITJ_Project/
├── CONFUSION/          ← main pipeline: dataset collection → labeling → ML model → live prediction
│   ├── aoi.py            AOI extraction: OCR the reading page into one bounding box per text line
│   ├── aoi_c.py          small AOI helper/variant
│   ├── collect.py        DATA COLLECTION script (was cnn.py; one folder per session in recordings/):
│   │                     records gaze + fixations + "Yes (Confused)" clicks + scanpath images
│   ├── feature.py        older variant of the collection script (first half is dead commented code)
│   ├── label.py          converts confusion clicks into per-fixation 0/1 labels
│   ├── test.py           LIVE PREDICTION: loads trained model, shows "😕 Confused" popup per fixation
│   ├── confusion_model_rf4.pkl, confusion_model_xgb_new.pkl     trained models
│   ├── feature_names_order.pkl, feature_names_order_xgb_new.pkl feature column order for each model
│   ├── fixation_label_final.csv   the labeled training dataset (1,553 fixations, 559 labeled confused)
│   ├── data_logs/, demo_video_logs/, test_data_logs/            collected sessions (gaze/fixation/AOI CSVs)
│   └── test_aoi_debug/, demo_debug/                             AOI overlay debug screenshots
├── POPUP/              ← rule-based (no ML) confusion demos with ChatGPT visual aids
│   ├── main_label.py     3 regressions on a line OR 7 clustered fixations → popup → GPT labeled image
│   └── main_comic.py     same trigger → GPT 4-panel comic of the confusing passage
└── web/                ← Wikipedia reading study: gaze + mouse + per-paragraph helpfulness ratings
    ├── extension/        Chrome extension (Wikipedia only): annotate blocks 0–3, log mouse, export CSVs
    ├── main.py           gaze/fixation/saccade recorder to run alongside the extension
    ├── final.py          merges all CSVs into one block-level JSON dataset
    └── graph2.py, plot_help.py   analysis plots (KDEs, boxplots vs. helpfulness)
```

Also in the repo root:

- `WEBCAM/` — the webcam-only confusion detector (React + MediaPipe, no Tobii needed): vendored app source in `WEBCAM/app/` plus its own runbook and next-task list in [`WEBCAM/README.md`](WEBCAM/README.md).
- `DOCUMENTATION_.docx` — the previous intern's original write-up (this README supersedes it but keep it for reference).
- `working_video.zip` (Git LFS, ~374 MB) — **screen-recorded demos of every procedure below.** Watch the matching video before running each stage the first time:

| Video | Shows |
|---|---|
| `Enable_green_bubble` | Tobii Experience + Tobii Ghost setup (§4) |
| `DataCollection_of_Confusion` | AOI extraction + dataset collection (§5–6) |
| `Label_train_test_model` / `Test_model` | Labeling, training, live prediction (§7–9) |
| `LabelImage_popup` / `ComicScript_popup` | POPUP demos (§9.3) |
| `web_based_annotation` | Wikipedia study (§9.4) |

---

## 3. Stage 1 — Set up the computer (no Tobii needed yet)

**You need a Windows 10/11 PC.** Tobii Experience and Tobii Ghost are Windows-only, and the scripts use the `keyboard` library and Tk popups as configured for Windows.

1. **Install Git LFS, then clone.** Without LFS you get 130-byte pointer files instead of the zips.
   ```
   git lfs install
   git clone https://github.com/ubisysresearch/ResearchWork_Gaze.git
   ```
   Sanity check: `IITJ_Project.zip` should be ~24 MB and `working_video.zip` ~374 MB. If they are tiny text files, run `git lfs pull`.
2. **Install Python 3.10+** (tick "Add to PATH").
3. **Unzip `IITJ_Project.zip`** in the repo root so you get the `IITJ_Project/` tree shown in §2.
4. **Install Python dependencies:**
   ```
   pip install -r requirements.txt
   ```
5. **Install Tesseract OCR** (needed by `aoi.py`): download the Windows installer from https://github.com/UB-Mannheim/tesseract/wiki, install, and add its folder to PATH. Verify with `tesseract --version`.
6. **Fixed display setup:** pick the monitor, resolution, and Windows display scaling (100% recommended) you will use, and never change them between AOI extraction and recording sessions — all coordinates in this project are absolute screen pixels (§10.7).

---

## 4. Stage 2 — Connect and configure the Tobii (do this now, before any experiment)

1. **Mount the tracker** on the bottom bezel of your monitor (magnetic strip, centered) and **plug in the USB cable now.**
2. **Install "Tobii Experience"** from the Microsoft Store. Open it — it should detect the tracker.
3. **Calibrate:** Tobii Experience → Settings → Calibration, follow the dots.
   **Recalibrate for every new participant, and whenever the tracker or monitor is moved.** Uncalibrated gaze is silently wrong by centimeters; this ruins the data without any visible error.
4. **Install "Tobii Ghost"** from https://gaming.tobii.com/getstarted.
5. **Configure Tobii Ghost** (this is what the Python code depends on):
   - Preview → **ON**
   - Shape → **Solid**
   - Color → **`#CC10F61F`**
6. **Verify:** a solid green circle now follows your gaze everywhere on screen. Watch the `Enable_green_bubble` video if anything looks different.

The Tobii + Ghost bubble must be running during **every** recording below. If the bubble is off, the scripts see nothing and log nothing (they don't error — they just wait).

---

## 5. Stage 3 — Extract AOIs for a reading page (`CONFUSION/aoi.py`)

AOIs ("areas of interest") are one bounding box per text line, produced by OCR from a screenshot. They are used to count re-reads per line and for analysis — **not** as model features any more (§10.1). Redo AOIs **every time the reading page, window position, zoom, or resolution changes.**

**For recordings you don't run this stage separately:** `collect.py` (Stage 4) captures the AOIs itself at the start of every session, so the AOI file always belongs to that recording. Run `aoi.py` on its own only for the live demo's test page (§9.1).

1. Open the reading page **full screen (F11)** so browser tabs, the address bar and the taskbar aren't OCR'd as lines. **The whole text must be visible without scrolling** (§10.7). Nothing green on screen.
2. `cd IITJ_Project/CONFUSION`, then `python aoi.py` (add `--out <file.csv>` to choose the output, `--delay N` to change the countdown).
3. During the 5-second countdown, switch to the reading page and don't touch anything.
4. It writes the AOI csv (`AOI_ID, x1, y1, x2, y2`; default `demo_video_logs/aoi_lines_1.csv`) and a debug PNG with a green box per line (default `demo_debug/story_from_screenshot_with_aoistest2.png`). **Open the PNG and check every text line got its own tight box.**

---

## 6. Stage 4 — Record a session (`CONFUSION/collect.py`)

`collect.py` replaces `cnn.py` (which contained no CNN; it is in git history). One run = one session = one new folder; nothing is ever appended to an older session.

1. Green bubble running (Stage 2), participant **calibrated**, reading page full screen (F11), nothing green on screen.
2. `python collect.py --participant P01 --text T01` — use anonymous ids (keep the id → name key elsewhere) and a fixed id per text. Optional: `--notes "..."`, `--aoi <file.csv>` to reuse an existing AOI file instead of capturing.
3. During the 5-second countdown, switch to the reading page: the AOIs are captured. Then check `aoi_debug.png` in the session folder.
4. A small **"Gaze Capture"** window with a **"Yes (Confused)"** button sits at the bottom right.
5. Press **ESC** to start; the participant reads naturally and **clicks "Yes (Confused)" whenever they feel confused**. (Clicks before ESC are ignored.)
6. Press **Ctrl+Q** to stop (a plain `q` no longer stops it — typing it anywhere used to end the recording).

Output: `recordings/<participant>_<text>_<YYYYmmdd-HHMMSS>/`

| File | Contents |
|---|---|
| `gaze.csv` | every frame with the bubble: `gaze_x, gaze_y, timestamp, t` (`t` = seconds since epoch) |
| `fixations.csv` | one row per fixation, from `gaze_core.py`: position, `start_ts`, `end_ts`, `duration`, `dispersion`, corrected `saccade_before_duration` / `regression_flag` / `regression_type`, saccade dx/dy/amplitude, the old definitions as `*_legacy`, and the `aoi` line |
| `clicks.csv` | each confusion click: `timestamp, gaze_x, gaze_y, AOI_ID, t, gaze_age_s` (how old the last gaze sample was) |
| `aoi.csv`, `aoi_debug.png` | the AOIs captured for this session |
| `meta.json` | participant, text, duration, achieved capture/gaze rate (Hz), frames with bubble, screen size and display scaling, `gaze_core` parameters, git commit |

Right after each recording run `python check_session.py` (quality check: gaze rate, tracking loss, fixations on text, AOIs, clicks, screen setup → PASS/WARN/FAIL, saved as `qc.json`). For study sessions follow [`PROTOCOL.md`](PROTOCOL.md). New sessions are picked up automatically by `sessions.py`, so `python rebuild_fixations.py` and `python label.py` process them with everything else.

Fixation rule (`gaze_core.py`): gaze held within **25 px** for ≥ **0.25 s**; a bubble dropout under 0.5 s (a blink) doesn't end a fixation. Regression = ≥ 25 px leftward on the same line, or up to an earlier line. The capture loop has no fixed sleep or per-frame printing: **~31 frames/s on the lab PC vs ~18 for `cnn.py`.** 15 s scanpath PNGs are no longer drawn live (they can be rendered from `gaze.csv`).

---

## 7. Stage 5 — Label the fixations (`CONFUSION/label.py`)

Turns the confusion clicks into a `label` column (1 = confused) on `fixation.csv`.

> **Replaced on branch `intern-work` (§11 Exp. 1):** `label.py` now labels by *time* (fixation overlaps the 5/10/15 s before a click), for every session listed in `sessions.py`, from the corrected fixations made by `rebuild_fixations.py`. Run `python rebuild_fixations.py` then `python label.py`; outputs go to `processed/<session>/fixations_labeled.csv` and `processed/label_summary.csv`. The rest of this section describes the original script (still in git history at the baseline commit).

**This script is not runnable as-is on new data** — it has a session-specific hardcoded row range (`range(2, 33)`) and hardcoded file paths. For every new session you must edit it:

1. Point the two `read_csv` paths at your session's `fixation.csv` and `yes_click_log1.csv`.
2. Initialize the label column for **all** rows before the loop: `fixation_df['label'] = 0`.
3. Replace the hardcoded `range(2, 33)` so it iterates over **all** rows (`fixation_df.index`).
4. Run `python label.py` → writes `fixation_label.csv`.

**Known flaw in the labeling logic itself (§10.2):** it labels *every* fixation that ever landed in a clicked AOI as confused, across the whole session, with no time window. This is the root cause of the leakage problem and the first thing the next experiments must change (§11, Experiment 1). The existing labeled dataset built this way is `fixation_label_final.csv` (1,553 rows, 559 positive).

---

## 8. Stage 6 — Train the model (script missing — must be recreated)

> **Now exists on branch `intern-work` (§11 Exp. 2):** `CONFUSION/train.py` — behavioural window features only, leave-one-session-out evaluation, fixed seed; writes `processed/exp2_results.json` and `processed/exp2_windows.csv`. Run after `rebuild_fixations.py` and `label.py`. Results in §10.9. The rest of this section describes the original, unrecorded procedure.

**There is no training script in the repo.** The previous intern trained the `.pkl` models in an uncommitted notebook. The procedure they documented:

1. Load `fixation_label.csv` with pandas.
2. Drop non-feature columns: `start_time`, `end_time`, `fix_start_ts`; take `label` as the target `y`.
3. Train a Random Forest and an XGBoost classifier on the rest.
4. Save with joblib: the model (`confusion_model_*.pkl`) **and** the exact feature column order (`feature_names_order*.pkl`) — `test.py` needs both, in matching order.

**Before you train anything, read §10.1.** Reproducing the old training reproduces the leakage. The correct first experiment (§11) trains on behavioral features only, with grouped evaluation, and commits the script as `CONFUSION/train.py`.

---

## 9. Stage 7 — Run the demos

### 9.1 Live confusion prediction (`CONFUSION/test.py`)

1. Extract AOIs for the **test** page (Stage 3 procedure) and save as `test_data_logs/aoi_lines_test2.csv` (or update the path in `test.py`).
2. Confirm `confusion_model_xgb_new.pkl` + `feature_names_order_xgb_new.pkl` are present. **The AOI count of the test page must equal the training page's AOI count** or the feature columns won't line up (§10.1 — another symptom of the leakage design).
3. Green bubble on → `python test.py` → a "Confusion Prediction" popup appears → press **ESC** to start.
4. Per fixation it displays `AOI: AOI_X` plus "😕 Confused" or "waiting". Press **q** to stop.

### 9.2 What the rule-based demos detect

`POPUP/main_label.py` and `main_comic.py` skip ML entirely. A confusion event fires when either:
- **≥ 3 regression saccades on the same line** (saccade = jump faster than 450 px/s; same line = within 32 px vertically), or
- **≥ 7 fixations clustered in the same small area** (50 px radius).

On trigger: the confusing region is cropped from the screen, OCR'd (easyocr), and a popup asks "Are you confused?" — on Yes, ChatGPT generates a summary plus a labeled illustration (`main_label.py`) or a 4-panel comic (`main_comic.py`).

### 9.3 Running the POPUP demos

1. Both scripts contain `openai.OpenAI(api_key="enter you api key")`. **Do not paste your key into the file** (it will end up committed). Change the line to `api_key=os.environ["OPENAI_API_KEY"]` and set the environment variable in your terminal instead.
2. First run downloads easyocr model weights (~100 MB) — needs internet.
3. `cd IITJ_Project/POPUP`, `python main_label.py` (or `main_comic.py`), switch to the reading page, read; the popup fires on the rules above. Outputs land in `saved_images/` and `prompt_log*.json`.

### 9.4 Wikipedia reading study (`web/`)

Collects gaze + mouse + per-paragraph helpfulness ratings on real Wikipedia pages.

1. Chrome → `chrome://extensions` → Developer Mode ON → **Load unpacked** → select `IITJ_Project/web/extension/`. Works **only on Wikipedia**.
2. Open a Wikipedia article and refresh. Blocks get outlines and 0–3 helpfulness buttons; a sidebar appears.
3. `cd IITJ_Project/web`, `python main.py`, switch to the article, press **ESC** to start.
4. Read and rate each block 0–3 as you go. When done press **q**, then click **Export Logs** in the sidebar → downloads `annotations.csv` and `mouse_log.csv`.
5. Move both files into the session folder `main.py` wrote (`fixation.csv`, `saccade.csv`, `Gaze.csv`), update the paths in `final.py`, run `python final.py` → block-level JSON dataset.
6. Plots: update the JSON filename inside `graph2.py` (KDE distributions) and `plot_help.py` (boxplots vs. helpfulness), run each.

---

## 10. Known issues and limitations (read before designing anything)

1. **Feature/label leakage — the critical one.** The model's features include raw fixation position (`fix_x`, `fix_y`), `distance` from screen origin, and one-hot AOI flags, while labels were assigned *per AOI*. The model can (and by all evidence does) learn "line 7 of this story = confused" and cannot generalize to any new text. Any accuracy measured on a random train/test split of this data is meaningless. Fix: §11, Experiments 1–2.
2. **Labeling has no time window.** A single click marks every fixation ever made in that AOI as confused for the entire session. 36% of all fixations ended up labeled "confused," which is implausibly high.
3. **No training/evaluation code is committed.** Only model pickles exist; no split, no metrics, no seed.
4. **Screen-scraped gaze, not SDK gaze.** ~10–20 Hz effective sampling (screenshot-rate-bound) vs 60+ Hz native; genuine saccade dynamics (20–80 ms) are invisible, and **pupil diameter — one of the strongest confusion signals — is never captured.** The workaround exists because consumer Tobii trackers license-gate raw data access; a research-grade tracker or Pro SDK license removes it.
5. **`regression_flag` misses most regressions.** It only fires on *upward* movement; in reading, most regressions are *leftward within the same line*. Also `saccade_before_duration` is measured start-to-start, so it wrongly includes the previous fixation's duration.
6. **Per-fixation prediction is too fine-grained.** The literature detects confusion over windows (10–15 s aggregates: regression rate, fixation count/duration, saccade amplitude). Ironically `cnn.py` already collects 15 s windows for the scanpath images — the tabular pipeline should aggregate the same way.
7. **Everything is absolute screen pixels.** Any change to monitor, resolution, display scaling, window position, zoom, or a single scroll of the page invalidates the AOI file. Design experiments so the full text fits on one static screen.
8. **Code hygiene:** `cnn.py` contains no CNN; `feature.py` and `test.py` are ~half dead commented-out code; the green-bubble detector is copy-pasted into six files; filenames are hand-edited constants that drift between scripts (§5 warning).

### 10.9 Findings from the reproduction (branch `intern-work`)

Measured while reproducing stages 3–7 and auditing the old data. Status in brackets.

- **The 20 training sessions were appended into one file.** `cnn.py` opens `fixation.csv` in append mode, so all sessions (11–13 July 2025) went under the first session's header; 3 rows even have an extra column. Each session read a *different page* with its own 18-line AOI file, so the column `AOI_5` means "the 4th line on screen" — a different sentence in every session. The shipped XGBoost model takes **72% of its gain from these AOI columns** (+9% from `fix_x`/`fix_y`/`distance`): it learned *which screen line*, not *how the eyes move* (§10.1). *[Fixed: `rebuild_fixations.py` writes one file per old session; new recordings use `collect.py`, one folder per session.]*
- **The old data was sampled at only 5–8 Hz** (not 10–20 Hz as §10.4 says); the new PC gets ~18 Hz. At 5–8 Hz a 0.25 s fixation rests on 2–3 samples.
- **`regression_flag` was mostly noise, not just incomplete.** It fired on *any* upward move, including 1-px jitter: 38% of all fixations were flagged, and 89% of those flags moved up ≤ 25 px (median 6 px) — same line. It also missed 115 of 180 genuine leftward regressions. *[Fixed in `gaze_core.py`: leftward ≥ 25 px on the same line, or up to an earlier line → 15% of fixations.]*
- **`saccade_before_duration` was start-to-start** (median ≈ 1.3 s); corrected end-to-start median ≈ 0.65 s. At these sampling rates it is the *time between fixations*, not a saccade duration. *[Fixed in `gaze_core.py`.]*
- **One missed screenshot discarded the fixation in progress.** `cnn.py` reset on any frame without a bubble (a blink, a flicker). *[Fixed in `gaze_core.py`: only a gap > 0.5 s ends a fixation.]*
- **`gaze_core.py` is validated against the original:** run on the old raw gaze files with the original reset rule, it reproduces 99.1% of the 1,553 fixations `cnn.py` logged (`python validate_gaze_core.py`).
- **`test.py` as shipped crashes**: `test_data_logs/aoi_lines_test2.csv` has 19 AOIs; the model needs exactly 18. It also predicts twice per fixation, the first time with a hardcoded duration of 0.25 s.
- **A confusion click made while looking outside every AOI is lost**: it is logged with `AOI_ID = None` and `label.py` skips it. (Time-window labelling — §11 Exp. 1 — does not need the AOI, so this goes away.)
- **`aoi.py`** took its screenshot instantly, always overwrote the same filename, and OCRs browser tabs, the address bar and the taskbar — use a full-screen (F11) page. *[Fixed: 5 s countdown, `--out` option; `collect.py` captures AOIs into each session folder.]*
- **Who read the 20 old sessions is unknown** — not recorded, and nobody in the lab knows; possibly a single reader. Treat every result on them as *within the unknown reader(s)*, not across people. `collect.py` now requires `--participant`.
- **`cnn.py` reached only ~18 frames/s** although a screenshot takes ~20 ms and bubble detection ~3 ms (≈ 44 Hz possible): a fixed 20 ms sleep and per-frame console printing ate the rest. *[Fixed in `collect.py`: ~31 frames/s on the lab PC.]*
- **First `collect.py` test (TEST_T00, 2.2 min):** 35 frames/s captured, bubble found in 82% → **29 Hz gaze** (old data 5–8 Hz); median 33 ms between samples; live fixations identical to the offline rebuild. Two observations: (1) **the gaze at a click is almost always on the button itself** (2 of 3 clicks), so a click's `AOI_ID` says little about the confusing line — another reason to label by time, not by AOI. (2) Pressing F11 shows a "press Esc to exit full screen" banner for a few seconds; it was OCR'd as an AOI — press F11 a few seconds *before* starting `collect.py`.
- **Timestamps:** the capture scripts write *local* wall-clock time strings. `sessions.to_seconds()` read them as UTC (5.5 h off in India) until the TEST session exposed it against `collect.py`'s true-epoch `t` column. Fixed; labels and all results were unaffected, because clicks and fixations had always been converted the same way.
- **`label.py` reads `CONFUSION/fixation.csv`** (an old file), not the session's `demo_video_logs/fixation.csv`.
- **Experiment 1 result (time-window labels, 20 old sessions, 1,616 corrected fixations).** Positive rate: 16% (5 s), 26% (10 s), 35% (15 s). So the "implausible 36%" of §10.2 comes mostly from the 15 s window length, not only from labelling by place; the place rule and the 15 s time rule disagree on just 16% of fixations here, because a reader's fixations on one line also cluster in time. (On a session with many clicks on different lines — s21 — they disagree on 47%.) The important change is *what the labels mean*: time labels mark *when* the reader was confused and don't depend on line identity, so they can't leak position into a model. **Behaviour differs before clicks** (5 s window, paired per session): regression rate higher in 19/19 sessions with clicks (median +0.18), fixations longer in 17/19 (+0.13 s), saccades shorter in 19/19 (−95 px); Wilcoxon p < 0.001 each. Not caused by glances at the click button (0 fixations on it inside windows); unchanged when only fixations on text lines are used (19/19). Caveats: probably one reader; self-report clicks; fixations inside one window are not independent (hence per-session tests).
- **Experiment 2 result — the honest baseline** (`train.py`). Unit: 10 s windows, step 1 s; positive = window ends 0–3 s before a click; windows containing a click dropped; 13 behavioural features, no position or line identity. 2,357 windows from the 20 old sessions, 166 positive (7%).

  | Setup | Evaluation | ROC-AUC | PR-AUC (chance) |
  |---|---|---|---|
  | **Behavioural windows, XGBoost** | leave-one-session-out | **0.76** | **0.29** (0.07) |
  | Behavioural windows, Random Forest | leave-one-session-out | 0.76 | 0.23 (0.07) |
  | Regression rate alone (no ML) | — | 0.71 | 0.15 (0.07) |
  | Same models, train 20 old → test s21 (new PC, 18 Hz) | external | 0.55–0.63 | 0.24–0.30 (0.20) |
  | *Old setup* (position + AOI one-hot, place labels, per fixation), XGBoost | random 80/20 split | 0.87 | 0.84 (0.36) |
  | *Old setup*, XGBoost | leave-one-session-out | 0.74 | 0.62 (0.36) |

  Reading it: (1) Behaviour alone detects the run-up to a confusion click well above chance on **unseen sessions/texts** — AUC 0.76, PR-AUC ~4× chance, AUC > 0.5 in 18/19 sessions with clicks. (2) ML adds a modest gain over regression rate alone (0.76 vs 0.71). (3) The old setup loses 0.13 AUC when moved from a random split to unseen sessions — that gap is the leakage made visible; its numbers are not comparable to ours otherwise (different labels, unit and prevalence). (4) The s21 test is near chance but tiny (46 windows, 9 positive) and differs in sampling rate and probably reader — inconclusive; it shows why Exp. 3 needs more readers and the same capture setup. (5) Window-length check (chosen 10 s before looking): 5 s → AUC 0.68–0.69, 10 s → 0.76, 15 s → 0.79–0.81. Longer windows help at 5–8 Hz. Strongest features (RF): leftward-regression rate, mean saccade amplitude, mean fixation duration, re-read rate. *(Numbers corrected after a bug fix: pandas reads the AOI text `None` as NaN, so off-text fixations — 4% — were counted as re-reads; AUCs moved by ≤ 0.01, s21 by up to +0.05.)* Caveats as Exp. 1, plus: one dataset, most likely one reader — **not yet a generalisation claim across people**.

---

## 11. Next set of experiments (in this order)

**Experiment 1 — Re-label by time, not by place.** Write a new `label.py`: a fixation is confused iff its time falls inside a window before a click (start with 15 s, matching the scanpath segments; try 5/10/15 as a sensitivity check). Rebuild the labeled dataset from the existing raw logs — no new data collection needed for this step.

**Experiment 2 — Behavioral features only, honest evaluation.** Drop `fix_x`, `fix_y`, `distance`, and all AOI one-hot columns. Keep/add: duration, dispersion, corrected regression flag (leftward *or* upward), corrected saccade duration (current start − previous *end*), saccade amplitude, re-reading count per line. Aggregate per 10–15 s window (counts, means, rates). Train RF/XGBoost; evaluate with **leave-one-text-out** and, once multiple readers exist, **leave-one-participant-out**. Commit `train.py` and the metrics. *Expect accuracy to drop versus the old model — that drop is the honest baseline, and it is the result to report.*

**Experiment 3 — Multi-text, multi-participant dataset.** ≥ 3 texts of graded difficulty (easy / medium / hard — hard texts generate real confusion events), ≥ 10 participants, calibration per participant (§4.3), fixed protocol: calibrate → AOI extract → read → click when confused → rest. Keep every session's raw logs, and record participant ID + text ID in the filenames. **Step-by-step checklist, participant instructions, text order and session log: [`PROTOCOL.md`](PROTOCOL.md).** Run `python check_session.py` after every recording.

**Experiment 4 — Real gaze stream.** Get SDK-level access (Tobii Pro Spark or a Pro SDK-licensed device): 60+ Hz gaze plus **pupil diameter**, proper I-VT fixation/saccade classification, and add pupil-dilation features to Experiment 2's set. If stuck with the Ghost bubble, first measure and report its true sampling rate (timestamps in `gaze.csv`).

**Experiment 5 — Close the loop.** Only after 2–4 hold up: connect the validated model to the POPUP intervention (summary/comic on *predicted* confusion instead of rule triggers) and run a small user study: does the intervention actually help comprehension (quiz scores) vs. a no-intervention control?

**Experiment 6 — Webcam track (parallel effort).** Bring the webcam-only detector up to research grade and validate it against the Tobii: tasks W1–W7 in [`WEBCAM/README.md`](WEBCAM/README.md) §5. The centerpiece is W5 — recording webcam and Tobii **simultaneously** on the same reader (they don't conflict: the webcam never reads the screen, so the Ghost bubble stays on) to measure exactly how much accuracy the webcam loses. The end goal is the comparison study: same labels, same evaluation, Tobii features vs. webcam features (W7).

**Ongoing — cleanup as you touch things:** delete the dead commented halves, extract the shared bubble/fixation code into one module imported everywhere *(done: `gaze_core.py`, used by `collect.py`; `test.py`, `feature.py`, `POPUP/`, `web/` still have their own copies)*, rename `cnn.py` → `collect.py` *(done)*, and keep `requirements.txt` current.

---

## 12. Quick reference

| Key | Value |
|---|---|
| Ghost bubble color | `#CC10F61F`, solid, preview ON |
| Bubble HSV detection range | hue 55–70, S ≥ 180, V ≥ 180 |
| Fixation definition | ≤ 25 px movement held ≥ 0.25 s |
| Saccade velocity threshold (POPUP) | 450 px/s |
| Rule triggers (POPUP) | 3 regressions on a line, or 7 fixations in 50 px cluster |
| Confusion window on click | 15 s before click |
| Start / stop recording | ESC / q (all capture scripts) |
| Labeled dataset | `CONFUSION/fixation_label_final.csv` — 1,553 fixations, 559 positive |
| Best current model | `confusion_model_xgb_new.pkl` + `feature_names_order_xgb_new.pkl` (⚠ §10.1) |
