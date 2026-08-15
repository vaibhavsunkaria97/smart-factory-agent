"""
evaluate.py
===========
Compares detector configurations against the ground-truth labels.

Why these metrics
-----------------
Accuracy is deliberately NOT reported. With ~11% positives, a model that
predicts "normal" for every row already scores ~89% - a number that looks
good and means nothing. Under class imbalance, accuracy is misleading.

F2 is reported alongside F1 because beta=2 weights recall four times more
than precision. On a production line a missed fault costs more than a false
alarm, so recall is the metric that matters.

A precision-recall curve is used instead of ROC. ROC's false-positive rate
has a large true-negative denominator when positives are rare, which makes
curves look flatteringly good. PR focuses on the rare positive class.
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.mixture import GaussianMixture
from sklearn.metrics import (precision_score, recall_score, f1_score,
                             fbeta_score, confusion_matrix,
                             precision_recall_curve, average_precision_score)

from preprocessing import preprocess
from detectors import AnomalyEnsemble, RuleDetector


def metrics(y_true, y_pred):
    return {
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "f2": float(fbeta_score(y_true, y_pred, beta=2, zero_division=0)),
        "flagged": int(np.sum(y_pred)),
    }


def main():
    df = pd.read_csv("data/sensor_data.csv")

    # Match ground truth BY TIMESTAMP, not by index: preprocessing drops
    # duplicate rows, so positional alignment would silently misalign labels.
    truth = dict(zip(pd.to_datetime(df["timestamp"]).astype(str), df["label"]))

    clean = preprocess(df)
    raw, std = clean.raw, clean.standardized
    y_true = np.array([
        1 if truth.get(str(pd.to_datetime(t))) == "abnormal" else 0
        for t in raw["timestamp"]
    ])

    results = {}

    # --- 1. rules only ---------------------------------------------------
    rd = RuleDetector()
    y_rule = np.array([1 if rd.check(raw.iloc[i]) else 0 for i in range(len(raw))])
    results["Rule-based only"] = metrics(y_true, y_rule)

    # --- 2. IsolationForest only -----------------------------------------
    iso = IsolationForest(n_estimators=200, contamination=0.12, random_state=42)
    y_if = (iso.fit_predict(std.values) == -1).astype(int)
    # Negate: sklearn returns LOWER values for MORE anomalous points.
    if_scores = -iso.score_samples(std.values)
    results["IsolationForest only"] = metrics(y_true, y_if)

    # --- 3. Gaussian Mixture ---------------------------------------------
    # BIC picks the component count instead of guessing. Each component can be
    # read as an operating mode (idle / normal run / high load).
    bics = {}
    for k in range(1, 6):
        g = GaussianMixture(k, covariance_type="full", random_state=42,
                            n_init=3).fit(std.values)
        bics[k] = g.bic(std.values)
    best_k = min(bics, key=bics.get)
    gmm = GaussianMixture(best_k, covariance_type="full", random_state=42,
                          n_init=3).fit(std.values)
    gmm_scores = -gmm.score_samples(std.values)      # negative log-likelihood
    y_gmm = (gmm_scores > np.percentile(gmm_scores, 88)).astype(int)
    results[f"Gaussian Mixture (K={best_k})"] = metrics(y_true, y_gmm)

    # --- 4. shipped ensemble ---------------------------------------------
    dets = AnomalyEnsemble().detect(raw, std)
    idx = {d.index for d in dets}
    y_ens = np.array([1 if i in idx else 0 for i in range(len(raw))])
    results["Rule + IF ensemble (shipped)"] = metrics(y_true, y_ens)

    # --- figure -----------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8))

    cm = confusion_matrix(y_true, y_ens)
    ax1.imshow(cm, cmap="Blues")
    for (i, j), v in np.ndenumerate(cm):
        ax1.text(j, i, str(v), ha="center", va="center", fontsize=15,
                 fontweight="bold",
                 color="white" if v > cm.max() / 2 else "#0f172a")
    ax1.set_xticks([0, 1]); ax1.set_yticks([0, 1])
    ax1.set_xticklabels(["pred normal", "pred anomaly"])
    ax1.set_yticklabels(["true normal", "true anomaly"])
    ax1.set_title("Confusion matrix - shipped ensemble", fontsize=10,
                  fontweight="bold")

    prec, rec, _ = precision_recall_curve(y_true, if_scores)
    ap = average_precision_score(y_true, if_scores)
    ax2.plot(rec, prec, color="#1d4ed8", lw=1.8,
             label=f"IsolationForest (AP={ap:.3f})")
    ax2.axhline(y_true.mean(), ls="--", lw=1, color="#94a3b8",
                label=f"random baseline ({y_true.mean():.2f})")
    e = results["Rule + IF ensemble (shipped)"]
    ax2.scatter([e["recall"]], [e["precision"]], s=90, marker="*",
                color="#dc2626", zorder=5, label="shipped operating point")
    ax2.set_xlabel("Recall"); ax2.set_ylabel("Precision")
    ax2.set_xlim(0, 1.02); ax2.set_ylim(0, 1.05)
    ax2.set_title("Precision-Recall (ML score)", fontsize=10, fontweight="bold")
    ax2.legend(fontsize=7, loc="lower left"); ax2.grid(alpha=0.25)

    plt.tight_layout()
    plt.savefig("assets/evaluation.png", dpi=160, bbox_inches="tight")

    # --- outputs ----------------------------------------------------------
    summary = {
        "n_rows": int(len(raw)),
        "n_true_anomalies": int(y_true.sum()),
        "average_precision_if": float(ap),
        "gmm_best_k": int(best_k),
        "results": results,
    }
    with open("evaluation_results.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'Detector':<32}{'P':>8}{'R':>8}{'F1':>8}{'F2':>8}{'Flagged':>9}")
    print("-" * 73)
    for name, m in results.items():
        print(f"{name:<32}{m['precision']:>8.3f}{m['recall']:>8.3f}"
              f"{m['f1']:>8.3f}{m['f2']:>8.3f}{m['flagged']:>9d}")
    print(f"\nground truth: {int(y_true.sum())} anomalies / {len(y_true)} readings")
    print("wrote assets/evaluation.png, evaluation_results.json")


if __name__ == "__main__":
    main()