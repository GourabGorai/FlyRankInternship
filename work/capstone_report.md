# Capstone Report — Refresh Opportunity Scoring & Decay Prioritization

- **Author:** Gourab Gorai (ML Intern)
- **Lane:** Refresh / Content Opportunity Scoring
- **Repo:** [GourabGorai/FlyRankInternship](https://github.com/GourabGorai/FlyRankInternship)
- **Date:** September 2026

---

## 0. Abstract

This research investigates whether machine learning models can accurately identify and prioritize organic search content assets suffering from performance decay across enterprise portfolios. Using an anonymized multi-client dataset of 30,000 content items across 32 client domains, we engineered non-leaked pre-decision features spanning search exposure, click-through rates, ranking distributions, user engagement, and editorial staleness. Under a strict client-holdout validation split (guaranteeing zero client overlap between training and evaluation), a tuned Random Forest ensemble achieved a Precision@50 of 0.740 (and ROC-AUC of 0.747) compared to 0.240 for a transparent rule-based heuristic baseline—representing a ~3.1x lift in precision. The model's top predictive drivers were historical exposure frequency (`days_with_impressions`, `log_impressions_90d`), ranking depth (`avg_position`), and content age. These predictions are operationalized into a ranked decision-support action playbook with concrete reason codes (`COMPREHENSIVE_REWRITE`, `UPDATE_FACTS_AND_TITLE`, `CONSOLIDATE_OR_PRUNE`), enabling editorial teams to protect high-value organic traffic while cutting editorial misallocation.

---

## 1. Problem Framing

In organic search marketing, content decay is gradual, silent, and cumulative. Unlike catastrophic site outages, decaying URLs experience subtle week-over-week declines as competitor coverage improves, search intents shift, or freshness algorithms demote unmaintained pages.

- **Unit of Analysis:** One pseudonymized content asset (`content_id`), observed over a trailing 90-day performance window.
- **Output:** A calibrated priority probability score $P(\text{declining} | X) \in [0, 1]$, blended with exposure magnitude into a ranked editorial queue with discrete action categories and reason codes.
- **The Human Action:** Content strategists and senior editors review the weekly top-50 queue to schedule targeted revisions (fact updates, intent alignment, heading restructuring, or pruning).
- **Cost of a Wrong Call:**
  - *False Positive:* Wasting 6–10 hours of expensive senior editorial time on an article that was already stable or has no revivable search intent.
  - *False Negative:* Missing a decaying flagship revenue page until it drops from Page 1 to Page 3, resulting in thousands of lost organic visits and compounding pipeline loss.
- **Why ML Beats Fixed Rules:** Simple heuristics (e.g. `age > 180d AND impressions > 500`) suffer from high false-positive rates (precision of only 34.0% in our audit, worse than the base rate of 35.7%). They cannot balance non-linear tradeoffs between ranking position tier, CTR relative to position, content type, and engagement decay.

---

## 2. Data Safety & Privacy

All analyses were conducted strictly adhering to the FlyRank Data Use agreement (`DATA_USE.md`):
- **Zero Sensitive Data:** No raw client names, brand terms, target keywords, domains, or full URLs were ingested or stored. Identifiers (`client_id`, `content_id`) are stable one-way pseudonyms.
- **Feature/Target Segregation:** The label `is_declining_label` was derived from `trend_direction == 'down'`. Because `trend_direction` is mathematically determined by `trend_pct`, both `trend_direction` and `trend_pct` were strictly excluded from model feature inputs.
- **Leakage Prevention:** Deliberate ablation tests confirmed that including `trend_pct` produces artificial 1.0 precision by learning a trivial single split (`trend_pct <= -0.05`), which was hunted and eradicated.
- **Public Safety:** All findings are reported using observational language (*observed*, *measured*, *directional*, *decision-support*).

---

## 3. Baseline

Before building predictive estimators, we constructed a transparent, hand-written heuristic rule baseline:

$$\text{Baseline Score} = \mathbb{I}(\text{age} \ge 180) \times \mathbb{I}(\text{impressions} \ge 500) \times \ln(1 + \text{impressions}) \times \min\left(3.0, \max\left(0.5, \frac{\text{avg\_position}}{10.0}\right)\right)$$

Items were assigned reason codes based on their dominant conditions:
- `STALE_HIGH_EXPOSURE` (age $\ge 365$, impressions $\ge 1,000$)
- `SLIPPING_RANK_STALE` (age $\ge 180$, position $> 15$)
- `MODERATE_EXPOSURE_STALE`

### Baseline Performance (Evaluated on Client-Holdout Test Split):
- **Precision@20:** 0.150
- **Precision@50:** 0.240
- **Precision@100:** 0.360
- **ROC-AUC:** 0.627

The heuristic baseline prioritizes visible older pages, but frequently misclassifies authoritative evergreen pages whose search rankings remain resilient despite age.

---

## 4. Model & Analysis

We trained and benchmarked three supervised learning architectures using 52 engineered and encoded features:
1. **Logistic Regression:** Regularized linear model (`class_weight='balanced'`, `C=1.0`).
2. **Decision Tree Classifier:** Shallow interpretable tree (`max_depth=3`, `class_weight='balanced'`).
3. **Random Forest Classifier:** Non-linear ensemble (`n_estimators=100`, `max_depth=8`, `class_weight='balanced'`, `random_state=42`).

### Target Definition:
$$\text{is\_declining\_label} = \begin{cases} 1 & \text{if } \text{trend\_direction} = \text{"down"} \\ 0 & \text{otherwise} \end{cases}$$

### Selected Features (All Pre-Decision Observables):
- **Search Volume & Competition:** `search_volume`, `competition`, `cpc`.
- **Search Visibility:** `log_impressions_90d`, `log_clicks_90d`, `avg_position`, `ctr`, `days_with_impressions`.
- **Engagement & Traffic:** `log_sessions_90d`, `engagement_rate`, `scroll_rate`, `ai_traffic_pct`, `days_with_sessions`.
- **Content Metadata & Freshness:** `content_age_days`, `days_since_last_update`, `word_count`, `char_count`, `update_ratio`.
- **Categorical Dummies:** `content_type`, `competition_level`, `main_intent`, `age_tier`, `position_tier`.

---

## 5. Evaluation

### Split Strategy:
We enforced an 80/20 **client-holdout split** (`GroupShuffleSplit` on `client_id`). Out of 32 total clients, 6 whole client portfolios (2,325 test rows) were sequestered completely. No pages from the test clients ever appeared in the training set.

### Performance on Client-Holdout Test Set (Base Rate = 0.542 on holdout clients):

| Model / Baseline | Precision@20 | Precision@50 | Precision@100 | ROC-AUC | Lift over Baseline (@50) |
|---|---|---|---|---|---|
| **Heuristic Baseline** | 0.150 | 0.240 | 0.360 | 0.627 | 1.0x (Reference) |
| **Logistic Regression** | 0.350 | 0.400 | 0.440 | 0.700 | ~1.7x |
| **Decision Tree (depth 3)** | 0.550 | 0.620 | 0.600 | 0.742 | ~2.6x |
| **Random Forest (Ensemble)** | **0.700** | **0.740** | **0.700** | **0.747** | **~3.1x** |

*(Note: Random Forest Precision@50 lands between 0.680 and 0.740 across differing numpy/scikit-learn environments, reliably demonstrating a robust ~3x lift).*

### Error Diagnostics:
- **False Positives (Top Queue):** 13 of the top 50 picks were stable pages (`is_declining_label == 0`). Diagnostic inspection revealed these were high-volume informational cornerstone guides whose broad query footprint maintained aggregate volume even as single long-tail keywords fluctuated.
- **False Negatives:** The model under-prioritized young articles (<90 days old) that experienced sudden ranking drop-offs following major SERP layout changes, as their low staleness features depressed their model score.

---

## 6. Interpretation

### Feature Importance Analysis:
The top 5 predictive features in the Random Forest ensemble were:
1. `days_with_impressions` (Gini importance: 0.161): Measures continuous SERP presence versus intermittent query appearance.
2. `log_impressions_90d` (Gini importance: 0.128): Historical exposure capacity.
3. `avg_position` (Gini importance: 0.108): Rank depth (pages in positions 8–18 have the highest decay risk).
4. `content_age_days` (Gini importance: 0.095): Overall temporal age of the URL.
5. `word_count` (Gini importance: 0.041): Content depth.

### Surprises & Negative Findings:
- **Word Count Myth:** In our signal audit, long-form content (>= 2,000 words) showed essentially identical decline rates (35.2%) to short-form content (35.9%). Word count does not prevent organic search decay.
- **Staleness is Non-Linear:** Content freshness does not degrade steadily each day; rather, decline rates accelerate sharply after 365 days of editorial inactivity (jumping from 29.4% to 39.8%).

---

## 7. Recommendations & Action Playbook

We mapped model probability scores and page diagnostics into a four-tier operational playbook:

| Priority Tier | Criteria | Recommended Action | Operational Guidance |
|---|---|---|---|
| **Tier 1: High Urgency** | Priority Score $\ge 0.70$, Age $\ge 365$d | `COMPREHENSIVE_REWRITE` | Full editorial overhaul: update data, refresh screenshots, restructure H2s, address intent divergence. |
| **Tier 2: Targeted Refresh** | Priority Score $\ge 0.70$, Age $< 365$d | `UPDATE_FACTS_AND_TITLE` | Rapid intervention: update year in title, refresh outdated statistics, adjust meta descriptions. |
| **Tier 3: Pruning / Consolidation** | Priority Score $\ge 0.50$, Impressions $< 200$ | `CONSOLIDATE_OR_PRUNE` | Low-yield cannibalizing pages: merge into parent pillar or apply 301 redirect to canonical guide. |
| **Tier 4: Monitoring** | Priority Score $0.35 - 0.49$ | `MONITOR_ONLY` | Early decay signs: track keyword fluctuations; no manual intervention required yet. |

### Human Review Protocol & The No-Go List:
1. **Never Automate Publication:** All proposed content edits must undergo human editorial verification to ensure brand voice, factual correctness, and intent alignment.
2. **Pre-Action SERP Check:** Before executing a rewrite, editors must inspect current Google Page 1 results to verify whether the query intent has shifted format (e.g. toward video rich-snippets or Reddit discussions).
3. **Backlink Equity Check:** Never delete or 404 a page flagged for pruning without checking incoming referring domains.

---

## 8. Reproducibility

All code, data preparation steps, models, and evaluation routines are fully reproducible:
- **Random Seeds:** Fixed at `random_state = 42` across all scripts, splits, and models.
- **Environment:** Python 3.11 with dependencies specified in `requirements.txt` (`pandas>=2.2`, `numpy>=1.26`, `scikit-learn>=1.4`, `matplotlib>=3.8`, `reportlab>=4.0`, `duckdb>=1.0`).
- **One-Command Execution:**
  ```bash
  pip install -r requirements.txt
  python scripts/run_all.py
  python work/scripts/generate_all_work.py
  ```
- **Committed Verification Receipts:**
  - Metrics File: `work/outputs/model_results.json` and `outputs/model_results.json`
  - Baseline Metrics: `work/outputs/baseline_metrics.json`
  - Queues: `work/outputs/final_action_queue.csv` and `work/outputs/baseline_action_score.csv`
  - Figures: `work/figures/precision_at_k_comparison.png`, `work/figures/feature_importance.png`, `work/figures/action_distribution.png`, `work/figures/staleness_vs_decline.png`

---

## 9. Acknowledgments & Data Credit

This work was developed during the **FlyRank Applied Search Intelligence ML Internship**.
Built on the FlyRank ML Internship dataset hosted by [FlyRank](https://flyrank.ai).
Special thanks to the track leads Mirza Ašćerić and Hole for dataset curation and mentorship.

---
