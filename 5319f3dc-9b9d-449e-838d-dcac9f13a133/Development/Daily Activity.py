

# Branches off "EDA Summary". Uses the slim `events` frame to build a daily
# series (DAU + event volume) — light enough for Lambda.

daily = (
    events.assign(date=events["timestamp"].dt.tz_convert("UTC").dt.date)
          .groupby("date", as_index=False)
          .agg(dau=("person_id", "nunique"),
               n_events=("event", "size"))
)
daily["date"] = pd.to_datetime(daily["date"])
daily = daily.sort_values("date").reset_index(drop=True)

print(f"days covered            : {len(daily)}")
print(f"DAU mean / median / max : {daily['dau'].mean():.0f} / {daily['dau'].median():.0f} / {int(daily['dau'].max())}")
print(f"events/day median / max : {int(daily['n_events'].median()):,} / {int(daily['n_events'].max()):,}")
print()
print("first 5 days:")
print(daily.head().to_string(index=False))
print()
print("last 5 days:")
print(daily.tail().to_string(index=False))
