"""Prompt templates for the K2 strategist.

Kept in a separate module so prompt tweaks don't require running the data
extraction again. `build_user_prompt` formats segment stats into a stable
text block; `STRATEGIST_SYSTEM` carries the role + JSON schema rules.
"""
from __future__ import annotations
import json


STRATEGIST_SYSTEM = """\
You are a senior growth strategist at Zerve, a cloud AI notebook platform
(competitors: Google Colab, Hex, Deepnote). You help Zerve's product and
marketing teams turn user-segment data into specific, ROI-justified
campaigns.

Zerve's monetization: free tier with credit-based usage. Users upgrade to
the paid plan when they hit credit limits, deploy notebooks externally,
or use the Coder Agent intensively. Most upgrades happen within 7 days
of signup; ~36% of paying users go inactive within 60 days.

You will be given ONE user segment along with its statistics, behavioral
features, demographics, and relevant business-playbook context. Output
exactly 3 prioritized marketing actions ranked by expected ROI, plus 3
risks.

Be concrete: name the channel, write actual ad/email copy (not a
description of what to write), give a target filter that an analyst
could turn into SQL, and tie every claim to the data the user provided
or the playbook excerpt.

Return ONLY valid JSON matching this schema. No prose, no markdown
fences, no commentary:

{
  "segment_id": str,
  "summary": str,
  "actions": [
    {
      "rank": 1 | 2 | 3,
      "title": str,
      "channel": "email" | "in_app_modal" | "sales_call" |
                 "push_notification" | "ad_retargeting" |
                 "lifecycle_drip",
      "message_en": str,
      "message_ko": str,
      "target_filter": str,
      "expected_uplift_pp": float,
      "estimated_cost_per_user_usd": float,
      "estimated_roi_multiple": float,
      "rationale": str,
      "playbook_alignment": str
    },
    ... 2 more
  ],
  "risks": [str, str, str]
}
"""


def _fmt_num(x):
    if isinstance(x, float):
        if abs(x) < 0.01:
            return f"{x:.4f}"
        return f"{x:.2f}"
    return str(x)


def build_user_prompt(seg: dict, playbook_excerpt: str) -> str:
    """Format a segment_summary dict into the LLM user prompt.

    The dict shape comes from build_strategies.extract_segment_data.
    """
    lines = []
    L = lines.append
    L(f"SEGMENT_ID:   {seg['segment_id']}")
    L(f"LABEL:        {seg['label']}")
    L(f"SIZE:         {seg['size']:,} users  ({seg['pct_of_total']:.1f}% of all)")
    L("")
    L(f"OBSERVED UPGRADE RATE (within window): {seg['observed_rate']:.2%}")
    L(f"BASELINE (all users):                  {seg['baseline_rate']:.2%}")
    L(f"LIFT vs baseline:                      {seg['baseline_lift']:.2f}x")
    L("")
    L("ACTIVITY SUMMARY (medians):")
    L(f"  - n_events:           {seg['median_n_events']:,}")
    L(f"  - distinct_days:      {seg['median_distinct_days']}")
    L(f"  - days_since_last:    {seg['median_days_since_last']:.1f}")
    L(f"  - session_minutes:    {seg['median_session_min']:.1f}")
    L("")
    L("TOP DISTINGUISHING BEHAVIORS (vs baseline, sorted by reach lift):")
    for row in seg["top_behavioral"]:
        L(f"  - {row['feature']}: segment median={_fmt_num(row['seg_median'])}, "
          f"baseline median={_fmt_num(row['base_median'])}, "
          f"reach={row['seg_reach']:.1%} vs baseline {row['base_reach']:.1%} "
          f"(lift {row['reach_lift']:.1f}x)")
    L("")
    L("DEMOGRAPHIC PROFILE (top values):")
    for k, v in seg["demographics"].items():
        L(f"  - {k}: {v}")
    L("")
    L("METADATA FLAG MIX:")
    for k, v in seg["metadata"].items():
        L(f"  - {k}: {v}")
    L("")
    L("PREDICTION SCORE (v3 calibrated ensemble, on this segment):")
    L(f"  - median: {seg['score']['median']:.3f}")
    L(f"  - p90:    {seg['score']['p90']:.3f}")
    L(f"  - share above top-5%-cutoff: {seg['score']['pct_top5']:.1%}")
    L("")
    L("FUNNEL CONTEXT:")
    L(f"  This segment sits at \"{seg['label']}\" in our 15-stage funnel.")
    L(f"  Stage rank: {seg['stage_rank']}/15. Adjacent stages: {seg['adjacent']}")
    L("")
    L("BUSINESS PLAYBOOK EXCERPT (use this to ground recommendations):")
    L("---")
    L(playbook_excerpt)
    L("---")
    L("")
    L("TASK:")
    L("Recommend 3 prioritized marketing actions for this segment, plus")
    L("3 risks. Output the JSON object only, matching the schema in your")
    L("instructions exactly.")
    return "\n".join(lines)


# Quick sanity check on import
if __name__ == "__main__":
    fake = {
        "segment_id": "atrisk_engaged",
        "label": "9.AtRisk@Engaged",
        "size": 457,
        "pct_of_total": 2.6,
        "observed_rate": 0.0,
        "baseline_rate": 0.0184,
        "baseline_lift": 0.0,
        "median_n_events": 633,
        "median_distinct_days": 6,
        "median_days_since_last": 57.6,
        "median_session_min": 45.0,
        "top_behavioral": [
            {"feature": "n_agent_tool_24h", "seg_median": 30, "base_median": 0,
             "seg_reach": 0.85, "base_reach": 0.12, "reach_lift": 7.1},
        ],
        "demographics": {"purpose": "Personal Projects (62%)"},
        "metadata": {"agent_first": "78%"},
        "score": {"median": 0.05, "p90": 0.21, "pct_top5": 0.12},
        "stage_rank": 12,
        "adjacent": "7.Engaged → 9.AtRisk@Engaged → (no upgrade path)",
    }
    print(build_user_prompt(fake, "(playbook excerpt placeholder)"))
