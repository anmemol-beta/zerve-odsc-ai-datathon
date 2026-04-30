# pyright: reportRedeclaration=false, reportGeneralTypeIssues=false, reportPossiblyUnboundVariable=false


# 4-panel cohort / time-travel dashboard, mirroring the web app's #06 section
# directly onto the Zerve canvas node.
#   Top-left  : cumulative growth lines (users / active / engaged / upgraded / at_risk)
#   Top-right : daily activity volume sparkline + upgrade-event markers
#   Bot-left  : cohort-week upgrade rate vs cumulative all-time
#   Bot-right : day-of-week × hour-of-day event heatmap
#
# Inherits `events`, `user_features`, `is_active`, `is_created`, `is_ai`,
# `is_engaged`, `is_at_risk` from "Funnel Stages".

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ── Daily timeline
day = events["timestamp"].dt.normalize()
events_per_day = events.groupby(day).size().sort_index()
upgrade_per_day = events.loc[events["event"] == "subscription_upgraded"].groupby(day).size().sort_index()

# Per-user first event day → cohort timeline
user_first = events.groupby("person_id", observed=True)["timestamp"].min()
user_first_day = user_first.dt.normalize()
new_users_per_day = user_first_day.value_counts().sort_index()

# Cumulative reach per day. We approximate "as-of T" reach by counting
# users whose first_event ≤ T who eventually reached the stage.
flags = pd.DataFrame({
    "first_day": user_first_day.reindex(user_features.index).values,
    "active":    is_active.values,
    "engaged":   is_engaged.values,
    "at_risk":   is_at_risk.values,
    "upgraded":  user_features["upgraded"].values,
}, index=user_features.index)

daily_new = flags.groupby("first_day").agg(
    n=("active", "size"),
    n_active=("active", "sum"),
    n_engaged=("engaged", "sum"),
    n_at_risk=("at_risk", "sum"),
    n_upgraded=("upgraded", "sum"),
).sort_index()
daily_cum = daily_new.cumsum()

# ── Cohort weekly upgrade rate
weeks = user_first.dt.to_period("W").dt.start_time
cohort_df = pd.DataFrame({
    "week":     weeks.reindex(user_features.index).values,
    "upgraded": user_features["upgraded"].values,
})
cohort_grp = cohort_df.groupby("week", observed=True).agg(
    n=("upgraded", "size"),
    n_up=("upgraded", "sum"),
).sort_index()
cohort_grp["rate"] = 100 * cohort_grp["n_up"] / cohort_grp["n"].clip(lower=1)
cohort_grp["cum_n"] = cohort_grp["n"].cumsum()
cohort_grp["cum_up"] = cohort_grp["n_up"].cumsum()
cohort_grp["cum_rate"] = 100 * cohort_grp["cum_up"] / cohort_grp["cum_n"].clip(lower=1)

# ── Day-of-week × hour-of-day heatmap
hod = events["timestamp"].dt.hour
dow = events["timestamp"].dt.dayofweek
heat = pd.crosstab(dow, hod).reindex(index=range(7), columns=range(24), fill_value=0)
DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ── Plot
fig, axes = plt.subplots(2, 2, figsize=(15, 10))

# Top-left: cumulative growth lines
ax = axes[0, 0]
ax.plot(daily_cum.index, daily_cum["n"],          label=f"users (final {int(daily_cum['n'].iloc[-1]):,})",         color="#94a3b8", linewidth=1.6)
ax.plot(daily_cum.index, daily_cum["n_active"],   label=f"active ({int(daily_cum['n_active'].iloc[-1]):,})",       color="#3b82f6", linewidth=1.4)
ax.plot(daily_cum.index, daily_cum["n_engaged"],  label=f"engaged ({int(daily_cum['n_engaged'].iloc[-1]):,})",     color="#84cc16", linewidth=1.4)
ax.plot(daily_cum.index, daily_cum["n_at_risk"],  label=f"at-risk ({int(daily_cum['n_at_risk'].iloc[-1]):,})",     color="#f59e0b", linewidth=1.4)
ax.plot(daily_cum.index, daily_cum["n_upgraded"], label=f"upgraded ({int(daily_cum['n_upgraded'].iloc[-1]):,})",   color="#ec4899", linewidth=2.0)
ax.set_title("Cumulative growth over time (as-of)")
ax.set_xlabel("date"); ax.set_ylabel("cumulative users")
ax.legend(loc="upper left", fontsize=8)
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

# Top-right: daily events sparkline + upgrade markers
ax = axes[0, 1]
ax.fill_between(events_per_day.index, events_per_day.values, color="#06b6d4", alpha=0.4, linewidth=0)
ax.plot(events_per_day.index, events_per_day.values, color="#06b6d4", linewidth=1.2)
# Upgrade event dots
if len(upgrade_per_day) > 0:
    ax.scatter(upgrade_per_day.index, [events_per_day.max() * 0.96] * len(upgrade_per_day),
               s=upgrade_per_day.values * 4, color="#ec4899", alpha=0.7, edgecolor="white", linewidth=0.4,
               label=f"upgrade-event days (n={len(upgrade_per_day)})")
ax.set_title("Daily activity volume + upgrade events")
ax.set_xlabel("date"); ax.set_ylabel("events / day")
ax.legend(loc="upper left", fontsize=8)
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

# Bottom-left: cohort upgrade rate vs cumulative
ax = axes[1, 0]
ax.bar(cohort_grp.index, cohort_grp["rate"], width=5, color="#ec4899", alpha=0.55, label="this-cohort upgrade %")
ax.plot(cohort_grp.index, cohort_grp["cum_rate"], color="#94a3b8", linewidth=1.8, label="cumulative all-time %")
ax.set_title("Weekly cohort upgrade rate vs cumulative baseline")
ax.set_xlabel("cohort signup week"); ax.set_ylabel("% of cohort upgraded")
ax.legend(loc="upper left", fontsize=8)
ax.grid(True, alpha=0.3)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))

# Bottom-right: hourly heatmap
ax = axes[1, 1]
im = ax.imshow(heat.values, aspect="auto", cmap="viridis", origin="lower")
ax.set_yticks(range(7))
ax.set_yticklabels(DOW_NAMES)
ax.set_xticks(range(0, 24, 3))
ax.set_xticklabels([f"{h:02d}" for h in range(0, 24, 3)])
ax.set_xlabel("hour of day (UTC)")
ax.set_title("Activity heatmap — events by day-of-week × hour")
fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="events")

plt.tight_layout()
plt.show()


print(f"  cohorts (weeks)   : {len(cohort_grp)}")
print(f"  cohort rate range : {cohort_grp['rate'].min():.2f}% → {cohort_grp['rate'].max():.2f}%")
print(f"  latest cohort rate: {cohort_grp['rate'].iloc[-1]:.2f}%   cumulative {cohort_grp['cum_rate'].iloc[-1]:.2f}%")
print(f"  peak hour (UTC)   : {heat.values.sum(axis=0).argmax():02d}:00")
print(f"  peak weekday      : {DOW_NAMES[heat.values.sum(axis=1).argmax()]}")
