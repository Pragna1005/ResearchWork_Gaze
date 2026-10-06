"""Experiment 2 (README §11): behavioural features only, honest evaluation.

Unit of prediction: a WINDOW_S-second window of reading (README §10.6), slid
in STEP_S steps over each session.
  label 1  : the window ends 0..LEAD_S s before a confusion click
             (it holds only the reading that led up to the click)
  dropped  : a click falls inside the window (the click itself - looking at the
             button and back - would contaminate the gaze features)
  label 0  : everything else
Features describe HOW the eyes move, never WHERE: no fix_x/fix_y/distance, no
AOI identity (README §10.1). Line ids are used only to count re-reads.

Evaluation: leave-one-session-out over the 20 old sessions (each session is a
different page, so this is also leave-one-text-out), then train on all 20 and
test on s21 (new PC, ~18 Hz instead of 5-8 Hz).
For contrast, the OLD setup (fixation-level, position + AOI one-hot features,
place-based labels, fixation_label_final.csv) is scored with a random split
and with leave-one-session-out - the gap between the two is the leakage.

    python rebuild_fixations.py && python label.py && python train.py
"""
import json
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from sessions import D, HERE, SESSIONS, to_seconds

WINDOW_S = 10.0
STEP_S = 1.0
LEAD_S = 3.0
MIN_FIXATIONS = 2      # fewer fixations than this = bubble mostly lost, skip window
SEED = 42
OUT = os.path.join(HERE, "processed")

FEATURES = [
    "n_fix", "fix_dur_mean", "fix_dur_median", "fix_dur_max", "fix_time_frac", "dispersion_mean",
    "regr_rate", "regr_left_rate", "regr_up_rate", "sacc_amp_mean", "sacc_amp_median",
    "gap_mean", "reread_rate",
]


def window_features(f, start):
    """Behavioural summary of the fixations f inside [start, start + WINDOW_S]."""
    sacc = f.iloc[1:]  # the first fixation's jump comes from outside the window
    return {
        "n_fix": len(f),
        "fix_dur_mean": f.duration.mean(),
        "fix_dur_median": f.duration.median(),
        "fix_dur_max": f.duration.max(),
        "fix_time_frac": f.duration.sum() / WINDOW_S,
        "dispersion_mean": f.dispersion.mean(),
        "regr_rate": sacc.regression_flag.mean() if len(sacc) else 0.0,
        "regr_left_rate": (sacc.regression_type == "leftward").mean() if len(sacc) else 0.0,
        "regr_up_rate": (sacc.regression_type == "upward").mean() if len(sacc) else 0.0,
        "sacc_amp_mean": sacc.saccade_amplitude.mean() if len(sacc) else 0.0,
        "sacc_amp_median": sacc.saccade_amplitude.median() if len(sacc) else 0.0,
        "gap_mean": sacc.saccade_before_duration.mean() if len(sacc) else 0.0,
        # fixations on a line already visited earlier in this window (count only, not which line)
        "reread_rate": (f.aoi[f.aoi != "None"].duplicated().sum() / len(f)),
    }


def build_windows(session):
    fx = pd.read_csv(os.path.join(OUT, session["session"], "fixations.csv"))
    fx["regression_type"] = fx.regression_type.fillna("")
    clicks = to_seconds(pd.read_csv(session["clicks"]).timestamp)
    rows = []
    for start in np.arange(fx.start_ts.min(), fx.end_ts.max() - WINDOW_S, STEP_S):
        end = start + WINDOW_S
        if any(start < c < end for c in clicks):
            continue
        f = fx[(fx.start_ts >= start) & (fx.end_ts <= end)]
        if len(f) < MIN_FIXATIONS:
            continue
        label = int(any(end <= c <= end + LEAD_S for c in clicks))
        rows.append({"session": session["session"], "start": start, "label": label,
                     **window_features(f, start)})
    return rows


def models(y):
    pos_weight = (len(y) - y.sum()) / max(y.sum(), 1)
    return {
        "RandomForest": RandomForestClassifier(n_estimators=300, min_samples_leaf=5,
                                               class_weight="balanced", random_state=SEED, n_jobs=-1),
        "XGBoost": XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.05,
                                 subsample=0.8, colsample_bytree=0.8, scale_pos_weight=pos_weight,
                                 random_state=SEED, eval_metric="logloss"),
    }


def scores(y, p):
    return {"roc_auc": round(roc_auc_score(y, p), 3),
            "pr_auc": round(average_precision_score(y, p), 3),
            "pr_auc_chance": round(float(np.mean(y)), 3),
            "balanced_acc@0.5": round(balanced_accuracy_score(y, p >= 0.5), 3),
            "n": int(len(y)), "positives": int(np.sum(y))}


