"""Train MLP v3 — PyTorch tabular MLP with sklearn fallback.

The deep-learning candidate in the AutoML pool. Tree boosting (XGB/RF/HGB/
CatBoost) usually wins on tabular data, but a properly-regularized MLP is
a fair-fight comparison and lets us claim end-to-end model-family coverage
(linear → trees → neural).

Two execution paths:

  Path A — PyTorch (primary, when `torch<3` is installed)
        StandardScaler → 3-layer MLP [256, 128, 64] with BatchNorm/GELU/
        Dropout, class-weighted BCEWithLogitsLoss, Adam(1e-3) + cosine LR,
        30 epochs, batch 512. Best-by-val-PR-AUC checkpoint, then isotonic
        calibration on a held-out 20% slice.

  Path B — sklearn MLPClassifier (fallback if torch import fails)
        Same architecture (3-layer FF, ReLU, Adam), 200-iter max with
        early stopping. SMOTE oversampling for imbalance (or duplicate
        oversample if imbalanced-learn missing). Calibrated with
        CalibratedClassifierCV(cv=3, isotonic).

Either way, outputs are interchangeable:

    mlp_v3              wrapper exposing predict_proba(X)
    mlp_proba_v3        np.ndarray  — test set positive-class probabilities
    mlp_metrics_v3      dict
    mlp_backend         str  — "torch" | "sklearn"

Inputs (from canvas namespace):
    X_v3_train, y_v3_train, X_v3_test, y_v3_test, feature_cols_v3
"""
from __future__ import annotations

import warnings
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)

# Decide path at import time
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_OK = True
except Exception as e:
    print(f"[MLP v3] torch import failed ({e}) — falling back to sklearn MLPClassifier")
    TORCH_OK = False

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
)


# ─── shared data prep ─────────────────────────────────────────────────────
X_train_a = X_v3_train.fillna(0).values.astype(np.float32)
y_train_a = np.asarray(y_v3_train).astype(np.float32)
X_test_a = X_v3_test.fillna(0).values.astype(np.float32)
y_test_a = np.asarray(y_v3_test).astype(int)


# ═══ PATH A — PyTorch ════════════════════════════════════════════════════
if TORCH_OK:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[MLP v3] backend=torch  device={device}")

    # 1. carve a calibration validation slice from the train pool
    rng = np.random.default_rng(42)
    n_train = len(X_train_a)
    val_size = int(n_train * 0.2)
    shuffled = rng.permutation(n_train)
    val_idx = shuffled[:val_size]
    fit_idx = shuffled[val_size:]

    X_fit = X_train_a[fit_idx]
    y_fit = y_train_a[fit_idx]
    X_val = X_train_a[val_idx]
    y_val = y_train_a[val_idx]

    scaler = StandardScaler()
    X_fit_s = scaler.fit_transform(X_fit)
    X_val_s = scaler.transform(X_val)
    X_test_s = scaler.transform(X_test_a)

    # 2. model
    class TabularMLP(nn.Module):
        def __init__(self, n_in: int, p_drop: float = 0.3):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(n_in, 256), nn.BatchNorm1d(256), nn.GELU(), nn.Dropout(p_drop),
                nn.Linear(256, 128),  nn.BatchNorm1d(128), nn.GELU(), nn.Dropout(p_drop),
                nn.Linear(128, 64),   nn.BatchNorm1d(64),  nn.GELU(), nn.Dropout(p_drop),
                nn.Linear(64, 1),
            )
        def forward(self, x):
            return self.net(x).squeeze(-1)

    torch.manual_seed(42)
    model = TabularMLP(n_in=X_fit_s.shape[1]).to(device)
    pos_weight = float((y_fit == 0).sum() / max((y_fit == 1).sum(), 1))
    print(f"[MLP v3] pos_weight={pos_weight:.1f}")

    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], device=device))
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)

    EPOCHS = 30
    BATCH = 512
    train_ds = TensorDataset(torch.from_numpy(X_fit_s), torch.from_numpy(y_fit))
    train_dl = DataLoader(train_ds, batch_size=BATCH, shuffle=True, drop_last=False)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
    X_val_t = torch.from_numpy(X_val_s).to(device)

    best_val_pr = -1.0
    best_state = None
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0.0
        for xb, yb in train_dl:
            xb = xb.to(device, non_blocking=True)
            yb = yb.to(device, non_blocking=True)
            optimizer.zero_grad()
            logits = model(xb)
            loss = loss_fn(logits, yb)
            loss.backward()
            optimizer.step()
            total_loss += float(loss) * len(xb)
        scheduler.step()
        model.eval()
        with torch.no_grad():
            val_logits = model(X_val_t).cpu().numpy()
        val_proba = 1 / (1 + np.exp(-val_logits))
        val_pr = average_precision_score(y_val, val_proba) if y_val.sum() else 0.0
        if val_pr > best_val_pr:
            best_val_pr = val_pr
            best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"  epoch {epoch+1:>2}/{EPOCHS}  train_loss={total_loss/len(train_ds):.4f}  "
                  f"val_PR-AUC={val_pr:.4f}  (best {best_val_pr:.4f})")

    model.load_state_dict(best_state)

    # 3. predict + isotonic calibration on val slice
    model.eval()
    with torch.no_grad():
        val_logits = model(torch.from_numpy(X_val_s).to(device)).cpu().numpy()
        test_logits = model(torch.from_numpy(X_test_s).to(device)).cpu().numpy()
    val_raw = 1 / (1 + np.exp(-val_logits))
    test_raw = 1 / (1 + np.exp(-test_logits))

    from sklearn.isotonic import IsotonicRegression
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(val_raw, y_val)
    mlp_proba_v3 = iso.transform(test_raw)

    class _TorchMLPWrapper:
        def __init__(self, model, scaler, iso, device):
            self.model, self.scaler, self.iso, self.device = model, scaler, iso, device
        def predict_proba(self, X):
            Xa = X.fillna(0).values.astype(np.float32) if hasattr(X, "fillna") \
                 else np.asarray(X, dtype=np.float32)
            Xs = self.scaler.transform(Xa)
            self.model.eval()
            with torch.no_grad():
                logits = self.model(torch.from_numpy(Xs).to(self.device)).cpu().numpy()
            raw = 1 / (1 + np.exp(-logits))
            cal = self.iso.transform(raw)
            return np.column_stack([1 - cal, cal])

    mlp_v3 = _TorchMLPWrapper(model, scaler, iso, device)
    mlp_backend = "torch"
    backend_meta = {
        "epochs_run": EPOCHS,
        "best_val_pr_auc": float(best_val_pr),
        "pos_weight": pos_weight,
        "device": str(device),
    }


