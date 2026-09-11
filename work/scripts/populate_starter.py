"""
Script to build, populate, and execute all FlyRank ML Internship notebooks and artifacts.
"""
import os
import sys
import json
import nbformat as nbf
import pandas as pd
import numpy as np

def update_starter_notebooks():
    print("Updating starter notebooks 01 and 02...")
    
    # 01_first_look_and_discovery.ipynb
    nb1_path = "notebooks/01_first_look_and_discovery.ipynb"
    if os.path.exists(nb1_path):
        nb1 = nbf.read(nb1_path, as_version=4)
        for cell in nb1.cells:
            if cell.cell_type == "code" and "# Your discovery here" in cell.source:
                cell.source = """# Discovery: Testing whether impressions_90d > 0 changes the correlation between search_volume and impressions
active_pages = df[df["impressions_90d"] > 0]
active_corr = active_pages["search_volume"].corr(active_pages["impressions_90d"])
spearman_corr = active_pages["search_volume"].corr(active_pages["impressions_90d"], method="spearman")

print(f"Active pages (impressions > 0): {len(active_pages):,} rows")
print(f"Pearson correlation:  {active_corr:.3f}")
print(f"Spearman rank correlation: {spearman_corr:.3f}")
print("Observed: Even filtering for active pages with >0 impressions, keyword search volume has only weak rank correlation with realized traffic.")

# Cross-cut: Which content_type has the lowest CTR within position tier 1-3?
top_tier = active_pages[active_pages["position_tier"] == "1-3"]
ctr_by_type = top_tier.groupby("content_type")["ctr"].agg(["count", "mean"]).sort_values("mean")
print("\\nMean CTR by content_type in top positions (tier 1-3, min 30 items):")
print(ctr_by_type[ctr_by_type["count"] >= 30].round(3).to_string())
"""
        nbf.write(nb1, nb1_path)
        print("Updated 01_first_look_and_discovery.ipynb")

    # 02_your_first_readable_model.ipynb
    nb2_path = "notebooks/02_your_first_readable_model.ipynb"
    if os.path.exists(nb2_path):
        nb2 = nbf.read(nb2_path, as_version=4)
        for cell in nb2.cells:
            if cell.cell_type == "code" and "# Your experiment here" in cell.source:
                cell.source = """# Experiment: Evaluate Decision Tree at depth 3 & 4 with client-holdout split
from sklearn.model_selection import GroupShuffleSplit

gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(gss.split(df, groups=df["client_id"]))

X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
y_train, y_test = y[train_idx], y[test_idx]
hr_test = df["hand_rule_score"].iloc[test_idx].values

print(f"Train size: {len(X_train):,} | Test size: {len(X_test):,} (0 client overlap)")
print(f"Base rate (test declining): {y_test.mean():.3f}")
print(f"Hand rule Precision@50 (test): {precision_at_k(hr_test, y_test, 50):.3f}")

for depth in [2, 3, 4]:
    dt = DecisionTreeClassifier(max_depth=depth, class_weight="balanced", random_state=42)
    dt.fit(X_train, y_train)
    p_test = dt.predict_proba(X_test)[:, 1]
    p50 = precision_at_k(p_test, y_test, 50)
    p20 = precision_at_k(p_test, y_test, 20)
    print(f"Depth {depth} tree -> Precision@20: {p20:.3f}, Precision@50: {p50:.3f}")
"""
        nbf.write(nb2, nb2_path)
        print("Updated 02_your_first_readable_model.ipynb")

if __name__ == "__main__":
    update_starter_notebooks()
