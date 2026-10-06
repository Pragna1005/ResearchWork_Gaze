"""Charts for the progress presentation. Numbers come from the repo's processed/
outputs (or are quoted from README 10.9 where they were measured once).

    python presentation/make_charts.py
"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, "..", "IITJ_Project", "IITJ_Project", "CONFUSION")
OUT = os.path.join(HERE, "charts")

NEW, OLD, BASE = "#2a78d6", "#eb6834", "#a3a29d"     # palette slots 1, 2 + neutral
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e0"

plt.rcParams.update({
    "font.family": "Calibri", "font.size": 15, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "figure.dpi": 200, "savefig.bbox": "tight", "savefig.facecolor": "white",
})


def hbars(ax, labels, values, colors, fmt, xmax):
    y = range(len(labels))[::-1]
    ax.barh(list(y), values, color=colors, height=0.6, edgecolor="white", linewidth=2)
    for yi, v in zip(y, values):
        ax.text(v + xmax * 0.015, yi, fmt(v), va="center", color=INK, fontsize=15)
    ax.set_yticks(list(y), labels)
    ax.tick_params(axis="y", length=0, labelsize=15, labelcolor=INK)
    ax.set_xlim(0, xmax)
    ax.xaxis.set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["left"].set_color(GRID)


# 1. what the old model's decisions rely on (XGBoost gain, measured in this repo)
fig, ax = plt.subplots(figsize=(7.2, 2.6))
hbars(ax, ["Which text line\n(AOI columns)", "Screen position\n(x, y, distance)", "Eye behaviour\n(duration, regressions…)"],
      [72, 9, 18], [OLD, OLD, BASE], lambda v: f"{v}%", 85)
ax.set_title("Share of the old model's decision (XGBoost gain)", loc="left", fontsize=15, color=INK2)
fig.savefig(os.path.join(OUT, "old_model_reliance.png")); plt.close(fig)

# 2. regression flag: old vs new
fx = pd.concat([pd.read_csv(p) for p in sorted(glob.glob(os.path.join(CONF, "processed", "s*", "fixations.csv")))],
               ignore_index=True)
old_rate = fx.regression_flag_legacy.mean() * 100
jitter = ((fx.regression_flag_legacy == 1) & (fx.saccade_dy >= -25)).sum()
real_old = fx.regression_flag_legacy.sum() - jitter
fig, ax = plt.subplots(figsize=(7.2, 2.4))
y = [1, 0]
ax.barh(1, jitter / len(fx) * 100, color=OLD, height=0.55, edgecolor="white", linewidth=2)
ax.barh(1, real_old / len(fx) * 100, left=jitter / len(fx) * 100, color="#f4b49a", height=0.55, edgecolor="white", linewidth=2)
ax.barh(0, fx.regression_flag.mean() * 100, color=NEW, height=0.55, edgecolor="white", linewidth=2)
ax.text(old_rate + 1, 1, f"{old_rate:.0f}% of fixations", va="center", fontsize=15)
ax.text(fx.regression_flag.mean() * 100 + 1, 0, f"{fx.regression_flag.mean() * 100:.0f}%", va="center", fontsize=15)
ax.text(jitter / len(fx) * 100 / 2, 1, "jitter ≤ 25 px", va="center", ha="center", color="white", fontsize=14)
ax.set_yticks(y, ["Old flag\n(any upward move)", "New flag\n(left on line, or up a line)"])
ax.tick_params(axis="y", length=0, labelsize=15, labelcolor=INK)
ax.set_xlim(0, 52); ax.xaxis.set_visible(False); ax.spines["bottom"].set_visible(False); ax.spines["left"].set_color(GRID)
ax.set_title("Fixations flagged as a regression", loc="left", fontsize=15, color=INK2)
fig.savefig(os.path.join(OUT, "regression_flag.png")); plt.close(fig)

# 3. per-session regression rate: normal reading vs the 5 s before a click
lab = pd.concat([pd.read_csv(p) for p in sorted(glob.glob(os.path.join(CONF, "processed", "s*", "fixations_labeled.csv")))],
                ignore_index=True)
lab = lab[lab.session != "s21"]
p = lab.groupby(["session", "label_t5"]).regression_flag.mean().unstack().dropna() * 100
fig, ax = plt.subplots(figsize=(5.6, 4.4))
for _, r in p.iterrows():
    ax.plot([0, 1], [r[0], r[1]], color=NEW, linewidth=2, alpha=0.55, marker="o", markersize=7,
            markeredgecolor="white", markeredgewidth=1.5)
ax.plot([0, 1], [p[0].median(), p[1].median()], color=INK, linewidth=3, marker="o", markersize=9,
        markeredgecolor="white", markeredgewidth=2, zorder=5)
ax.text(1.06, p[1].median(), f"median\n{p[1].median():.0f}%", va="center", fontsize=14)
ax.text(-0.06, p[0].median(), f"median\n{p[0].median():.0f}%", va="center", ha="right", fontsize=14)
ax.set_xticks([0, 1], ["Normal reading", "5 s before a\nconfusion click"])
ax.tick_params(axis="x", length=0, labelsize=15, labelcolor=INK)
ax.set_xlim(-0.45, 1.45)
ax.set_ylabel("Regression rate (% of fixations)")
ax.yaxis.grid(True, color=GRID, linewidth=1); ax.set_axisbelow(True)
ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
ax.set_title(f"Each line = one session ({len(p)} sessions with clicks)", loc="left", fontsize=14, color=INK2)
fig.savefig(os.path.join(OUT, "before_click.png")); plt.close(fig)

# 4. Experiment 2 results (ROC-AUC), read from exp2_results.json
import json
r = json.load(open(os.path.join(CONF, "processed", "exp2_results.json")))
rows = [
    ("Old setup, random split", r["old_setup"]["XGBoost random 80/20 split"]["roc_auc"], OLD),
    ("Old setup, unseen sessions", r["old_setup"]["XGBoost leave-one-session-out"]["roc_auc"], OLD),
    ("New: behaviour only, unseen sessions", r["behavioural_LOSO"]["XGBoost"]["roc_auc"], NEW),
    ("Regression rate alone (no ML)", r["baseline_regr_rate_only"]["roc_auc"], BASE),
]
fig, ax = plt.subplots(figsize=(8.2, 3.2))
y = list(range(len(rows)))[::-1]
ax.barh(y, [v - 0.5 for _, v, _ in rows], left=0.5, color=[c for *_, c in rows], height=0.6, edgecolor="white", linewidth=2)
for yi, (_, v, _) in zip(y, rows):
    ax.text(v + 0.006, yi, f"{v:.2f}", va="center", fontsize=15)
ax.set_yticks(y, [n for n, *_ in rows]); ax.tick_params(axis="y", length=0, labelsize=15, labelcolor=INK)
ax.set_xlim(0.5, 0.95); ax.set_xticks([0.5, 0.6, 0.7, 0.8, 0.9]); ax.set_xticklabels(["0.5\n(guessing)", "0.6", "0.7", "0.8", "0.9"])
ax.xaxis.grid(True, color=GRID, linewidth=1); ax.set_axisbelow(True)
ax.spines["left"].set_color(GRID); ax.spines["bottom"].set_visible(False); ax.tick_params(axis="x", length=0)
ax.set_title("ROC-AUC (1.0 = perfect, 0.5 = guessing)", loc="left", fontsize=15, color=INK2)
fig.savefig(os.path.join(OUT, "exp2_auc.png")); plt.close(fig)

# 5. sampling rate (measured: README 10.9, rebuild_summary.csv, TEST session meta.json)
fig, ax = plt.subplots(figsize=(6.4, 2.4))
hbars(ax, ["Old data (2025)", "cnn.py on lab PC", "collect.py on lab PC"], [6.9, 17.8, 29.1],
      [OLD, OLD, NEW], lambda v: f"{v:.0f} Hz" if v > 10 else "5–8 Hz", 34)
ax.set_title("Gaze samples per second", loc="left", fontsize=15, color=INK2)
fig.savefig(os.path.join(OUT, "sampling_rate.png")); plt.close(fig)
print("charts written to", OUT)