# ═══ PATH B — sklearn fallback ═══════════════════════════════════════════
else:
    print("[MLP v3] backend=sklearn  (MLPClassifier — pure sklearn)")
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.calibration import CalibratedClassifierCV

    # light oversampling for imbalance
    USE_SMOTE = False
    try:
        from imblearn.over_sampling import SMOTE
        sm = SMOTE(random_state=42, k_neighbors=5, sampling_strategy=1/10)
        X_train_bal, y_train_bal = sm.fit_resample(X_train_a, y_train_a.astype(int))
        USE_SMOTE = True
        print(f"  SMOTE: {len(X_train_a):,} → {len(X_train_bal):,} rows")
    except Exception as e:
        print(f"  imblearn unavailable ({e}); duplicating positives")
        rng2 = np.random.default_rng(42)
        pos_idx = np.where(y_train_a == 1)[0]
        neg_idx = np.where(y_train_a == 0)[0]
        target_pos = max(len(pos_idx) * 5, len(neg_idx) // 10)
        pos_resample = rng2.choice(pos_idx, size=target_pos, replace=True)
        keep = np.concatenate([neg_idx, pos_resample])
        X_train_bal = X_train_a[keep]
        y_train_bal = y_train_a[keep].astype(int)

    base = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPClassifier(
            hidden_layer_sizes=(256, 128, 64), activation="relu",
            solver="adam", alpha=1e-4, learning_rate_init=1e-3,
            max_iter=200, early_stopping=True, validation_fraction=0.1,
            n_iter_no_change=10, random_state=42, verbose=False,
        )),
    ])
    mlp_v3 = CalibratedClassifierCV(base, method="isotonic", cv=3)
    mlp_v3.fit(X_train_bal, y_train_bal.astype(int))
    mlp_proba_v3 = mlp_v3.predict_proba(X_test_a)[:, 1]
    mlp_backend = "sklearn"
    backend_meta = {
        "balanced_with": "SMOTE" if USE_SMOTE else "duplicate_oversample",
        "balanced_train_size": int(len(X_train_bal)),
    }


# ═══ shared metrics + report ═════════════════════════════════════════════
mlp_metrics_v3 = {
    "model": "mlp_v3",
    "backend": mlp_backend,
    "pr_auc":  float(average_precision_score(y_test_a, mlp_proba_v3)),
    "roc_auc": float(roc_auc_score(y_test_a, mlp_proba_v3)),
    "brier":   float(brier_score_loss(y_test_a, mlp_proba_v3)),
    "n_test_pos": int(y_test_a.sum()),
    **backend_meta,
}

print()
print("=" * 60)
print(f"MLP V3 — backend = {mlp_backend}")
print("=" * 60)
print(f"  PR-AUC      : {mlp_metrics_v3['pr_auc']:.4f}")
print(f"  ROC-AUC     : {mlp_metrics_v3['roc_auc']:.4f}")
print(f"  Brier       : {mlp_metrics_v3['brier']:.4f}")
print(f"  test +      : {mlp_metrics_v3['n_test_pos']}")
for k, v in backend_meta.items():
    print(f"  {k:<11} : {v}")
print()
print("Note: this is the deep-learning candidate, not necessarily the winner.")
print("On tabular data with ~17k users, tree boosting usually wins by a margin —")
print("we include MLP for fair-fight model-family coverage.")
