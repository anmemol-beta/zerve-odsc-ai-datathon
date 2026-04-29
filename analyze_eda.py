"""
Zerve Hackathon - 원본 데이터 1차 EDA
- 350만+ 행, 861MB → 청크 단위로 처리
- 목적: 이벤트 분포, 사용자 수, 시간 범위, leakage 후보, 업그레이드 비율 등 핵심 통계
"""
import pandas as pd
from collections import Counter
import time

CSV = "/Users/hunjunsin/Desktop/zerve/zerve_events.csv"

# 가벼운 컬럼만 우선 로드 (전체 column 80개+ 중 핵심만)
USECOLS = [
    "person_id", "timestamp", "event",
    "person_properties.role", "person_properties.purpose", "person_properties.work_type",
    "person_properties.source", "person_properties.cloudProvider",
    "properties.$geoip_country_name", "properties.$device_type", "properties.$os",
    "properties.subscription_type", "properties.feature_tag",
    "properties.tool_name", "properties.button_name",
    "properties.utm_source", "properties.utm_campaign",
    "properties.workspace_id",
]

t0 = time.time()
event_counter = Counter()
user_set = set()
upgrader_set = set()
country_counter = Counter()
device_counter = Counter()
os_counter = Counter()
role_counter = Counter()
purpose_counter = Counter()
worktype_counter = Counter()
source_counter = Counter()
subscription_counter = Counter()
feature_counter = Counter()
tool_counter = Counter()
button_counter = Counter()
utm_source_counter = Counter()

# 사용자별 첫/마지막 이벤트 timestamp, 이벤트 수
user_first_ts = {}
user_last_ts = {}
user_event_count = Counter()

# 시간 범위
min_ts, max_ts = None, None

total_rows = 0
chunk_n = 0
CHUNK = 500_000

for chunk in pd.read_csv(CSV, usecols=USECOLS, chunksize=CHUNK,
                          dtype=str, low_memory=False):
    chunk_n += 1
    total_rows += len(chunk)

    # 이벤트 분포
    event_counter.update(chunk["event"].dropna().tolist())

    # 고유 사용자
    pids = chunk["person_id"].dropna()
    user_set.update(pids.unique())

    # 업그레이드한 사용자
    up = chunk.loc[chunk["event"] == "subscription_upgraded", "person_id"].dropna()
    upgrader_set.update(up.unique())

    # 사용자별 통계
    user_event_count.update(pids.tolist())

    # timestamp 처리 (string min/max는 ISO format이라 lexicographic OK)
    ts = chunk["timestamp"].dropna()
    if len(ts):
        cur_min, cur_max = ts.min(), ts.max()
        min_ts = cur_min if min_ts is None else min(min_ts, cur_min)
        max_ts = cur_max if max_ts is None else max(max_ts, cur_max)

    # 사용자별 첫/마지막 ts (sample용 — 너무 무거우면 skip)
    grp = chunk.groupby("person_id")["timestamp"].agg(["min", "max"])
    for pid, row in grp.iterrows():
        if pid in user_first_ts:
            if row["min"] < user_first_ts[pid]:
                user_first_ts[pid] = row["min"]
            if row["max"] > user_last_ts[pid]:
                user_last_ts[pid] = row["max"]
        else:
            user_first_ts[pid] = row["min"]
            user_last_ts[pid] = row["max"]

    # 카테고리 분포
    country_counter.update(chunk["properties.$geoip_country_name"].dropna().tolist())
    device_counter.update(chunk["properties.$device_type"].dropna().tolist())
    os_counter.update(chunk["properties.$os"].dropna().tolist())
    role_counter.update(chunk["person_properties.role"].dropna().tolist())
    purpose_counter.update(chunk["person_properties.purpose"].dropna().tolist())
    worktype_counter.update(chunk["person_properties.work_type"].dropna().tolist())
    source_counter.update(chunk["person_properties.source"].dropna().tolist())
    subscription_counter.update(chunk["properties.subscription_type"].dropna().tolist())
    feature_counter.update(chunk["properties.feature_tag"].dropna().tolist())
    tool_counter.update(chunk["properties.tool_name"].dropna().tolist())
    button_counter.update(chunk["properties.button_name"].dropna().tolist())
    utm_source_counter.update(chunk["properties.utm_source"].dropna().tolist())

    print(f"[chunk {chunk_n}] rows={total_rows:,} elapsed={time.time()-t0:.1f}s "
          f"users={len(user_set):,} upgraders={len(upgrader_set):,}", flush=True)

print("\n" + "="*70)
print(f"TOTAL ROWS: {total_rows:,}")
print(f"UNIQUE USERS: {len(user_set):,}")
print(f"UPGRADED USERS: {len(upgrader_set):,}  "
      f"({len(upgrader_set)/len(user_set)*100:.2f}%)")
