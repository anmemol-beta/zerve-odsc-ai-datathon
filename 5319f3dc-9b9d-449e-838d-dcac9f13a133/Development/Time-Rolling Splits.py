"""Time-Rolling Splits — define monthly evaluation cohorts.

The v3 model was tested on a single forward-walking cohort (2026-03 →
2026-04). That gives us one number per metric, but no read on stability:
*does the model still work when the test month moves to 2026-04? Will
the same champion model keep winning next month?*

This block carves the existing test set into monthly slices by user
signup month, producing several "rolling test cohorts" that downstream
blocks reuse. Cheap and tractable: no re-feature-build, no retrain.

Inputs:
    events                       (Example Dataset)  — for signup-month lookup
    X_v3_train, y_v3_train,
    X_v3_test, y_v3_test         (Build Features v3) — the existing splits

Outputs:
    rolling_splits     list[dict] — each element:
        { "name": "test_2026_03", "train_idx": [...], "test_idx": [...],
          "label": "March 2026", "n_train": int, "n_test": int,
          "n_test_pos": int }
    user_signup_month  pd.Series  — month-period per person_id
"""
import numpy as np
import pandas as pd

# ─── 1. signup month per user ─────────────────────────────────────────────
first_ts = events.groupby("person_id", observed=True)["timestamp"].min()
user_signup_month = first_ts.dt.to_period("M")
print(f"[rolling] derived signup month for {len(user_signup_month):,} users")
print("[rolling] signup month distribution:")
month_counts = user_signup_month.value_counts().sort_index()
for m, c in month_counts.items():
    bar = "█" * int(c / month_counts.max() * 25)
    print(f"  {m}  {c:>6,}  {bar}")

# ─── 2. align with the test set (X_v3_test users only) ───────────────────
test_ids = pd.Index(X_v3_test.index)
test_signup = user_signup_month.reindex(test_ids)
print(f"\n[rolling] test cohort signup month coverage: "
      f"{test_signup.notna().sum():,} / {len(test_ids):,}")

# ─── 3. build rolling cohorts ─────────────────────────────────────────────
# Strategy: each rolling window corresponds to a *test month* and uses the
# full training set. This isolates how the model performs on users who
# signed up at different points in time.
ROLLING_MONTHS = ["2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
rolling_splits = []
y_test_arr = np.asarray(y_v3_test)

for m in ROLLING_MONTHS:
    target_period = pd.Period(m, freq="M")
    test_mask = (test_signup == target_period).values
    if test_mask.sum() < 30:
        # too small to evaluate reliably — skip
        print(f"  skip  {m}  (only {test_mask.sum()} users)")
        continue
    n_pos = int(y_test_arr[test_mask].sum())
    rolling_splits.append({
        "name": f"test_{m.replace('-', '_')}",
        "label": pd.Period(m, freq="M").strftime("%b %Y"),
        "month": m,
        "test_mask": test_mask,
        "n_test": int(test_mask.sum()),
        "n_test_pos": n_pos,
        "test_pos_rate": n_pos / max(int(test_mask.sum()), 1),
    })

# Also one full cohort = entire X_v3_test
rolling_splits.append({
    "name": "test_full",
    "label": "Full test cohort",
    "month": "all",
    "test_mask": np.ones(len(X_v3_test), dtype=bool),
    "n_test": len(X_v3_test),
    "n_test_pos": int(y_test_arr.sum()),
    "test_pos_rate": float(y_test_arr.sum() / max(len(y_test_arr), 1)),
})

print()
print("=" * 70)
print("ROLLING COHORTS  (test set sliced by user signup month)")
print("=" * 70)
print(f"{'name':<18} {'label':<18} {'n_test':>8} {'n_pos':>8} {'pos_rate':>10}")
for s in rolling_splits:
    print(f"  {s['name']:<16} {s['label']:<18} "
          f"{s['n_test']:>8,} {s['n_test_pos']:>8,} "
          f"{s['test_pos_rate']*100:>9.2f}%")

print()
print("Note: each rolling cohort uses the SAME training set and the SAME")
print("trained model — we are measuring model stability across test months,")
print("not retraining. That isolates the 'does it still work next month?'")
print("question without needing to rebuild features at every cutoff.")
