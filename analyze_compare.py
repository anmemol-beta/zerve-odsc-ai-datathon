"""
업그레이드 사용자(323명) vs 비업그레이드 사용자(17,218명) 행동 비교
- 어떤 이벤트가 업그레이드 사용자에게 더 흔한가? (lift 계산)
- 단, 명백한 leakage 이벤트는 제외하고 결과 해석
"""
import pandas as pd
from collections import defaultdict, Counter
import time

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

# 1단계: 업그레이드한 person_id 집합 확보
print("Pass 1: collecting upgraders...", flush=True)
t0 = time.time()
upgraders = set()
all_users = set()
for chunk in pd.read_csv(CSV, usecols=["person_id", "event"], chunksize=1_000_000,
                         dtype=str, low_memory=False):
    all_users.update(chunk["person_id"].dropna().unique())
    up = chunk.loc[chunk["event"] == "subscription_upgraded", "person_id"].dropna()
    upgraders.update(up.unique())
print(f"  upgraders={len(upgraders):,}  others={len(all_users)-len(upgraders):,}  "
      f"({time.time()-t0:.1f}s)", flush=True)

# 2단계: 사용자별로 가진 이벤트 종류 카운트 (per-user count → 분자)
print("Pass 2: counting events per user-group...", flush=True)
t0 = time.time()

# 그룹별: 이 이벤트를 1번이라도 한 사용자 수
upg_event_users = defaultdict(set)   # event -> set of upgraders who triggered it
oth_event_users = defaultdict(set)
# 그룹별: 이벤트 총 발생 수
upg_event_count = Counter()
oth_event_count = Counter()
# 첫 업그레이드 시점 — leakage 컷오프용 (이후 EDA에서 활용)
upg_first_upgrade_ts = {}

for chunk in pd.read_csv(CSV, usecols=["person_id", "event", "timestamp"],
                         chunksize=1_000_000, dtype=str, low_memory=False):
    chunk = chunk.dropna(subset=["person_id", "event"])
    is_upg = chunk["person_id"].isin(upgraders)

    upg_chunk = chunk[is_upg]
    oth_chunk = chunk[~is_upg]

    upg_event_count.update(upg_chunk["event"].tolist())
    oth_event_count.update(oth_chunk["event"].tolist())

    # 사용자 단위 (이 이벤트를 한 번이라도 한 사람)
    for ev, sub in upg_chunk.groupby("event"):
        upg_event_users[ev].update(sub["person_id"].unique())
    for ev, sub in oth_chunk.groupby("event"):
        oth_event_users[ev].update(sub["person_id"].unique())

    # 업그레이드 첫 시점
    sub_upg = chunk[(chunk["event"] == "subscription_upgraded")]
    grp = sub_upg.groupby("person_id")["timestamp"].min()
    for pid, ts in grp.items():
        if pid not in upg_first_upgrade_ts or ts < upg_first_upgrade_ts[pid]:
            upg_first_upgrade_ts[pid] = ts

print(f"  done ({time.time()-t0:.1f}s)", flush=True)

# 3단계: 사용자 단위 reach 비교 + 1인당 빈도 비교
n_upg = len(upgraders)
n_oth = len(all_users) - len(upgraders)

rows = []
all_events = set(upg_event_users) | set(oth_event_users)
for ev in all_events:
    u_users = len(upg_event_users.get(ev, ()))
    o_users = len(oth_event_users.get(ev, ()))
    u_count = upg_event_count.get(ev, 0)
    o_count = oth_event_count.get(ev, 0)

    upg_reach = u_users / n_upg
    oth_reach = o_users / n_oth if n_oth else 0
    # 1인당 평균 발생 횟수
    upg_per_user = u_count / n_upg
    oth_per_user = o_count / n_oth if n_oth else 0
    # reach lift (smoothing 1e-4)
    lift_reach = (upg_reach + 1e-4) / (oth_reach + 1e-4)
    lift_freq  = (upg_per_user + 1e-3) / (oth_per_user + 1e-3)

    rows.append({
        "event": ev,
        "upg_users": u_users, "upg_reach_pct": round(upg_reach*100, 2),
        "oth_users": o_users, "oth_reach_pct": round(oth_reach*100, 2),
        "lift_reach": round(lift_reach, 2),
        "upg_per_user": round(upg_per_user, 2),
        "oth_per_user": round(oth_per_user, 2),
        "lift_freq": round(lift_freq, 2),
        "total_count": u_count + o_count,
    })

df = pd.DataFrame(rows).sort_values("lift_reach", ascending=False)