def leave_one_session_out(data, feats, make_models):
    """Returns {model: (pooled scores, per-session ROC-AUC)} and pooled predictions."""
    results = {}
    for name in make_models(data.label).keys():
        pred = pd.Series(np.nan, index=data.index)
        for s in data.session.unique():
            tr, te = data.session != s, data.session == s
            if data.label[tr].nunique() < 2:
                continue
            m = make_models(data.label[tr])[name].fit(data.loc[tr, feats], data.label[tr])
            pred[te] = m.predict_proba(data.loc[te, feats])[:, 1]
        per_session = {s: round(roc_auc_score(g.label, pred[g.index]), 3)
                       for s, g in data.groupby("session") if g.label.nunique() == 2}
        results[name] = {**scores(data.label, pred.to_numpy()),
                         "per_session_roc_auc_median": round(float(np.median(list(per_session.values()))), 3),
                         "sessions_auc_above_0.5": f"{sum(v > 0.5 for v in per_session.values())}/{len(per_session)}",
                         "per_session_roc_auc": per_session}
    return results


def old_setup():
    """The previous intern's setup, scored two ways, on their own labelled file."""
    old = pd.read_csv("fixation_label_final.csv")
    start = to_seconds(old.start_time)
    old["session"] = "?"
    for s in SESSIONS[:20]:
        t = to_seconds(pd.read_csv(s["gaze"]).timestamp)
        old.loc[(start >= t.min()) & (start <= t.max()), "session"] = s["session"]
    feats = [c for c in old.columns if c not in ("start_time", "end_time", "fix_start_ts", "label", "session")]
    X = old[feats].replace({"True": 1, "False": 0, True: 1, False: 0}).astype(float)
    old[feats] = X
    y = old.label.astype(int)
    out = {}
    tr, te = train_test_split(old.index, test_size=0.2, random_state=SEED, stratify=y)
    for name, m in models(y[tr]).items():
        m.fit(X.loc[tr], y[tr])
        out[f"{name} random 80/20 split"] = scores(y[te], m.predict_proba(X.loc[te])[:, 1])
    for name, r in leave_one_session_out(old, feats, models).items():
        out[f"{name} leave-one-session-out"] = {k: v for k, v in r.items() if k != "per_session_roc_auc"}
    return out


if __name__ == "__main__":
    data = pd.DataFrame([r for s in SESSIONS for r in build_windows(s)])
    train_data = data[data.session != "s21"].reset_index(drop=True)
    s21 = data[data.session == "s21"].reset_index(drop=True)
    print(f"windows: {len(train_data)} from 20 old sessions ({train_data.label.sum()} positive), "
          f"{len(s21)} from s21 ({s21.label.sum()} positive)")

    results = {"config": {"window_s": WINDOW_S, "step_s": STEP_S, "lead_s": LEAD_S,
                          "min_fixations": MIN_FIXATIONS, "seed": SEED, "features": FEATURES}}

    results["behavioural_LOSO"] = leave_one_session_out(train_data, FEATURES, models)

    # single-feature baseline: does ML add anything over "how much re-reading"?
    results["baseline_regr_rate_only"] = scores(train_data.label, train_data.regr_rate.to_numpy())

    results["s21_external"] = {}
    for name, m in models(train_data.label).items():
        m.fit(train_data[FEATURES], train_data.label)
        results["s21_external"][name] = scores(s21.label, m.predict_proba(s21[FEATURES])[:, 1])
        if name == "RandomForest":
            imp = pd.Series(m.feature_importances_, index=FEATURES).sort_values(ascending=False)
            results["rf_feature_importance"] = imp.round(3).to_dict()

    results["old_setup"] = old_setup()

    with open(os.path.join(OUT, "exp2_results.json"), "w") as fh:
        json.dump(results, fh, indent=2)
    data.to_csv(os.path.join(OUT, "exp2_windows.csv"), index=False)

    def show(title, d):
        print(f"\n== {title}")
        for k, v in d.items():
            print(f"  {k:<38} " + ", ".join(f"{a}={b}" for a, b in v.items() if a != "per_session_roc_auc"))

    show("behavioural features, leave-one-session-out (20 old sessions)", results["behavioural_LOSO"])
    show("baseline", {"regression rate alone": results["baseline_regr_rate_only"]})
    show("train on 20 old sessions, test on s21 (new PC)", results["s21_external"])
    show("OLD setup (position + AOI one-hot, place labels, per fixation)", results["old_setup"])
    print("\nRF feature importance:", results["rf_feature_importance"])
