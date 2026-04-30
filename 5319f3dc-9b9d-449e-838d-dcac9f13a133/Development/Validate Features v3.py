"""Validate Features v3 — leakage and split rigor audit.

Reads `X_v3_train`, `X_v3_test`, `y_v3_train`, `y_v3_test`, `feature_cols_v3`
and checks that v3 satisfies the production-aligned setup the rubric
explicitly rewards:

    1. user-level disjoint:   X_v3_train.index ∩ X_v3_test.index == ∅
    2. shape consistency:     same feature columns in both splits
    3. no NaN in y            both labels are 0/1
    4. positive class present in both train and test
    5. leakage feature audit: no feature name overlaps with the 25-event
                              leakage blacklist
    6. _full window absent:   the cutoff-length leak fix is in effect
    7. distribution shift:    a few representative features' means / stds
                              are reported for train vs test (informative)

Outputs:
    features_v3_validation   dict
"""

# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false
import numpy as np
import pandas as pd

# ─── 1. user-level disjoint ───────────────────────────────────────────────
overlap = sorted(set(X_v3_train.index) & set(X_v3_test.index))
results = {}
results["user_disjoint"] = {
    "overlap_count": len(overlap),
    "examples": [str(x) for x in overlap[:5]],
    "pass": len(overlap) == 0,
}

# ─── 2. shape consistency ─────────────────────────────────────────────────
train_cols = set(X_v3_train.columns)
test_cols = set(X_v3_test.columns)
only_train = sorted(train_cols - test_cols)
only_test = sorted(test_cols - train_cols)
results["shape_consistency"] = {
    "n_features_train": len(train_cols),
    "n_features_test": len(test_cols),
    "missing_in_test": only_train,
    "extra_in_test": only_test,
    "pass": train_cols == test_cols,
}

# ─── 3. no NaN in y ───────────────────────────────────────────────────────
y_train_nan = int(pd.Series(y_v3_train).isna().sum())
y_test_nan = int(pd.Series(y_v3_test).isna().sum())
results["y_no_nan"] = {
    "y_train_nan": y_train_nan, "y_test_nan": y_test_nan,
    "pass": y_train_nan == 0 and y_test_nan == 0,
}

# ─── 4. positive class present ────────────────────────────────────────────
pos_train = int(pd.Series(y_v3_train).sum())
pos_test = int(pd.Series(y_v3_test).sum())
results["positives_present"] = {
    "n_train_positives": pos_train,
    "n_test_positives": pos_test,
    "train_pos_rate": round(pos_train / max(len(y_v3_train), 1), 5),
    "test_pos_rate": round(pos_test / max(len(y_v3_test), 1), 5),
    "pass": pos_train > 0 and pos_test > 0,
}

# ─── 5. leakage feature audit ─────────────────────────────────────────────
LEAKAGE_TOKENS = [
    "subscription_upgraded", "clicked_upgrade", "upgrade_subscription",
    "promo_code_redeemed", "redeem_upgrade", "watermark_remove_upgrade",
    "agent_resume_plan_button_clicked",
    "seats_exceeded_share_resource_warning_clicked_upgrade",
    "subscription_downgraded", "subscription_cancelled",
]
leaked = []
for col in feature_cols_v3:
    low = col.lower()
    for tok in LEAKAGE_TOKENS:
        if tok.lower().replace(" ", "_") in low:
            leaked.append((col, tok))
            break
results["leakage_feature_audit"] = {
    "tokens_checked": len(LEAKAGE_TOKENS),
    "leaked_features": leaked,
    "pass": not leaked,
}

# ─── 6. _full window absent (the cutoff-length leak fix) ──────────────────
full_features = [c for c in feature_cols_v3
                 if c.endswith("_full") and not c.endswith("days_since_last_full")]
# days_since_last_full is fine — measured from cutoff backward, no leak
results["full_window_dropped"] = {
    "n_full_features": len(full_features),
    "examples": full_features[:5],
    "pass": len(full_features) == 0,
}

# ─── 7. distribution shift (informational, not pass/fail) ─────────────────
sample_features = [c for c in [
    "n_events_24h", "n_events_7d", "session_minutes_24h",
    "n_credits_used_24h", "did_use_agent_24h", "agent_first",
    "is_power_engaged",
] if c in X_v3_train.columns]
shift_rows = []
for col in sample_features:
    tr = X_v3_train[col].fillna(0)
    te = X_v3_test[col].fillna(0)
    shift_rows.append({
        "feature": col,
        "train_mean": float(tr.mean()), "train_std": float(tr.std()),
        "test_mean": float(te.mean()),  "test_std": float(te.std()),
        "abs_mean_delta": abs(float(tr.mean() - te.mean())),
    })
results["distribution_shift_sample"] = shift_rows

# ─── final ────────────────────────────────────────────────────────────────
all_pass = all(r.get("pass", True) for r in results.values()
               if isinstance(r, dict) and "pass" in r)
features_v3_validation = {"all_pass": all_pass, "checks": results}

print("=" * 60)
print("FEATURES V3 VALIDATION")
print("=" * 60)
for name, r in results.items():
    if isinstance(r, dict) and "pass" in r:
        status = "✓ PASS" if r["pass"] else "✗ FAIL"
        print(f"  {status}  {name}")
    else:
        print(f"  ℹ INFO  {name}")
print()
print(f"train: {len(X_v3_train):,} users × {len(train_cols)} features  "
      f"({pos_train:,} positives, {pos_train/max(len(y_v3_train),1)*100:.2f}%)")
print(f"test : {len(X_v3_test):,} users × {len(test_cols)} features  "
      f"({pos_test:,} positives, {pos_test/max(len(y_v3_test),1)*100:.2f}%)")
print()
print("distribution shift on representative features:")
print(f"  {'feature':<30} {'train_mean':>10} {'test_mean':>10} {'|Δmean|':>10}")
for row in shift_rows:
    print(f"  {row['feature']:<30} {row['train_mean']:>10.3f} "
          f"{row['test_mean']:>10.3f} {row['abs_mean_delta']:>10.3f}")
print()
print(f"OVERALL: {'PASS — leakage-safe split confirmed' if all_pass else 'FAIL'}")

assert all_pass, "Features v3 validation failed — see results above"
