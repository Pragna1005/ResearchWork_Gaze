# Webcam-Based Confusion Detection — Handover & Runbook

The second tracking method in this project: confusion detection with **no eye tracker at all**, just a standard webcam, running entirely in the browser. Built by a previous intern (original repo: https://github.com/gubbalabhargavi/Confusion_Detection-mobile-pervasive-computing-project- , live demo: https://webcame-based-confusion-detector-60xav2l5e.vercel.app/). The full source is vendored in `WEBCAM/app/` so this repo is self-contained.

Read the main repo `README.md` first — this document assumes you know the Tobii pipeline, because the whole point of this folder is comparing the two and closing the gap between them (§4–5).

---

## 1. What it is and how it works

A React + TypeScript single-page app. Everything runs client-side in the browser:

1. **Iris tracking** — Google **MediaPipe FaceLandmarker** finds 478 face landmarks per webcam frame; the iris landmarks (indices 469–472 and 474–477) give each iris center.
2. **"Gaze" mapping** — the two iris centers' *position within the camera image* is scaled directly to window coordinates (`App.tsx`, `predictWebcam`). ⚠️ Understand what this means: **there is no calibration and no eye-rotation model** — the mapped point mostly follows your *head position*, not your true gaze. See §4 before trusting any output.
3. **Fixation detection** — a proper **I-DT (dispersion-threshold) algorithm** (`services/gazeProcessor.ts`): gaze points within a 50 px dispersion for ≥ 150 ms form a fixation with centroid, duration, and dispersion.
4. **Regression detection** — a fixation jump ≥ 80 px *leftward* while staying within 50 px vertically (same line) counts as a regression. Note this is the *correct* reading-regression definition — the Tobii pipeline's `regression_flag` only checks upward movement (main README §10.5).
5. **Confusion score** — a heuristic accumulator: regression +60, fixation longer than 400 ms +5, gaze–mouse distance over 300 px +2, decaying 0.5/frame. Score above 100 → status flips to "CONFUSION DETECTED".
6. **Adaptive threshold** — after each session the user rates the detection; "inaccurate" nudges the threshold ±10% and persists it in `localStorage`.

All tunable parameters live in `app/constants.ts`.

**What it does NOT do (yet):** no data logging of any kind (no gaze/fixation CSVs, nothing exportable), no AOI concept, no confusion-click ground truth, no trained model — the "detector" is the hand-tuned score above. Closing exactly these gaps is the task list in §5.

---

## 2. Build and run

Needs: **Node.js 18+**, a webcam, Chrome/Edge, and **internet at runtime** (the app pulls Tailwind, React, the MediaPipe WASM bundle, and the FaceLandmarker model from CDNs — it will not work offline as-is).

```bash
cd WEBCAM/app
npm install
npm run dev        # → http://localhost:3000
```

1. Open the URL, allow camera access when prompted.
2. Sit centered, face evenly lit, roughly 50–70 cm from the screen. Keep your head as still as you can (§4 explains why this matters so much).
3. Click **Start Detection**. A cyan dot shows the mapped gaze point; the sidebar shows live status and the confusion-score bar.
4. Read the built-in text panel. Regressions and long stares push the score up; crossing the threshold flips the status to "CONFUSION DETECTED".
5. Click **Stop Detection** → session summary → answer the accuracy question (this tunes the threshold for the next session).

Production build: `npm run build` → static files in `dist/` (deployable anywhere, e.g. Vercel like the original).

Notes:
- The app was generated with Google AI Studio; `vite.config.ts` references a `GEMINI_API_KEY` env var, but **nothing in the code uses it** — no key is needed.
- `index.html` carries a CDN import map that overrides `node_modules` in the browser; that's why runtime internet is required even after `npm install`.
- The "Calibrating" status exists in `types.ts` but is never used — there is no calibration step (§5, task W2).

---

## 3. Code map

```
WEBCAM/
├── README.md                  ← this document
└── app/
    ├── App.tsx                  everything: webcam loop, MediaPipe, gaze mapping, scoring, UI
    ├── services/gazeProcessor.ts  I-DT fixation detection + regression detection (the research core)
    ├── constants.ts             every tunable parameter in one place
    ├── types.ts                 data structures (GazePoint, Fixation, Regression, …)
    ├── components/IconComponents.tsx, index.tsx, index.html, vite.config.ts, package.json
    └── README_original.md       the intern's original write-up
```

---

## 4. Feature parity: webcam vs. Tobii — the honest assessment

The question this section answers: **can the webcam method produce all the features the Tobii pipeline derives (fixations, saccades, regressions, AOIs, …)?** Short answer: *most of them coarsely, some only after the fixes in §5, and two not at all — but the webcam also offers two features the Tobii setup can't.*

The fundamental constraint is **spatial accuracy**. The current head-position mapping has no meaningful accuracy at all (turn your eyes without moving your head — the dot barely moves). Even *after* adding proper calibration (task W2), webcam gaze tops out around **3–5° of visual angle ≈ 100–200 px** at normal viewing distance. A text line is ~30 px tall. That single number decides the whole table:

| Feature (Tobii pipeline) | Webcam today | Webcam after §5 tasks | Notes |
|---|---|---|---|
| Raw gaze stream (`gaze.csv`) | ⚠️ produced but head-driven, not logged | ✅ coarse (~150 px error), logged | task W1 + W2 |
| Fixation: duration, dispersion | ✅ computed (better algorithm than the Tobii scripts) | ✅ | not persisted yet — W1 |
| Regression flag | ✅ computed (and more correctly than the Tobii scripts) | ✅ | direction survives coarse accuracy |
| Saccade amplitude / direction | ❌ not computed | 🟡 coarse (between-fixation vectors) | fine for large jumps only |
| Saccade velocity / duration | ❌ | ❌ | needs 60+ Hz and precision; webcam is ~30 fps |
| **AOI at text-line level** | ❌ no AOI concept | ❌ **not achievable** — error ≫ line height | this is the hard limit |
| **AOI at paragraph/block level** | ❌ | ✅ and *easier* than the Tobii way | task W3 — DOM rects, no OCR needed |
| `fixation_count_in_AOI` | ❌ | ✅ at paragraph level | follows from W3 |
| Confusion click labels | ❌ no button | ✅ trivial to add | task W1 |
| Pupil diameter | ❌ | ❌ not reliably from RGB webcam | Tobii Pro SDK remains the only route (main README §11, Exp. 4) |
| Sampling rate | ~30 fps (camera-bound) | same | comparable to the Ghost-bubble hack's ~10–20 Hz, ironically |
| — Blink rate | not enabled | ✅ **webcam-only bonus** | task W6 — MediaPipe blendshapes |
| — Brow furrow (facial confusion cue) | not enabled | ✅ **webcam-only bonus** | task W6 |

**Bottom line for experiment design:** the webcam can support *paragraph-level* confusion detection with the same protocol and the same downstream pipeline as the Tobii method, plus facial features the Tobii can't see. It cannot support *line- or word-level* analysis, and it cannot give pupil data. Design webcam experiments at block granularity, and keep the Tobii (or a research-grade tracker) for anything finer.

Known bugs to be aware of when reading the current code:
- **Regression double-counting:** each frame re-runs `detectRegressions` over the last 5 fixations, so the same regression pair is found and scored repeatedly — the score inflates. Fix in W4.
- **Frame-rate-dependent decay:** the score decays per animation frame, so a 120 Hz monitor decays 2× faster than a 60 Hz one. Make it time-based (W4).
- The mirrored x (`1 - x`) plus raw scaling means the gaze dot's motion is dominated by head translation; treat every current number as qualitative only until W2 lands.

---

## 5. Next set of tasks (webcam track) — in this order

**W1 — Make it a research instrument: logging + ground truth.** Add to the app: (a) an in-app **"I'm confused" button** (same role as the Tobii popup's "Yes (Confused)"); (b) session logging of gaze points, fixations, regressions, and clicks; (c) an **Export CSV** button producing `gaze.csv` / `fixation.csv` / `clicks.csv` with the **same column schemas as the Tobii pipeline** (main README §6) so `label.py` and the training code work on both datasets unchanged. Everything stays client-side (Blob download) — keep the privacy property. *This task needs no computer-vision work and unblocks everything else; do it first.*

**W2 — Real gaze estimation with calibration.** Replace the raw iris-position scaling:
1. Enable `outputFacialTransformationMatrixes: true` in the FaceLandmarker options to get head pose, and build a feature vector per frame: iris centers *relative to the eye corners/eyelids* + head pose.
2. Add a 9-point calibration screen (dots at a 3×3 grid; user looks at each and clicks/holds); fit a per-session ridge or polynomial regression from feature vector → screen x,y.
3. Show live validation after calibration (look at 4 fresh points, display mean error in px) and log that error with every session — it is the quality metric for the whole dataset.
   *Shortcut option:* [WebGazer.js](https://webgazer.cs.brown.edu/) does interaction-based calibration out of the box; evaluate it side-by-side before writing your own — whichever gives lower validation error wins.

**W3 — Paragraph-level AOIs from the DOM.** The reading text lives inside the app, so AOIs are free: give each paragraph an id and read `element.getBoundingClientRect()` — no screenshots, no Tesseract, no resolution fragility (this is genuinely cleaner than the Tobii pipeline's OCR route). Log per-fixation AOI membership and `fixation_count_in_AOI` exactly as the Tobii `fixation.csv` does.

**W4 — Bug fixes.** Deduplicate regressions (track the last scored fixation pair, or only test the newest fixation against its predecessor); make score decay time-based; make the gaze buffer robust to dropped frames (timestamps, not counts).

**W5 — The validation experiment: webcam vs. Tobii, simultaneously.** This is the experiment that decides whether webcam data is usable, and the two systems don't conflict — the webcam never reads the screen, so Tobii Ghost's bubble can stay on:
1. One participant, one machine: open the webcam app (after W1–W3) on the reading text, run `CONFUSION/collect.py` recording the Ghost bubble at the same time. Calibrate both first.
2. Both log wall-clock timestamps; align the two streams offline.
3. Report: mean gaze error webcam-vs-Tobii (px and degrees), fixation match rate (webcam fixation within X px and ±100 ms of a Tobii fixation), regression precision/recall with Tobii as ground truth, and AOI-assignment agreement at paragraph level.
4. Repeat for ≥ 5 participants. Publish the numbers in this README. If paragraph-level AOI agreement is above ~80%, the webcam track is validated for block-granularity experiments.

**W6 — Webcam-unique features.** Set `outputFaceBlendshapes: true` and log per-window **blink rate** (eyeBlinkLeft/Right) and **brow furrow** (browDownLeft/Right) — established cognitive-load and confusion cues that the Tobii setup cannot capture. Add them as extra columns; they may compensate for the missing pupil signal.

**W7 — Rerun the confusion-modeling experiments on webcam data.** With W1–W5 done, collect a webcam confusion dataset using the same protocol as the Tobii track (read → click when confused), then apply main README §11 Experiments 1–2 (time-window labels, behavioral features only, leave-one-text/participant-out). The comparison — Tobii features vs. webcam features vs. webcam+facial features, same labels, same evaluation — is the core result of this project phase, and a strong publication story: *how much confusion-detection accuracy do you lose when the eye tracker is replaced by a webcam?*

---

## 6. Quick reference

| Key | Value |
|---|---|
| Start the app | `cd WEBCAM/app && npm install && npm run dev` → localhost:3000 |
| Gaze source | MediaPipe FaceLandmarker iris landmarks (no calibration yet — §4) |
| Fixation (I-DT) | dispersion ≤ 50 px, duration ≥ 150 ms |
| Regression | ≥ 80 px leftward, ≤ 50 px vertical |
| Confusion score | regression +60, long fixation (>400 ms) +5, eye–mouse gap (>300 px) +2, decay 0.5/frame, threshold 100 (adaptive) |
| All parameters | `app/constants.ts` (session overrides in browser `localStorage`) |
| Effective rate | ~30 fps (camera-bound) |
| Hard limits | no line-level AOIs, no pupil diameter (§4 table) |