# 명백한 leakage 단어 — 이건 따로 표시
LEAK_KW = ["upgrade", "subscription", "redeem", "billing", "purchase",
           "payment", "pricing", "checkout", "trial", "promo",
           "claim_free", "add_credits", "addon_credits_purchased",
           "team_plan_modal", "cancel", "downgrade", "renew_plan",
           "watermark_remove"]
def is_leak(name):
    s = (name or "").lower()
    return any(k in s for k in LEAK_KW)
df["is_leak_candidate"] = df["event"].apply(is_leak)

# 빈도 충분한 것만 필터 (유저 ≥10명에게 reach)
df_freq = df[df["upg_users"] >= 10].copy()

print("\n=== TOP LIFT (upgrader reach / non-upgrader reach) — leakage 후보 표시 ===")
print("[L] = leakage candidate (target 직전/직후 행동, 모델링에서 제외 권장)\n")
view = df_freq.sort_values("lift_reach", ascending=False).head(40)
for _, r in view.iterrows():
    flag = "[L]" if r["is_leak_candidate"] else "   "
    print(f"  {flag} lift={r['lift_reach']:>6.1f}x  "
          f"upg={r['upg_reach_pct']:>5.1f}% ({r['upg_users']:>3d})  "
          f"oth={r['oth_reach_pct']:>5.2f}%  "
          f"freq_lift={r['lift_freq']:>6.1f}x  | {r['event']}")

# leakage 제외하고 본 것만
print("\n=== TOP LIFT — LEAKAGE 후보 제외 (clean predictors) ===")
clean = df_freq[~df_freq["is_leak_candidate"]].sort_values("lift_reach", ascending=False).head(30)
for _, r in clean.iterrows():
    print(f"      lift={r['lift_reach']:>6.1f}x  "
          f"upg={r['upg_reach_pct']:>5.1f}% ({r['upg_users']:>3d})  "
          f"oth={r['oth_reach_pct']:>5.2f}%  "
          f"freq_lift={r['lift_freq']:>6.1f}x  | {r['event']}")

# 업그레이드 사용자가 거의 안 하는 행동 (negative lift)
print("\n=== INVERSE — 업그레이더가 덜 하는 이벤트 (전체 reach 5%+ 이벤트 중) ===")
common = df[df["oth_reach_pct"] >= 5].sort_values("lift_reach").head(15)
for _, r in common.iterrows():
    print(f"      lift={r['lift_reach']:>6.2f}x  "
          f"upg={r['upg_reach_pct']:>5.1f}%  "
          f"oth={r['oth_reach_pct']:>5.1f}%  | {r['event']}")

# 결과 저장
df.sort_values("lift_reach", ascending=False).to_csv(
    "/Users/hunjunsin/Desktop/zerve/event_lift_table.csv", index=False)
print("\nWROTE /Users/hunjunsin/Desktop/zerve/event_lift_table.csv")

# 업그레이더의 첫 업그레이드 시점 분포 (=가입 후 며칠만에 결제했나)
# 비교군: 그 사용자의 첫 이벤트 vs 첫 업그레이드 시점
print("\nPass 3: time-to-upgrade...", flush=True)
t0 = time.time()
user_first_event = {}
for chunk in pd.read_csv(CSV, usecols=["person_id", "timestamp"],
                         chunksize=1_000_000, dtype=str, low_memory=False):
    chunk = chunk.dropna()
    chunk = chunk[chunk["person_id"].isin(upgraders)]
    grp = chunk.groupby("person_id")["timestamp"].min()
    for pid, ts in grp.items():
        if pid not in user_first_event or ts < user_first_event[pid]:
            user_first_event[pid] = ts

ttu = []
for pid in upgraders:
    if pid in user_first_event and pid in upg_first_upgrade_ts:
        a = pd.to_datetime(user_first_event[pid], utc=True)
        b = pd.to_datetime(upg_first_upgrade_ts[pid], utc=True)
        ttu.append((b - a).total_seconds() / 86400)
ttu_s = pd.Series(ttu)
print(f"\n--- TIME TO UPGRADE (days from first event → first subscription_upgraded) ---")
print(ttu_s.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9, 0.95]).to_string())
print(f"  same-day upgraders: {(ttu_s < 1).sum()} / {len(ttu_s)}  "
      f"({(ttu_s<1).mean()*100:.1f}%)")
print(f"  within 7 days:     {(ttu_s < 7).sum()} / {len(ttu_s)}  "
      f"({(ttu_s<7).mean()*100:.1f}%)")
print(f"  done ({time.time()-t0:.1f}s)")