print(f"TIME RANGE: {min_ts}  →  {max_ts}")
print(f"ELAPSED: {time.time()-t0:.1f}s")

print("\n--- TOP 50 EVENTS ---")
for ev, c in event_counter.most_common(50):
    print(f"  {c:>10,}  {ev}")

print(f"\nUNIQUE EVENT TYPES: {len(event_counter)}")

print("\n--- COUNTRIES (top 15) ---")
for k, v in country_counter.most_common(15):
    print(f"  {v:>10,}  {k}")

print("\n--- DEVICE TYPE ---")
for k, v in device_counter.most_common():
    print(f"  {v:>10,}  {k}")

print("\n--- OS (top 10) ---")
for k, v in os_counter.most_common(10):
    print(f"  {v:>10,}  {k}")

print("\n--- ROLE ---")
for k, v in role_counter.most_common():
    print(f"  {v:>10,}  {k}")

print("\n--- PURPOSE ---")
for k, v in purpose_counter.most_common():
    print(f"  {v:>10,}  {k}")

print("\n--- WORK_TYPE ---")
for k, v in worktype_counter.most_common():
    print(f"  {v:>10,}  {k}")

print("\n--- SOURCE (signup) ---")
for k, v in source_counter.most_common(15):
    print(f"  {v:>10,}  {k}")

print("\n--- SUBSCRIPTION_TYPE ---")
for k, v in subscription_counter.most_common():
    print(f"  {v:>10,}  {k}")

print("\n--- FEATURE TAG (top 20) ---")
for k, v in feature_counter.most_common(20):
    print(f"  {v:>10,}  {k}")

print("\n--- TOOL_NAME (top 20) ---")
for k, v in tool_counter.most_common(20):
    print(f"  {v:>10,}  {k}")

print("\n--- BUTTON_NAME (top 20) ---")
for k, v in button_counter.most_common(20):
    print(f"  {v:>10,}  {k}")

print("\n--- UTM_SOURCE (top 15) ---")
for k, v in utm_source_counter.most_common(15):
    print(f"  {v:>10,}  {k}")

# 사용자별 이벤트 수 분포
ec = pd.Series(user_event_count)
print("\n--- USER EVENT COUNT distribution ---")
print(ec.describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99]).to_string())

# 사용자 활동 기간 분포
df_user = pd.DataFrame({
    "first": pd.to_datetime(pd.Series(user_first_ts), utc=True, errors="coerce"),
    "last":  pd.to_datetime(pd.Series(user_last_ts),  utc=True, errors="coerce"),
})
df_user["lifetime_days"] = (df_user["last"] - df_user["first"]).dt.total_seconds() / 86400
print("\n--- USER LIFETIME (days) ---")
print(df_user["lifetime_days"].describe(percentiles=[0.5, 0.75, 0.9, 0.95, 0.99]).to_string())

# leakage 후보: event 이름에 'upgrade'/'subscription'/'pricing'/'plan'/'redeem'/'paywall'/'checkout' 들어간 것
print("\n--- LEAKAGE-CANDIDATE EVENTS (이름 기반) ---")
suspicious = []
for ev, c in event_counter.items():
    s = ev.lower() if ev else ""
    if any(k in s for k in ["upgrade", "subscription", "pricing", "plan",
                              "redeem", "paywall", "checkout", "billing",
                              "stripe", "purchase", "payment", "trial",
                              "credit", "offer"]):
        suspicious.append((ev, c))
suspicious.sort(key=lambda x: -x[1])
for ev, c in suspicious[:50]:
    print(f"  {c:>10,}  {ev}")

# 결과를 파일로도 저장 (signal 외에 일부 통계 dump)
import json
summary = {
    "total_rows": total_rows,
    "unique_users": len(user_set),
    "upgraded_users": len(upgrader_set),
    "upgrade_rate_pct": round(len(upgrader_set)/len(user_set)*100, 3),
    "time_min": min_ts,
    "time_max": max_ts,
    "unique_event_types": len(event_counter),
    "top_events": event_counter.most_common(100),
    "leakage_candidates": suspicious,
    "countries_top15": country_counter.most_common(15),
    "subscription_types": dict(subscription_counter),
    "purpose": dict(purpose_counter),
    "role": dict(role_counter),
    "work_type": dict(worktype_counter),
    "source": dict(source_counter),
}
with open("/Users/hunjunsin/Desktop/zerve/eda_summary.json", "w") as f:
    json.dump(summary, f, indent=2, default=str)
print("\nWROTE /Users/hunjunsin/Desktop/zerve/eda_summary.json")
