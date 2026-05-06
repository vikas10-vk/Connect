"""
Component Selector
------------------
Maps AI tool execution results to Generative UI component specifications.
The frontend MessageRenderer reads these specs and renders the correct
Tailwind component inline inside the chat thread.

Each component spec is:
{
    "type": "ComponentName",   # matches frontend registry key
    "data": { ... },           # raw data from tool result
    "props": { ... }           # additional render hints (urgency, variant, etc.)
}

No extra AI call needed — this is deterministic rule-based selection.
The AI already knows which tool it called; we just map the result.
"""

from typing import Optional


# ── Component type constants ─────────────────────────────────────────────────
TRADIE_GRID          = "TradieeGrid"
JOB_CONFIRM_CARD     = "JobConfirmCard"
JOB_LIST_CARD        = "JobListCard"
QUOTE_COMPARISON     = "QuoteComparison"
HOME_HEALTH_CHART    = "HomeHealthChart"
PHOTO_ANALYSIS_CARD  = "PhotoAnalysisCard"
TRADIE_PASS_CARD     = "TradiePassCard"
EARNINGS_SUMMARY     = "EarningsSummary"
LEAD_GRID            = "LeadGrid"
ASSET_ADDED_CARD     = "AssetAddedCard"
SWMS_PREVIEW_CARD    = "SWMSPreviewCard"
LICENCE_INFO_CARD    = "LicenceInfoCard"
CATEGORY_GRID        = "CategoryGrid"


def select_component(
    tool_name: str,
    tool_result: dict,
    vision_analysis: Optional[dict] = None,
) -> Optional[dict]:
    """
    Given a tool name and its result, return a UI component spec or None.

    Args:
        tool_name: The name of the tool that was called
        tool_result: The dict returned by execute_tool()
        vision_analysis: Optional vision analysis dict if photo was uploaded

    Returns:
        Component spec dict or None if no visual component needed
    """

    # Skip if tool returned an error
    if tool_result.get("error"):
        return None

    # ── Homeowner tools ───────────────────────────────────────────────────────

    if tool_name == "search_tradies":
        tradies = tool_result.get("tradies", [])
        if not tradies:
            return None
        return {
            "type": TRADIE_GRID,
            "data": {"tradies": tradies},
            "props": {
                "variant":     "compact",
                "show_map":    True,
                "show_action": True,   # shows "Get Quote" button per card
            },
        }

    if tool_name == "post_job":
        if not tool_result.get("success"):
            return None
        return {
            "type": JOB_CONFIRM_CARD,
            "data": {
                "job_id":   tool_result.get("job_id"),
                "title":    tool_result.get("title"),
                "category": tool_result.get("category"),
                "suburb":   tool_result.get("suburb"),
                "state":    tool_result.get("state"),
                "urgency":  tool_result.get("urgency"),
                "status":   tool_result.get("status"),
            },
            "props": {
                "show_confetti": True,
                "show_next_steps": True,
            },
        }

    if tool_name == "get_my_jobs":
        jobs = tool_result.get("jobs", [])
        if not jobs:
            return None
        return {
            "type": JOB_LIST_CARD,
            "data": {"jobs": jobs},
            "props": {
                "show_urgency_badge": True,
                "clickable":         True,
            },
        }

    if tool_name == "get_job_quotes":
        quotes = tool_result.get("quotes", [])
        if not quotes:
            return None
        return {
            "type": QUOTE_COMPARISON,
            "data": {"quotes": quotes},
            "props": {
                "highlight_best": True,
                "show_hire_btn":  True,
            },
        }

    if tool_name == "get_home_assets":
        assets = tool_result.get("assets", [])
        if not assets:
            return None
        return {
            "type": HOME_HEALTH_CHART,
            "data": {"assets": assets},
            "props": {
                "show_maintenance_schedule": True,
                "show_health_bar":           True,
            },
        }

    if tool_name == "add_home_asset":
        if not tool_result.get("success"):
            return None
        return {
            "type": ASSET_ADDED_CARD,
            "data": {
                "asset_type": tool_result.get("asset_type"),
                "brand_name": tool_result.get("brand_name"),
            },
            "props": {"animate_in": True},
        }

    if tool_name == "check_licence_requirements":
        return {
            "type": LICENCE_INFO_CARD,
            "data": tool_result,
            "props": {"show_verify_tip": True},
        }

    if tool_name == "get_categories":
        cats = tool_result.get("categories", [])
        if not cats:
            return None
        return {
            "type": CATEGORY_GRID,
            "data": {"categories": cats},
            "props": {"variant": "chips"},
        }

    # ── Tradie tools ──────────────────────────────────────────────────────────

    if tool_name == "get_my_leads":
        leads = tool_result.get("leads", [])
        if not leads:
            return None
        return {
            "type": LEAD_GRID,
            "data": {"leads": leads},
            "props": {
                "show_urgency_badge":   True,
                "show_intent_badge":    True,
                "show_quote_action":    True,
            },
        }

    if tool_name == "get_earnings_summary":
        return {
            "type": EARNINGS_SUMMARY,
            "data": tool_result,
            "props": {
                "show_gst_breakdown": True,
                "show_chart":         True,
            },
        }

    if tool_name == "get_tradie_pass":
        return {
            "type": TRADIE_PASS_CARD,
            "data": tool_result,
            "props": {
                "show_checklist":    True,
                "show_improve_tips": True,
            },
        }

    if tool_name == "generate_swms":
        if not tool_result.get("success"):
            return None
        return {
            "type": SWMS_PREVIEW_CARD,
            "data": {
                "doc_id":  tool_result.get("doc_id"),
                "preview": tool_result.get("preview"),
                "message": tool_result.get("message"),
            },
            "props": {"show_download_btn": True},
        }

    return None


def select_vision_component(vision_analysis: dict) -> Optional[dict]:
    """
    When a photo is uploaded and analysed, always render a PhotoAnalysisCard
    regardless of which tool (if any) was also called.
    This takes priority and appears first in the message thread.
    """
    if vision_analysis.get("error") or not vision_analysis.get("problem_detected"):
        return None

    return {
        "type": PHOTO_ANALYSIS_CARD,
        "data": {
            "problem_title":       vision_analysis.get("problem_title"),
            "problem_description": vision_analysis.get("problem_description"),
            "trade_required":      vision_analysis.get("trade_required"),
            "urgency":             vision_analysis.get("urgency"),
            "urgency_reason":      vision_analysis.get("urgency_reason"),
            "estimated_job_type":  vision_analysis.get("estimated_job_type"),
            "visible_damage":      vision_analysis.get("visible_damage", []),
            "safety_risk":         vision_analysis.get("safety_risk", False),
            "safety_note":         vision_analysis.get("safety_note"),
            "confidence":          vision_analysis.get("confidence"),
        },
        "props": {
            "show_post_job_btn":   True,   # "Post this as a job" quick action
            "show_find_tradie_btn": True,
            "urgency_banner":      vision_analysis.get("urgency") in ("emergency", "asap"),
        },
    }