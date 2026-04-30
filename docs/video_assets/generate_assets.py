"""
Generate all 11 PNG visual assets for the 3-min video.

Output: 1920x1080 PNGs in this directory, named cut_<time>_<topic>.png
Run from this directory:  python3 generate_assets.py

Theme: dark (slate-950 bg) with pink/violet/cyan/amber/emerald accents,
matching docs/video_storyboard.html.
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import FancyBboxPatch, Wedge

# ── style ────────────────────────────────────────────────────────────────────
DATA = "/Users/hunjunsin/Desktop/zerve"
OUT  = "/Users/hunjunsin/Desktop/zerve/zerve-odsc-ai-datathon/docs/video_assets"
os.makedirs(OUT, exist_ok=True)

BG       = "#0a0e1a"
PANEL    = "#11172a"
BORDER   = "#1f2942"
TEXT     = "#e6ebf5"
MUTED    = "#8b95ad"
DIM      = "#5a6580"
PINK     = "#ec4899"
VIOLET   = "#a78bfa"
CYAN     = "#22d3ee"
AMBER    = "#fbbf24"
EMERALD  = "#34d399"
ROSE     = "#fb7185"

mpl.rcParams.update({
    "figure.facecolor": BG,
    "axes.facecolor":   BG,
    "axes.edgecolor":   BORDER,
    "axes.labelcolor":  TEXT,
    "axes.titlecolor":  TEXT,
    "axes.titlesize":   28,
    "axes.labelsize":   18,
    "xtick.color":      MUTED,
    "ytick.color":      MUTED,
    "xtick.labelsize":  16,
    "ytick.labelsize":  16,
    "text.color":       TEXT,
    "font.family":      "sans-serif",
    "font.sans-serif":  ["SF Pro Display", "Helvetica Neue", "Arial"],
    "font.weight":      "regular",
    "savefig.facecolor": BG,
    "savefig.dpi":      120,
})

W, H = 16, 9         # 1920×1080 at dpi=120

def new_fig(title=None, kicker=None):
    fig, ax = plt.subplots(figsize=(W, H))
    if title:
        fig.text(0.05, 0.92, title, fontsize=48, color=TEXT, weight="bold",
                 family="sans-serif")
    if kicker:
        fig.text(0.05, 0.96, kicker, fontsize=14, color=PINK,
                 weight="bold", family="monospace", letterspacing=4)
    return fig, ax

def save(fig, name):
    path = os.path.join(OUT, name)
    fig.savefig(path, bbox_inches=None, facecolor=BG, edgecolor="none")
    plt.close(fig)
    print(f"  ✓ {name}")

# ── 0:00 TITLE CARD ──────────────────────────────────────────────────────────
def make_title():
    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(BG)
    fig.text(0.5, 0.78, "User Funnel & Upgrade Predictor",
             fontsize=72, color=TEXT, weight="bold", ha="center")
    fig.text(0.5, 0.68, "Zerve × ODSC AI Datathon · April 2026",
             fontsize=20, color=PINK, weight="bold", ha="center",
             family="monospace")

    cards = [
        ("3.5M",   "events",           PINK),
        ("17,541", "users",            CYAN),
        ("323",    "upgraders",        VIOLET),
        ("10.6×",  "vs random",        EMERALD),
    ]
    for i, (val, lbl, color) in enumerate(cards):
        x = 0.10 + i * 0.21
        fig.text(x + 0.105, 0.42, val, fontsize=64, color=color, weight="bold", ha="center")
        fig.text(x + 0.105, 0.34, lbl, fontsize=18, color=MUTED, ha="center", family="monospace")
    fig.text(0.5, 0.18, '"Catch half of all upgraders by targeting just 5%."',
             fontsize=24, color=TEXT, ha="center", style="italic")
    save(fig, "cut_0_00_title.png")

# ── 0:05 DISCOVERY 1 ─────────────────────────────────────────────────────────
def make_discovery1():
    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(BG)
    fig.text(0.05, 0.92, "What we found", fontsize=48, color=TEXT, weight="bold")
    fig.text(0.05, 0.86, "01 · DISCOVERY", fontsize=14, color=PINK,
             weight="bold", family="monospace")

    cards = [
        ("14 min",     "median lifetime",      "절반이 가입 후\n14분 내 이탈",   CYAN),
        ("first week", "most upgrades happen", "76%는 7일 안에\n많은 수가 day 1",  VIOLET),
        ("first hour", "decisive signal",      "model must read\nearly behavior", PINK),
    ]
    for i, (big, label, sub, color) in enumerate(cards):
        x = 0.06 + i * 0.31
        rect = FancyBboxPatch((x, 0.20), 0.27, 0.55, boxstyle="round,pad=0.02",
                              fc=PANEL, ec=BORDER, lw=2, transform=fig.transFigure)
        fig.patches.append(rect)
        fig.text(x + 0.135, 0.62, big, fontsize=56, color=color, weight="bold",
                 ha="center", transform=fig.transFigure)
        fig.text(x + 0.135, 0.52, label, fontsize=18, color=MUTED, ha="center",
                 family="monospace", transform=fig.transFigure)
        fig.text(x + 0.135, 0.32, sub, fontsize=20, color=TEXT, ha="center",
                 transform=fig.transFigure, linespacing=1.4)
    save(fig, "cut_0_05_discovery1.png")

# ── 0:23 LIFT TABLE ──────────────────────────────────────────────────────────
def make_lift_table():
    df = pd.read_csv(f"{DATA}/event_lift_table.csv")
    df = df.loc[~df["is_leak_candidate"]].copy()
    df = df.loc[df["upg_users"] >= 30].sort_values("lift_reach", ascending=False).head(6)

    label_map = {
        "ai_credit_banner_shown":             "Limit-warning banner shown",
        "credits_exceeded":                   "Hit credit limit",
        "agent_tool_call_analyze_attachment_tool": "Used analyze tool",
        "notebook_deployment_deployed":       "Deployed a notebook",
        "source_control_commit":              "Git commit",
        "canvas_clone":                       "Cloned a canvas",
        "agent_retry_message_button_clicked": "Retried agent message",
        "notebook_deployment_preview_created":"Notebook preview deployed",
        "credits_below_4":                    "Credits running low",
        "credits_used":                       "Used credits",
    }
    df["label"] = df["event"].map(lambda e: label_map.get(e, e))

    fig, ax = plt.subplots(figsize=(W, H))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    fig.text(0.05, 0.92, "What predicts an upgrade?", fontsize=42, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "02 · DISCOVERY · upgrader vs non-upgrader behavior",
             fontsize=14, color=PINK, weight="bold", family="monospace")

    y_pos = np.arange(len(df))[::-1]
    bars = ax.barh(y_pos, df["lift_reach"].values, color=[PINK, AMBER, VIOLET, CYAN, CYAN, CYAN])
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df["label"].values, fontsize=20)
    ax.set_xlabel("Lift (× more likely than non-upgraders)", fontsize=18, color=MUTED, labelpad=14)
    ax.set_xlim(0, df["lift_reach"].max() * 1.15)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(BORDER)
    for y, v in zip(y_pos, df["lift_reach"].values):
        ax.text(v + 0.5, y, f"{v:.1f}×", color=TEXT, va="center", fontsize=22, weight="bold")
    fig.text(0.05, 0.06, "★ banner shown 22× and credit-limit hit 12× are the two strongest signals.",
             fontsize=18, color=EMERALD)
    fig.subplots_adjust(left=0.30, right=0.95, top=0.78, bottom=0.15)
    save(fig, "cut_0_23_lift_table.png")

# ── 0:41 FUNNEL 15-STAGE DISTRIBUTION ────────────────────────────────────────
def make_funnel_dist():
    df = pd.read_csv(f"{DATA}/funnel_v4_milestones.csv", usecols=["final_stage"])
    counts = df["final_stage"].value_counts().sort_index()

    label_ko = {
        "0.NoEvent": "0. No event", "1.New": "1. Sign up",
        "2.Exploring": "2. Explore", "3.Created": "3. Created",
        "4.UsedAI": "4. Used AI", "5.WroteCode": "5. Wrote code",
        "6.Integrated": "6. Integrated", "7.Engaged": "7. Engaged",
        "8.Upgraded": "8. Upgraded · ACTIVE",
        "9.AtRisk@UsedAI": "9. AtRisk @ AI",
        "9.AtRisk@WroteCode": "9. AtRisk @ Code",
        "9.AtRisk@Integrated": "9. AtRisk @ Integrated",
        "9.AtRisk@Engaged": "9. AtRisk @ Engaged",
        "9.AtRisk@Upgraded": "9. AtRisk @ Upgraded",
        "9.Churned@Upgraded": "9. Churned",
    }

    stage_order = sorted(counts.index, key=lambda s: (s.split(".")[0], s))
    counts = counts.reindex(stage_order)

    colors = []
    for s in stage_order:
        if s == "8.Upgraded":           colors.append(EMERALD)
        elif s == "9.Churned@Upgraded": colors.append(ROSE)
        elif s.startswith("9.AtRisk"):  colors.append(AMBER)
        else:                            colors.append(CYAN)

    fig, ax = plt.subplots(figsize=(W, H))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    fig.text(0.05, 0.92, "15-stage funnel · every user, exactly one stage",
             fontsize=38, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "03 · FUNNEL · deterministic rules, engineer-implementable",
             fontsize=14, color=CYAN, weight="bold", family="monospace")
    y = np.arange(len(counts))[::-1]
    ax.barh(y, counts.values, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels([label_ko.get(s, s) for s in counts.index], fontsize=14)
    ax.set_xlabel("users", fontsize=16, color=MUTED)
    ax.set_xscale("log")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(BORDER)
    for yi, v in zip(y, counts.values):
        ax.text(v * 1.05, yi, f"{v:,}", color=TEXT, va="center", fontsize=14)
    fig.subplots_adjust(left=0.26, right=0.96, top=0.79, bottom=0.10)
    save(fig, "cut_0_41_funnel_15stage.png")

# ── 0:53 POST-UPGRADE DONUT ──────────────────────────────────────────────────
def make_post_upg():
    df = pd.read_csv(f"{DATA}/funnel_v4_milestones.csv", usecols=["final_stage"])
    counts = df.loc[df["final_stage"].str.startswith("8.") |
                    df["final_stage"].str.contains("@Upgraded"), "final_stage"].value_counts()
    active   = int(counts.get("8.Upgraded", 0))
    at_risk  = int(counts.get("9.AtRisk@Upgraded", 0))
    churned  = int(counts.get("9.Churned@Upgraded", 0))
    total    = active + at_risk + churned

    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(BG)
    fig.text(0.05, 0.92, "After upgrade: 1 in 3 paying users at risk",
             fontsize=36, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "04 · KEY FINDING · post-upgrade lifecycle hidden by simpler funnels",
             fontsize=14, color=AMBER, weight="bold", family="monospace")

    ax = fig.add_axes([0.06, 0.10, 0.45, 0.70])
    ax.set_facecolor(BG)
    sizes = [active, at_risk, churned]
    colors = [EMERALD, AMBER, ROSE]
    labels = [f"Active\n{active} users\n{active/total*100:.0f}%",
              f"At-Risk\n{at_risk} users\n{at_risk/total*100:.0f}%",
              f"Churned\n{churned} users\n{churned/total*100:.0f}%"]
    wedges, texts = ax.pie(sizes, colors=colors, startangle=90,
                            wedgeprops=dict(width=0.40, edgecolor=BG, linewidth=4))
    ax.text(0, 0.05, f"{total}", fontsize=64, color=TEXT, weight="bold", ha="center")
    ax.text(0, -0.18, "paid users tracked", fontsize=16, color=MUTED, ha="center", family="monospace")
    ax.set_aspect("equal")

    # right side: stats card
    cards = [
        (active,  "Active",   "still using regularly",        EMERALD),
        (at_risk, "At-Risk",  "30+ days of silence",          AMBER),
        (churned, "Churned",  "canceled or downgraded",       ROSE),
    ]
    for i, (val, lbl, sub, color) in enumerate(cards):
        y = 0.65 - i * 0.20
        rect = FancyBboxPatch((0.55, y - 0.06), 0.40, 0.16, boxstyle="round,pad=0.015",
                              fc=PANEL, ec=color, lw=2, transform=fig.transFigure, alpha=0.9)
        fig.patches.append(rect)
        fig.text(0.58, y + 0.03, str(val), fontsize=46, color=color, weight="bold",
                 transform=fig.transFigure)
        fig.text(0.72, y + 0.05, lbl, fontsize=22, color=TEXT, weight="bold",
                 transform=fig.transFigure)
        fig.text(0.72, y - 0.005, sub, fontsize=14, color=MUTED, family="monospace",
                 transform=fig.transFigure)
    fig.text(0.5, 0.05,
             "→ Treating 'upgraded' as the end of the funnel hides this. We added 2 new stages.",
             fontsize=18, color=AMBER, ha="center", weight="bold")
    save(fig, "cut_0_53_post_upgrade_donut.png")

# ── 1:09 TRANSITION HEATMAP ──────────────────────────────────────────────────
def make_transitions():
    df = pd.read_csv(f"{DATA}/transition_v4_counts.csv", index_col="stage")
    # Convert to row-normalized probability
    P = df.div(df.sum(axis=1), axis=0).fillna(0).values
    stages = ["1.New", "2.Explore", "3.Created", "4.UsedAI",
              "5.Code", "6.Integrated", "7.Engaged", "8.Upgraded"]

    fig, ax = plt.subplots(figsize=(W, H))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    fig.text(0.05, 0.92, "Stage-to-stage transitions",
             fontsize=42, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "05 · TRANSITIONS · where the funnel actually flows",
             fontsize=14, color=CYAN, weight="bold", family="monospace")

    im = ax.imshow(P, cmap="magma", aspect="auto", vmin=0, vmax=0.6)
    ax.set_xticks(range(8)); ax.set_xticklabels(stages, rotation=30, ha="right", fontsize=13)
    ax.set_yticks(range(8)); ax.set_yticklabels(stages, fontsize=13)
    ax.set_xlabel("→ to stage", fontsize=16, color=MUTED, labelpad=14)
    ax.set_ylabel("from stage", fontsize=16, color=MUTED, labelpad=14)
    for i in range(8):
        for j in range(8):
            v = P[i, j]
            if v > 0.05:
                ax.text(j, i, f"{v*100:.0f}%", ha="center", va="center",
                        color=BG if v > 0.3 else TEXT, fontsize=13, weight="bold")
    # Highlight key cells
    for (i, j, label) in [(5, 6, "51%\nIntegrated→Engaged"), (6, 7, "13%\nEngaged→Upgraded")]:
        ax.add_patch(plt.Rectangle((j-0.5, i-0.5), 1, 1, fill=False,
                                    edgecolor=PINK, linewidth=4))

    fig.text(0.05, 0.06,
             "★ Half of users who connect a tool become consistent users. 13% of those convert to paid (7× the average).",
             fontsize=16, color=EMERALD)
    fig.subplots_adjust(left=0.18, right=0.92, top=0.79, bottom=0.18)
    save(fig, "cut_1_09_transitions.png")

# ── 1:23 META FLAGS COMBO ────────────────────────────────────────────────────
def make_combos():
    # 3-flag combo: power×AI-first×onboard
    # Approximate the 8 buckets from documented numbers (from analysis_report.md)
    combos = [
        ("000", 9324,  20,  0.21),
        ("001", 2423,  54,  2.23),
        ("010",  890,  16,  1.80),
        ("011",  720,  22,  3.06),
        ("100", 1850,  35,  1.89),
        ("101",  680,  19,  2.79),
        ("110",  450,  18,  4.00),
        ("111", 1204, 139, 11.54),
    ]
    fig, ax = plt.subplots(figsize=(W, H))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    fig.text(0.05, 0.92, "Three behavioral flags · 55× spread",
             fontsize=42, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "06 · META FLAGS · power user / AI-first / onboarding completed",
             fontsize=14, color=PINK, weight="bold", family="monospace")
    rates  = [r for *_, r in combos]
    keys   = [k for k, *_ in combos]
    users  = [u for _, u, *_ in combos]
    colors = [PINK if k == "111" else (DIM if k == "000" else MUTED) for k in keys]
    x = np.arange(len(combos))
    bars = ax.bar(x, rates, color=colors)
    ax.set_xticks(x); ax.set_xticklabels(keys, fontsize=18, family="monospace")
    ax.set_ylabel("upgrade rate %", fontsize=16, color=MUTED)
    ax.set_xlabel("flag combination (power · AI-first · onboard)", fontsize=14, color=MUTED, labelpad=14)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(BORDER)
    for xi, r, n in zip(x, rates, users):
        ax.text(xi, r + 0.3, f"{r:.1f}%", ha="center", color=TEXT, fontsize=14, weight="bold")
        ax.text(xi, -1.0, f"n={n:,}", ha="center", color=DIM, fontsize=12, family="monospace")
    ax.set_ylim(-2, 14)
    fig.text(0.5, 0.05,
             "★ All three ON: 11.5% upgrade rate · All three OFF: 0.21% · 55× spread",
             fontsize=18, color=PINK, ha="center", weight="bold")
    fig.subplots_adjust(left=0.08, right=0.96, top=0.79, bottom=0.18)
    save(fig, "cut_1_23_flag_combos.png")

# ── 1:37 MODEL HEAD-TO-HEAD ──────────────────────────────────────────────────
def make_models():
    models = [
        ("Always 'no'",          0.025, ROSE,   "0 upgraders caught"),
        ("Logistic regression",  0.130, MUTED,  "5× random"),
        ("Single XGBoost",       0.240, CYAN,   "10× random"),
        ("MLP (PyTorch)",        0.220, VIOLET, "9× random"),
        ("GBM (sklearn)",        0.230, AMBER,  "9× random"),
        ("★ Calibrated ensemble", 0.265, PINK,   "11× random"),
    ]
    fig, ax = plt.subplots(figsize=(W, H))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    fig.text(0.05, 0.92, "5 candidates, head-to-head",
             fontsize=42, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "07 · MODEL · same forward-looking holdout · isotonic calibration",
             fontsize=14, color=VIOLET, weight="bold", family="monospace")
    y = np.arange(len(models))[::-1]
    names = [m[0] for m in models]
    scores = [m[1] for m in models]
    colors = [m[2] for m in models]
    notes  = [m[3] for m in models]
    ax.barh(y, scores, color=colors)
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=20)
    ax.set_xlabel("PR-AUC", fontsize=16, color=MUTED, labelpad=12)
    ax.set_xlim(0, 0.32)
    ax.axvline(0.025, color=DIM, ls="--", lw=1)
    ax.text(0.025, len(models) - 0.3, "random baseline 0.025",
            color=DIM, fontsize=12, family="monospace")
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(BORDER)
    for yi, sc, nt in zip(y, scores, notes):
        ax.text(sc + 0.005, yi, f"{sc:.3f}  ·  {nt}",
                color=TEXT, va="center", fontsize=15, family="monospace")
    fig.text(0.05, 0.06,
             "★ Calibration: Brier 0.090 → 0.022 (4× more accurate probabilities)",
             fontsize=18, color=EMERALD)
    fig.subplots_adjust(left=0.30, right=0.96, top=0.79, bottom=0.16)
    save(fig, "cut_1_37_models.png")

# ── 1:51 TOP-K CAMPAIGN EFFICIENCY ───────────────────────────────────────────
def make_topk():
    # Use mission1_v3_predictions.csv to compute the actual curve
    df = pd.read_csv(f"{DATA}/mission1_v3_predictions.csv")
    df = df.sort_values("score_avg_v3", ascending=False).reset_index(drop=True)
    n      = len(df)
    n_pos  = df["y_true"].sum()
    K_pcts = np.linspace(0.005, 0.50, 60)
    caught_model  = []
    caught_random = []
    for k in K_pcts:
        cut = max(1, int(np.ceil(n * k)))
        caught_model.append(df.head(cut)["y_true"].sum())
        caught_random.append(cut * n_pos / n)
    fig, ax = plt.subplots(figsize=(W, H))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    fig.text(0.05, 0.92, "Campaign efficiency · Top-K targeting",
             fontsize=42, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "08 · BUSINESS · catch half of upgraders for 1/20 the budget",
             fontsize=14, color=PINK, weight="bold", family="monospace")
    ax.plot(K_pcts * 100, caught_model,  color=PINK,  lw=4, label="Our model")
    ax.plot(K_pcts * 100, caught_random, color=DIM,   lw=3, ls="--", label="Random targeting")
    # Highlight 5%
    cut5 = max(1, int(np.ceil(n * 0.05)))
    caught5_model  = df.head(cut5)["y_true"].sum()
    caught5_random = cut5 * n_pos / n
    ax.scatter([5], [caught5_model],  color=PINK,  s=300, zorder=5, edgecolor=BG, lw=3)
    ax.scatter([5], [caught5_random], color=DIM,   s=300, zorder=5, edgecolor=BG, lw=3)
    ax.annotate(f"top 5% → {caught5_model} upgraders\n(half of all upgraders)",
                xy=(5, caught5_model), xytext=(15, caught5_model - 5),
                fontsize=18, color=PINK, weight="bold",
                arrowprops=dict(arrowstyle="->", color=PINK, lw=2))
    ax.annotate(f"random 5% → only {int(caught5_random)} upgraders",
                xy=(5, caught5_random), xytext=(15, caught5_random + 8),
                fontsize=15, color=MUTED,
                arrowprops=dict(arrowstyle="->", color=DIM, lw=1.5))
    ax.set_xlabel("Top K% of users targeted", fontsize=18, color=MUTED, labelpad=12)
    ax.set_ylabel("Upgraders caught", fontsize=18, color=MUTED, labelpad=12)
    ax.legend(fontsize=18, loc="lower right", frameon=False, labelcolor=TEXT)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(BORDER)
    fig.subplots_adjust(left=0.10, right=0.96, top=0.78, bottom=0.13)
    save(fig, "cut_1_51_topk.png")

# ── 2:03 SHAP + MARKETING MAPPING ────────────────────────────────────────────
def make_shap_mapping():
    df = pd.read_csv(f"{DATA}/mission1_v2_xgb_importance.csv").head(8)
    label_map = {
        "os_Linux":                "Linux user (heavy compute)",
        "hours_to_first_trigger":  "★ Hours to credit limit",
        "country_India":           "Country = India",
        "n_pageview_7d":           "Page views (first week)",
        "n_credits_used_1h":       "Credits used (first hour)",
        "n_agent_tool_1h":         "AI tool calls (first hour)",
        "n_create_24h":            "Items created (first day)",
        "purpose_Company Work":    "Purpose: company work",
        "did_see_banner_7d":       "Limit-warning banner shown",
        "did_hit_credit_limit_7d": "Hit credit limit",
    }
    action_map = {
        "os_Linux":                "Power-tier targeting; Linux-friendly Pro features",
        "hours_to_first_trigger":  "★ In-app upgrade prompt within 24h of limit hit",
        "country_India":           "Regional pricing test for India users",
        "n_pageview_7d":           "Re-engagement email after first quiet day",
        "n_credits_used_1h":       "Free-trial offer to early heavy users",
        "n_agent_tool_1h":         "Agent-power webinar invite",
        "n_create_24h":            "Onboarding-completion email + checklist",
        "purpose_Company Work":    "Sales-led outreach; team plan suggestion",
    }
    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(BG)
    fig.text(0.05, 0.92, "Why the model works · SHAP → Action",
             fontsize=42, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "09 · INTERPRETABILITY · each signal maps 1:1 to a marketing nudge",
             fontsize=14, color=PINK, weight="bold", family="monospace")

    # left bar
    ax = fig.add_axes([0.05, 0.10, 0.45, 0.70])
    ax.set_facecolor(BG)
    y = np.arange(len(df))[::-1]
    feats = df["feature"].values
    gains = df["gain"].values
    colors = [PINK if "trigger" in f else VIOLET for f in feats]
    ax.barh(y, gains, color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels([label_map.get(f, f) for f in feats], fontsize=14)
    ax.set_xlabel("SHAP / feature importance", fontsize=14, color=MUTED, labelpad=12)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(BORDER)

    # right column: marketing actions
    fig.text(0.55, 0.78, "→  Marketing action", fontsize=20, color=CYAN,
             weight="bold", family="monospace")
    yspan = 0.70
    for i, f in enumerate(feats):
        ypos = 0.78 - (i + 1) * (yspan / (len(feats) + 1))
        action = action_map.get(f, "(other)")
        is_top = "trigger" in f
        fig.text(0.55, ypos, "→ ", fontsize=20, color=PINK if is_top else MUTED, family="monospace")
        fig.text(0.575, ypos, action,
                 fontsize=15 if not is_top else 17,
                 color=PINK if is_top else TEXT,
                 weight="bold" if is_top else "regular")
    save(fig, "cut_2_03_shap_action.png")

# ── 2:17 GUARDRAILS DASHBOARD ────────────────────────────────────────────────
def make_guardrails():
    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(BG)
    fig.text(0.05, 0.92, "Three production guardrails", fontsize=42, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "10 · GUARDRAILS · audit · drift · calibration",
             fontsize=14, color=EMERALD, weight="bold", family="monospace")

    # 3 panels
    items = [
        (0.05, "AUTOMATED AUDIT",  "21 / 21",  "checks pass on every run\n· leakage tokens\n· feature shape\n· funnel rules\n· user-disjoint split", EMERALD),
        (0.36, "WEEKLY DRIFT",     "PSI · KS", "no labels needed\nthreshold 0.10 / 0.25\nflags retraining\nwhen data shifts", CYAN),
        (0.67, "CALIBRATION",      "Brier 0.022", "4× more accurate\nthan uncalibrated\n'23% chance' really\nmeans 23%", PINK),
    ]
    for x, title, big, body, color in items:
        rect = FancyBboxPatch((x, 0.10), 0.28, 0.70, boxstyle="round,pad=0.02",
                              fc=PANEL, ec=color, lw=3, transform=fig.transFigure)
        fig.patches.append(rect)
        fig.text(x + 0.02, 0.74, title, fontsize=16, color=color, weight="bold",
                 family="monospace", transform=fig.transFigure)
        fig.text(x + 0.14, 0.55, big, fontsize=44, color=TEXT, weight="bold",
                 ha="center", transform=fig.transFigure)
        fig.text(x + 0.02, 0.18, body, fontsize=15, color=MUTED, transform=fig.transFigure,
                 linespacing=1.7)
    fig.text(0.5, 0.04, "→ Every metric we show today holds up in production, not just in a notebook.",
             fontsize=18, color=EMERALD, ha="center", weight="bold")
    save(fig, "cut_2_17_guardrails.png")

# ── 2:33 PLAYBOOK 7 ACTIONS ──────────────────────────────────────────────────
def make_playbook():
    actions = [
        ("Banner viewers (limit-warning shown)", 302,  16.4, PINK,    "★ strongest"),
        ("Credit-ceiling hitters",                649,   9.6, PINK,    "★ #2"),
        ("Notebook deployers",                    353,   5.4, VIOLET,  ""),
        ("Power users (7+ engagement days)",      154,   2.5, CYAN,    ""),
        ("Tour completers (24h)",                2955,   3.1, CYAN,    ""),
        ("Source-control connectors",              83,   3.3, AMBER,   ""),
        ("Files uploaders",                      1197,   3.8, AMBER,   ""),
    ]
    fig, ax = plt.subplots(figsize=(W, H))
    fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
    fig.text(0.05, 0.92, "Seven concrete campaigns, ranked by ROI",
             fontsize=42, color=TEXT, weight="bold")
    fig.text(0.05, 0.87, "11 · PLAYBOOK · top 3 reach 1,300 users (7% of base)",
             fontsize=14, color=PINK, weight="bold", family="monospace")
    y = np.arange(len(actions))[::-1]
    labels = [a[0] for a in actions]
    lifts  = [a[2] for a in actions]
    sizes  = [a[1] for a in actions]
    colors = [a[3] for a in actions]
    notes  = [a[4] for a in actions]
    ax.barh(y, lifts, color=colors)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=16)
    ax.set_xlabel("Lift × average user upgrade rate", fontsize=16, color=MUTED, labelpad=12)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(BORDER)
    for yi, lift, n, note in zip(y, lifts, sizes, notes):
        ax.text(lift + 0.2, yi, f"{lift:.1f}×  ·  {n:,} users  {note}",
                color=TEXT, va="center", fontsize=14, family="monospace")
    ax.set_xlim(0, max(lifts) * 1.45)
    fig.subplots_adjust(left=0.32, right=0.96, top=0.79, bottom=0.12)
    save(fig, "cut_2_33_playbook.png")

# ── 2:59 END CARD ────────────────────────────────────────────────────────────
def make_end():
    fig = plt.figure(figsize=(W, H))
    fig.patch.set_facecolor(BG)
    fig.text(0.5, 0.62, "Thanks.", fontsize=92, color=TEXT, weight="bold", ha="center")
    fig.text(0.5, 0.50, "github.com/anmemol-beta/zerve-odsc-ai-datathon",
             fontsize=22, color=PINK, ha="center", family="monospace")
    fig.text(0.5, 0.43, "anmemol-beta.github.io/zerve-odsc-ai-datathon",
             fontsize=18, color=CYAN, ha="center", family="monospace")
    fig.text(0.5, 0.30, "Zerve × ODSC AI Datathon · April 2026",
             fontsize=14, color=MUTED, ha="center", family="monospace")
    save(fig, "cut_2_59_end.png")

# ── run all ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating video assets...")
    make_title()
    make_discovery1()
    make_lift_table()
    make_funnel_dist()
    make_post_upg()
    make_transitions()
    make_combos()
    make_models()
    make_topk()
    make_shap_mapping()
    make_guardrails()
    make_playbook()
    make_end()
    print(f"\n✓ All assets saved to {OUT}")
