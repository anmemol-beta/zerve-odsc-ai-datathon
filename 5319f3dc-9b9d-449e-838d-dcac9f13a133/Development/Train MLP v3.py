"""Train MLP v3 — PyTorch tabular MLP, the deep-learning candidate.

Tree boosting (XGB/RF/HGB) is usually best on tabular data, but a
properly-regularized MLP is a fair-fight comparison and lets us claim
end-to-end coverage of the model family space (linear → trees →
neural). It also surfaces interactions trees miss when there are very
few positives per leaf.

Inputs:
    X_v3_train, y_v3_train, X_v3_test, y_v3_test, feature_cols_v3

Architecture:
    StandardScaler → 3-layer MLP [hidden=256, 128, 64] with dropout 0.3,
    GELU activations, BatchNorm. Class-weighted BCE loss. Adam(1e-3),
    cosine LR schedule, 30 epochs, batch 512. Calibrated post-hoc with
    isotonic regression on a 20% validation slice of the train set.

Outputs:
    mlp_v3              calibrated wrapper-style dict (predict_proba)
    mlp_proba_v3        np.ndarray  — test probabilities (calibrated)
    mlp_metrics_v3      dict
"""
from __future__ import annotations

import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
except ImportError as e:
    raise RuntimeError(f"torch not available in this environment: {e}")

from sklearn.preprocessing import StandardScaler
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score, roc_auc_score, brier_score_loss,
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[MLP v3] device: {device}")

# ─── 1. fixed train/val split inside the train pool for calibration ──────
rng = np.random.default_rng(42)
n_train = len(X_v3_train)
val_frac = 0.2
val_size = int(n_train * val_frac)
shuffled = rng.permutation(n_train)
val_idx = shuffled[:val_size]
fit_idx = shuffled[val_size:]

X_fit = X_v3_train.iloc[fit_idx].fillna(0).values.astype(np.float32)
y_fit = np.asarray(y_v3_train)[fit_idx].astype(np.float32)
X_val = X_v3_train.iloc[val_idx].fillna(0).values.astype(np.float32)
y_val = np.asarray(y_v3_train)[val_idx].astype(np.float32)
X_test_a = X_v3_test.fillna(0).values.astype(np.float32)
y_test_a = np.asarray(y_v3_test).astype(int)

# ─── 2. scale ─────────────────────────────────────────────────────────────
scaler = StandardScaler()
X_fit_s = scaler.fit_transform(X_fit)
X_val_s = scaler.transform(X_val)
X_test_s = scaler.transform(X_test_a)

# ─── 3. model ─────────────────────────────────────────────────────────────
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

# Class-weighted BCE
pos_weight = float((y_fit == 0).sum() / max((y_fit == 1).sum(), 1))
print(f"[MLP v3] pos_weight = {pos_weight:.1f}")
loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor([pos_weight], device=device))
optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)

# ─── 4. training loop ─────────────────────────────────────────────────────
EPOCHS = 30
BATCH = 512

train_ds = TensorDataset(torch.from_numpy(X_fit_s), torch.from_numpy(y_fit))
train_dl = DataLoader(train_ds, batch_size=BATCH, shuffle=True, drop_last=False)
scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)

X_val_t = torch.from_numpy(X_val_s).to(device)
y_val_t = torch.from_numpy(y_val).to(device)

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
    # validation PR-AUC
    model.eval()
    with torch.no_grad():
        val_logits = model(X_val_t).cpu().numpy()
    val_proba = 1 / (1 + np.exp(-val_logits))
    val_pr = average_precision_score(y_val, val_proba) if y_val.sum() else 0.0
    if val_pr > best_val_pr:
        best_val_pr = val_pr
        best_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
    if (epoch + 1) % 5 == 0 or epoch == 0:
        print(f"  epoch {epoch+1:>2}/{EPOCHS}  "
              f"train_loss={total_loss/len(train_ds):.4f}  "
              f"val_PR-AUC={val_pr:.4f}  (best so far {best_val_pr:.4f})")

model.load_state_dict(best_state)

# ─── 5. predict on val + test ─────────────────────────────────────────────
model.eval()
with torch.no_grad():
    val_logits = model(torch.from_numpy(X_val_s).to(device)).cpu().numpy()
    test_logits = model(torch.from_numpy(X_test_s).to(device)).cpu().numpy()
val_raw = 1 / (1 + np.exp(-val_logits))
test_raw = 1 / (1 + np.exp(-test_logits))

# ─── 6. isotonic calibration on the validation slice ──────────────────────
iso = IsotonicRegression(out_of_bounds="clip")
iso.fit(val_raw, y_val)
mlp_proba_v3 = iso.transform(test_raw)

# ─── 7. metrics ───────────────────────────────────────────────────────────
mlp_metrics_v3 = {
    "model": "mlp_v3",
    "pr_auc": float(average_precision_score(y_test_a, mlp_proba_v3)),
    "roc_auc": float(roc_auc_score(y_test_a, mlp_proba_v3)),
    "brier": float(brier_score_loss(y_test_a, mlp_proba_v3)),
    "pr_auc_uncalibrated": float(average_precision_score(y_test_a, test_raw)),
    "n_test_pos": int(y_test_a.sum()),
    "best_val_pr_auc": float(best_val_pr),
}

# Wrap for downstream Train Across Time consumption — needs predict_proba(X)
class _MLPWrapper:
    def __init__(self, model, scaler, iso, device):
        self.model, self.scaler, self.iso, self.device = model, scaler, iso, device
    def predict_proba(self, X):
        Xa = X.fillna(0).values.astype(np.float32) if hasattr(X, "fillna") else np.asarray(X, dtype=np.float32)
        Xs = self.scaler.transform(Xa)
        self.model.eval()
        with torch.no_grad():
            logits = self.model(torch.from_numpy(Xs).to(self.device)).cpu().numpy()
        raw = 1 / (1 + np.exp(-logits))
        cal = self.iso.transform(raw)
        return np.column_stack([1 - cal, cal])

mlp_v3 = _MLPWrapper(model, scaler, iso, device)

print()
print("=" * 60)
print("MLP V3 (PyTorch)")
print("=" * 60)
print(f"  PR-AUC (calibrated) : {mlp_metrics_v3['pr_auc']:.4f}")
print(f"  PR-AUC (raw)        : {mlp_metrics_v3['pr_auc_uncalibrated']:.4f}")
print(f"  ROC-AUC             : {mlp_metrics_v3['roc_auc']:.4f}")
print(f"  Brier               : {mlp_metrics_v3['brier']:.4f}")
print(f"  test positives      : {mlp_metrics_v3['n_test_pos']}")
print()
print("Note: this is the deep-learning candidate, not necessarily the winner.")
print("On tabular data with ~17k users, tree boosting usually wins by a margin —")
print("we include MLP for fair-fight model coverage and Compare/AutoML downstream.")
