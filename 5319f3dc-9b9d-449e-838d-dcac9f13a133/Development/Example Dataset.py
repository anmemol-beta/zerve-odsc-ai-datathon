

# Slim-load the event log: only the 3 columns downstream blocks use, parsed
# at read time. ~0.9s on local laptop, ~190 MB in memory. Lambda-friendly.

events = pd.read_csv(
    "zerve_events.csv",
    usecols=["person_id", "timestamp", "event"],
    engine="pyarrow",
)
events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True, format="ISO8601")
events["event"] = events["event"].astype("category")
events.dropna(subset=["person_id", "timestamp", "event"], inplace=True)
events.reset_index(drop=True, inplace=True)

print(f"rows         : {len(events):,}")
print(f"memory       : {events.memory_usage(deep=True).sum() / 1e6:.0f} MB")
print(f"unique users : {events['person_id'].nunique():,}")
print(f"event types  : {events['event'].nunique()}")
print(f"time range   : {events['timestamp'].min()}  ->  {events['timestamp'].max()}")
