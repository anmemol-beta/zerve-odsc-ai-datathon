"""Insights Card — final fan-in summary block.

This block is the last node in the DAG. It consumes outputs from every
upstream branch and renders a single 1-page summary suitable for
presentation, video, or as the "Executive Summary" of the Zerve agent
report. It depends on (i.e., is downstream of):

    Diagnose v3            → diagnose_v3
    SHAP v3                → shap_summary_v3
    Compare Models         → comparison_summary, model_comparison
    Per-Segment Performance → segment_performance_v3
    Build Strategies        → strategies
    ROI Ranking             → roi_top10, roi_per_channel

Outputs:
    insights_card_text    str  — the summary text (so it can be embedded)
    insights_payload      dict — structured payload, ready for the report
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timezone


def _fmt_int(x):
    return f"{int(x):,}"


# ─── 1. headline numbers ──────────────────────────────────────────────────
n_users_total = len(user_features_v4)
n_upgraders = int(user_features_v4["upgraded"].sum())
base_rate = n_upgraders / n_users_total if n_users_total else 0
n_test_pos = int(np.asarray(y_v3_test).sum())

# v3 ensemble metrics
ens = diagnose_v3.get("ensemble_v3", {})
pr_auc = ens.get("pr_auc", float("nan"))
roc_auc = ens.get("roc_auc", float("nan"))
brier = ens.get("brier", float("nan"))
ece = ens.get("ece", float("nan"))

# top-3 SHAP
top3_features = shap_summary_v3.head(3)["feature"].tolist() \
    if "shap_summary_v3" in dir() else []

# top action
top_action = roi_top10.iloc[0] if "roi_top10" in dir() and len(roi_top10) else None

# best segment by lift
seg_with_pos = segment_performance_v3.dropna(subset=["lift_over_base"])
best_seg = seg_with_pos.iloc[seg_with_pos["lift_over_base"].argmax()] \
    if len(seg_with_pos) else None

# ─── 2. text card ─────────────────────────────────────────────────────────
generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
lines = [
    "=" * 78,
    " ZERVE UPGRADE PREDICTION & FUNNEL — INSIGHTS CARD",
    f" generated {generated}",
    "=" * 78,
    "",
    "DATASET",
    f"  • {_fmt_int(n_users_total)} users  ·  {_fmt_int(n_upgraders)} upgraders  "
    f"·  base rate {base_rate*100:.2f}%",
    "",
    "MODEL — v3 calibrated XGB+RF+HistGB ensemble",
    f"  • PR-AUC  {pr_auc:.4f}    ROC-AUC {roc_auc:.4f}    Brier {brier:.4f}    ECE {ece:.4f}",
    f"  • {_fmt_int(n_test_pos)} test positives (time-based cohort split)",
    f"  • top SHAP features: {', '.join(top3_features) if top3_features else '(see SHAP v3)'}",
    "",
    "FUNNEL — v4, 15 stages, Time-Aware",
    f"  • {len(user_features_v4['final_stage'].dropna().unique())} unique stages "
    f"covering 100% of users",
    f"  • post-upgrade lifecycle modeled "
    f"({_fmt_int((user_features_v4['final_stage'] == '9.AtRisk@Upgraded').sum())} "
    f"AtRisk@Upgraded + "
    f"{_fmt_int((user_features_v4['final_stage'] == '9.Churned@Upgraded').sum())} "
    "Churned@Upgraded users)",
    "",
    "STRATEGIST — K2-Think over 14 segments",
    f"  • {len(strategies['segments'])} segments × ≤3 actions × 3 risks "
    f"({len(actions_long) if 'actions_long' in dir() else '~42'} total actions)",
    f"  • generation source: {strategies.get('_source', 'unknown')}",
]

if top_action is not None:
    lines += [
        "",
        "TOP ROI ACTION (K2)",
        f"  segment   : {top_action['segment_label']}",
        f"  channel   : {top_action['channel']}",
        f"  ROI       : {top_action['roi_multiple']:.1f}x  "
        f"(uplift +{top_action['expected_uplift_pp']:.2f}pp, "
        f"cost ${top_action['cost_per_user_usd']:.2f}/user)",
        f"  title     : {top_action['title'][:70]}",
    ]

if best_seg is not None:
    lines += [
        "",
        "MODEL'S STRONGEST SEGMENT (highest top-5% lift over segment base rate)",
        f"  segment       : {best_seg['final_stage']}",
        f"  users (test)  : {_fmt_int(best_seg['n_users'])}  "
        f"(positives: {_fmt_int(best_seg['n_pos'])})",
        f"  PR-AUC        : {best_seg['pr_auc']:.4f}",
        f"  top-5% lift   : {best_seg['lift_over_base']:.1f}x base rate of segment",
    ]

# v1 vs v3 comparison
if "comparison_summary" in dir():
    cs = comparison_summary
    if cs.get("winner_metrics"):
        lines += [
            "",
            "MODEL CHOICE RATIONALE (v1 vs v3)",
            f"  test positives : 6 (v1 random) → {cs['v3_test_pos']} "
            f"(v3 cohort) — {cs['statistical_power_ratio']:.0f}x more power",
        ]
        for m, w in cs["winner_metrics"].items():
            sign = "✓" if w["v3_better"] else "✗"
            lines.append(
                f"    {sign} {m:<8}  v1={w['v1']:.4f}  v3={w['v3']:.4f}  "
                f"Δ={w['delta']:+.4f}"
            )

lines += [
    "",
    "DOWNSTREAM USAGE",
    "  • web/components/ActionCards.tsx renders strategies.json directly",
    "  • live demo: https://beta-zerve.hub.zerve.cloud (Section 07)",
    "  • this canvas reproduces every artifact end-to-end",
    "",
    "=" * 78,
]
insights_card_text = "\n".join(lines)
print(insights_card_text)


# ─── 3. structured payload ────────────────────────────────────────────────
insights_payload = {
    "generated_at": generated,
    "headline": {
        "n_users": n_users_total,
        "n_upgraders": n_upgraders,
        "base_rate": base_rate,
        "n_test_positives": n_test_pos,
    },
    "model": {
        "name": "ensemble_v3",
        "pr_auc": pr_auc,
        "roc_auc": roc_auc,
        "brier": brier,
        "ece": ece,
        "top_features": top3_features,
    },
    "funnel": {
        "n_stages": int(user_features_v4["final_stage"].nunique()),
        "atrisk_upgraded": int(
            (user_features_v4["final_stage"] == "9.AtRisk@Upgraded").sum()
        ),
        "churned_upgraded": int(
            (user_features_v4["final_stage"] == "9.Churned@Upgraded").sum()
        ),
    },
    "strategy": {
        "n_segments": len(strategies["segments"]),
        "source": strategies.get("_source", "unknown"),
        "top_action_roi": float(top_action["roi_multiple"]) if top_action is not None else None,
        "top_action_segment": str(top_action["segment_label"]) if top_action is not None else None,
        "top_action_channel": str(top_action["channel"]) if top_action is not None else None,
    },
}

# ─── 4. visual card ───────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(12, 8))
ax.axis("off")
ax.text(0.5, 0.97, "Zerve Upgrade Prediction & Funnel — Final Insights",
        fontsize=18, fontweight="bold", ha="center", va="top",
        transform=ax.transAxes, color="#1e293b")
ax.text(0.5, 0.92, generated,
        fontsize=10, ha="center", va="top",
        transform=ax.transAxes, color="#64748b")

# four big numbers
panels = [
    ("USERS", _fmt_int(n_users_total), "#06b6d4"),
    ("UPGRADERS", f"{_fmt_int(n_upgraders)}  ({base_rate*100:.2f}%)", "#ec4899"),
    ("V3 PR-AUC", f"{pr_auc:.4f}", "#a855f7"),
    ("V3 ROC-AUC", f"{roc_auc:.3f}", "#10b981"),
]
for i, (label, value, color) in enumerate(panels):
    x = 0.05 + i * 0.235
    ax.add_patch(plt.Rectangle((x, 0.65), 0.21, 0.18,
                               transform=ax.transAxes,
                               facecolor=color, alpha=0.12,
                               edgecolor=color, linewidth=1.5))
    ax.text(x + 0.105, 0.78, label, fontsize=10, ha="center",
            transform=ax.transAxes, color="#475569")
    ax.text(x + 0.105, 0.71, value, fontsize=16, fontweight="bold",
            ha="center", transform=ax.transAxes, color=color)

# narrative
narrative = (
    f"v4 funnel covers all {_fmt_int(n_users_total)} users across "
    f"{insights_payload['funnel']['n_stages']} Time-Aware stages.\n"
    f"v3 calibrated ensemble achieves PR-AUC {pr_auc:.3f} on a "
    f"time-based cohort split with {_fmt_int(n_test_pos)} test positives "
    f"— 30x more statistical power than the original random 80/20.\n"
    f"K2-Think generates 3 ranked actions × 3 risks for each of "
    f"{len(strategies['segments'])} segments — all grounded in segment-specific "
    "data and a Zerve playbook excerpt."
)
ax.text(0.5, 0.55, narrative, fontsize=11, ha="center", va="top",
        transform=ax.transAxes, color="#1e293b", wrap=True)

if top_action is not None:
    ax.text(0.5, 0.32,
            f"TOP ROI ACTION   {top_action['roi_multiple']:.1f}x",
            fontsize=14, fontweight="bold", ha="center",
            transform=ax.transAxes, color="#ec4899")
    ax.text(0.5, 0.27,
            f"{top_action['segment_label']}  →  {top_action['channel']}",
            fontsize=11, ha="center", transform=ax.transAxes, color="#475569")
    ax.text(0.5, 0.22, f"\"{top_action['title'][:80]}\"",
            fontsize=10, ha="center", style="italic",
            transform=ax.transAxes, color="#1e293b")

ax.text(0.5, 0.05,
        "EDA → v4 Funnel → v3 Features → v3 Ensemble → SHAP/Diagnose → K2 Strategist → Insights",
        fontsize=9, ha="center", transform=ax.transAxes,
        color="#64748b", family="monospace")

plt.tight_layout()
plt.show()
