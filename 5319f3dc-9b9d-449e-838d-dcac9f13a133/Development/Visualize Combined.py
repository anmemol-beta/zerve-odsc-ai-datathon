

# Fan-in block. Two parents:
#   - "Daily Activity"     → provides `daily`
#   - "User Demographics"  → provides `demographics`
# Renders a 2x2 dashboard combining both.

import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 2, figsize=(16, 9))

# Top-left: DAU
axes[0, 0].plot(daily["date"], daily["dau"], color="#4c72b0", linewidth=1.2)
axes[0, 0].set_title("Daily active users")
axes[0, 0].set_ylabel("DAU")
axes[0, 0].grid(True, alpha=0.3)

# Top-right: event volume
axes[0, 1].plot(daily["date"], daily["n_events"], color="#dd8452", linewidth=1.2)
axes[0, 1].set_title("Daily event volume")
axes[0, 1].set_ylabel("events / day")
axes[0, 1].grid(True, alpha=0.3)

# Bottom-left: browsers
b = demographics["browser"]
axes[1, 0].barh(range(len(b)), b.values, color="#55a868")
axes[1, 0].set_yticks(range(len(b)))
axes[1, 0].set_yticklabels(b.index)
axes[1, 0].invert_yaxis()
axes[1, 0].set_title("Top browsers (event count)")

# Bottom-right: countries
c = demographics["country"]
axes[1, 1].barh(range(len(c)), c.values, color="#c44e52")
axes[1, 1].set_yticks(range(len(c)))
axes[1, 1].set_yticklabels(c.index)
axes[1, 1].invert_yaxis()
axes[1, 1].set_title("Top countries (event count)")

for ax in axes[0]:
    for label in ax.get_xticklabels():
        label.set_rotation(30)
        label.set_ha("right")

plt.tight_layout()
plt.show()
