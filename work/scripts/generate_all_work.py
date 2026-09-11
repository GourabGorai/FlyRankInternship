"""
generate_all_work.py
Complete data processing, modeling, visualization, and notebook population for FlyRank ML Internship.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import GroupShuffleSplit
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
import nbformat as nbf

# Ensure working directory is repo root
if os.path.basename(os.getcwd()) == "scripts" or os.path.basename(os.getcwd()) == "work":
    os.chdir("../..")

RAW_CSV = "data/raw/content_refresh_anonymized.csv"
WORK_OUTPUTS = "work/outputs"
WORK_FIGURES = "work/figures"
os.makedirs(WORK_OUTPUTS, exist_ok=True)
os.makedirs(WORK_FIGURES, exist_ok=True)

print(f"Loading data from {RAW_CSV}...")
df = pd.read_csv(RAW_CSV)

# Define label
df["is_declining_label"] = (df["trend_direction"].str.lower() == "down").astype(int)

# Precision@K helper
def precision_at_k(scores, labels, k):
    order = np.argsort(-np.asarray(scores))
    topk = np.asarray(labels)[order[:k]]
    return float(topk.mean())

# Feature engineering
print("Engineering features...")
features_numeric = [
    "impressions_90d", "clicks_90d", "ctr", "avg_position",
    "content_age_days", "days_since_last_update", "word_count",
    "engagement_rate", "scroll_rate", "sessions_90d", "ai_traffic_pct"
]

X_raw = df[features_numeric].copy()
X_raw["log_impressions"] = np.log1p(np.maximum(0, X_raw["impressions_90d"]))
X_raw["log_clicks"] = np.log1p(np.maximum(0, X_raw["clicks_90d"]))
X_raw["update_ratio"] = X_raw["days_since_last_update"] / (X_raw["content_age_days"] + 1.0)
X_raw["has_missing_wc"] = X_raw["word_count"].isna().astype(int)
X_raw["is_unranked"] = (X_raw["avg_position"] == 0).astype(int)

# Fill missing values
X_clean = X_raw.replace([np.inf, -np.inf], np.nan).fillna(0)

# One-hot encode content_type
type_dummies = pd.get_dummies(df["content_type"], prefix="type", drop_first=True, dtype=int)
X_all = pd.concat([X_clean, type_dummies], axis=1)

FEATURE_COLS = list(X_all.columns)
y_all = df["is_declining_label"].values
groups = df["client_id"].values

print(f"Total features: {len(FEATURE_COLS)}")

# Baseline score calculation
stale = (df["days_since_last_update"] >= 180).astype(int)
visible = (df["impressions_90d"] >= 500).astype(int)
position_factor = np.clip(df["avg_position"] / 10.0, 0.5, 3.0)
baseline_score = stale * visible * np.log1p(df["impressions_90d"]) * position_factor
df["baseline_score"] = baseline_score

# Assign baseline reason codes
def get_reason_code(row):
    if row["baseline_score"] == 0:
        return "LOW_SIGNAL_OR_FRESH"
    if row["days_since_last_update"] >= 365 and row["impressions_90d"] >= 1000:
        return "STALE_HIGH_EXPOSURE"
    if row["avg_position"] > 15:
        return "SLIPPING_RANK_STALE"
    return "MODERATE_EXPOSURE_STALE"

df["reason_code"] = df.apply(get_reason_code, axis=1)

# Client holdout split
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(gss.split(df, groups=groups))

X_train, X_test = X_all.iloc[train_idx], X_all.iloc[test_idx]
y_train, y_test = y_all[train_idx], y_all[test_idx]
df_test = df.iloc[test_idx].copy()

base_rate = float(y_test.mean())
print(f"Client-holdout test set: {len(X_test)} rows | Base rate: {base_rate:.3f}")

# Train baseline evaluation
hr_test = df_test["baseline_score"].values
p20_base = precision_at_k(hr_test, y_test, 20)
p50_base = precision_at_k(hr_test, y_test, 50)
p100_base = precision_at_k(hr_test, y_test, 100)

print(f"Baseline Precision@20: {p20_base:.3f} | Precision@50: {p50_base:.3f}")

# Export baseline outputs
df_baseline_export = df[["content_id", "client_id", "baseline_score", "reason_code", "is_declining_label", "impressions_90d", "days_since_last_update", "avg_position"]].sort_values("baseline_score", ascending=False)
df_baseline_export.to_csv(os.path.join(WORK_OUTPUTS, "baseline_action_score.csv"), index=False)

baseline_metrics = {
    "task": "Refresh Opportunity Scoring",
    "base_rate": base_rate,
    "split": "client_holdout",
    "test_rows": len(X_test),
    "precision_at_20": p20_base,
    "precision_at_50": p50_base,
    "precision_at_100": p100_base
}
with open(os.path.join(WORK_OUTPUTS, "baseline_metrics.json"), "w") as f:
    json.dump(baseline_metrics, f, indent=2)

# Train ML Models
print("Training models...")
# 1. Logistic Regression
lr = LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced")
lr.fit(X_train, y_train)
p_test_lr = lr.predict_proba(X_test)[:, 1]

# 2. Decision Tree
dt = DecisionTreeClassifier(max_depth=3, class_weight="balanced", random_state=42)
dt.fit(X_train, y_train)
p_test_dt = dt.predict_proba(X_test)[:, 1]

# 3. Random Forest
rf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42, class_weight="balanced", n_jobs=-1)
rf.fit(X_train, y_train)
p_test_rf = rf.predict_proba(X_test)[:, 1]

results = {
    "split_strategy": "client_holdout",
    "test_size": len(X_test),
    "base_rate": base_rate,
    "baseline": {
        "precision_at_20": p20_base,
        "precision_at_50": p50_base,
        "precision_at_100": p100_base
    },
    "logistic_regression": {
        "precision_at_20": precision_at_k(p_test_lr, y_test, 20),
        "precision_at_50": precision_at_k(p_test_lr, y_test, 50),
        "precision_at_100": precision_at_k(p_test_lr, y_test, 100),
        "roc_auc": float(roc_auc_score(y_test, p_test_lr))
    },
    "decision_tree": {
        "precision_at_20": precision_at_k(p_test_dt, y_test, 20),
        "precision_at_50": precision_at_k(p_test_dt, y_test, 50),
        "precision_at_100": precision_at_k(p_test_dt, y_test, 100),
        "roc_auc": float(roc_auc_score(y_test, p_test_dt))
    },
    "random_forest": {
        "precision_at_20": precision_at_k(p_test_rf, y_test, 20),
        "precision_at_50": precision_at_k(p_test_rf, y_test, 50),
        "precision_at_100": precision_at_k(p_test_rf, y_test, 100),
        "roc_auc": float(roc_auc_score(y_test, p_test_rf))
    }
}
results["lift_at_50"] = results["random_forest"]["precision_at_50"] / p50_base

with open(os.path.join(WORK_OUTPUTS, "model_results.json"), "w") as f:
    json.dump(results, f, indent=2)

print(f"Random Forest Precision@50: {results['random_forest']['precision_at_50']:.3f} | Lift: {results['lift_at_50']:.2f}x")

# Final Action Queue creation
df["model_score"] = rf.predict_proba(X_all)[:, 1]
# Blended priority score: weighted model score + volume log boost
df["priority_score"] = (0.7 * df["model_score"] + 0.3 * (np.log1p(df["impressions_90d"]) / np.log1p(df["impressions_90d"].max()))).round(4)

def assign_recommended_action(row):
    if row["priority_score"] >= 0.70:
        if row["days_since_last_update"] >= 365:
            return "COMPREHENSIVE_REWRITE"
        else:
            return "UPDATE_FACTS_AND_TITLE"
    elif row["priority_score"] >= 0.50:
        if row["impressions_90d"] < 200:
            return "CONSOLIDATE_OR_PRUNE"
        else:
            return "UPDATE_METADATA_AND_LINKS"
    elif row["priority_score"] >= 0.35:
        return "MONITOR_ONLY"
    else:
        return "NO_ACTION"

df["recommended_action"] = df.apply(assign_recommended_action, axis=1)

df_action_queue = df[[
    "content_id", "client_id", "priority_score", "model_score", "recommended_action",
    "reason_code", "impressions_90d", "days_since_last_update", "avg_position",
    "ctr", "is_declining_label"
]].sort_values("priority_score", ascending=False)

df_action_queue.to_csv(os.path.join(WORK_OUTPUTS, "final_action_queue.csv"), index=False)
print("Saved final_action_queue.csv")

# Generate Figures
print("Generating publication figures...")
plt.style.use("default")
plt.rcParams.update({"font.family": "sans-serif", "figure.autolayout": True})

# Figure 1: Precision@K comparison
fig, ax = plt.subplots(figsize=(8, 5))
ks = [20, 50, 100]
p_base = [results["baseline"]["precision_at_20"], results["baseline"]["precision_at_50"], results["baseline"]["precision_at_100"]]
p_lr = [results["logistic_regression"]["precision_at_20"], results["logistic_regression"]["precision_at_50"], results["logistic_regression"]["precision_at_100"]]
p_dt = [results["decision_tree"]["precision_at_20"], results["decision_tree"]["precision_at_50"], results["decision_tree"]["precision_at_100"]]
p_rf = [results["random_forest"]["precision_at_20"], results["random_forest"]["precision_at_50"], results["random_forest"]["precision_at_100"]]

x = np.arange(len(ks))
width = 0.18

ax.bar(x - 1.5*width, p_base, width, label="Heuristic Baseline", color="#94a3b8")
ax.bar(x - 0.5*width, p_lr, width, label="Logistic Regression", color="#60a5fa")
ax.bar(x + 0.5*width, p_dt, width, label="Decision Tree (d=3)", color="#34d399")
ax.bar(x + 1.5*width, p_rf, width, label="Random Forest (Ensemble)", color="#3b82f6")

ax.axhline(base_rate, color="#ef4444", linestyle="--", linewidth=1.5, label=f"Base Rate ({base_rate:.3f})")
ax.set_ylabel("Precision@K (Holdout Clients)")
ax.set_title("Precision@K: Learned Models vs Heuristic Baseline (Client-Holdout Split)")
ax.set_xticks(x)
ax.set_xticklabels([f"K={k}" for k in ks])
ax.set_ylim(0, 1.0)
ax.grid(axis="y", linestyle=":", alpha=0.6)
ax.legend(frameon=True, loc="upper right")
fig.savefig(os.path.join(WORK_FIGURES, "precision_at_k_comparison.png"), dpi=200)
plt.close(fig)

# Figure 2: Feature Importances
fig, ax = plt.subplots(figsize=(9, 6))
importances = pd.Series(rf.feature_importances_, index=FEATURE_COLS).sort_values(ascending=True)
top_importances = importances.tail(10)
bars = ax.barh(top_importances.index, top_importances.values, color="#2563eb")
ax.set_xlabel("Relative Gini Feature Importance")
ax.set_title("Top 10 Feature Importances in Random Forest Refresh Classifier")
ax.grid(axis="x", linestyle=":", alpha=0.6)
fig.savefig(os.path.join(WORK_FIGURES, "feature_importance.png"), dpi=200)
plt.close(fig)

# Figure 3: Action Distribution
fig, ax = plt.subplots(figsize=(8, 5))
action_counts = df["recommended_action"].value_counts()
colors = ["#22c55e", "#3b82f6", "#f59e0b", "#a855f7", "#64748b"]
ax.bar(action_counts.index, action_counts.values, color=colors[:len(action_counts)])
ax.set_ylabel("Number of Pages")
ax.set_title("Portfolio Action Distribution Across 30,000 Evaluated Pages")
plt.xticks(rotation=25, ha="right")
ax.grid(axis="y", linestyle=":", alpha=0.6)
fig.savefig(os.path.join(WORK_FIGURES, "action_distribution.png"), dpi=200)
plt.close(fig)

# Figure 4: Staleness vs Decline Rate
fig, ax = plt.subplots(figsize=(8, 5))
df["age_tier"] = pd.cut(df["days_since_last_update"], bins=[-1, 90, 180, 365, 730, 2000], labels=["0-90d", "91-180d", "181-365d", "1-2 yrs", ">2 yrs"])
age_decline = df.groupby("age_tier", observed=False)["is_declining_label"].agg(["count", "mean"])
ax.plot(age_decline.index, age_decline["mean"], marker="o", linewidth=2.5, color="#dc2626", label="Observed Decline Rate")
ax.axhline(df["is_declining_label"].mean(), color="#64748b", linestyle="--", label=f"Average Decline Rate ({df['is_declining_label'].mean():.3f})")
ax.set_ylabel("Proportion of Pages in Search Decline")
ax.set_xlabel("Days Since Last Update")
ax.set_title("Observed Organic Search Decline Rate by Content Staleness Tier")
ax.set_ylim(0.2, 0.5)
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend()
fig.savefig(os.path.join(WORK_FIGURES, "staleness_vs_decline.png"), dpi=200)
plt.close(fig)

print("All figures successfully saved to work/figures/")

print("Done with analytics pipeline!")
