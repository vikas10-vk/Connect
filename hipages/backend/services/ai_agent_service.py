"""
AI Agent Service
----------------
Core agentic loop. Handles:
  - Vision analysis (photo uploads -> Groq vision model)
  - Tool orchestration (Groq llama-3.3-70b-versatile)
  - Generative UI component selection
  - Memory context injection

Returns a structured dict:
{
    "response":      str,
    "ui_component":  dict | None,
    "vision":        dict | None,
    "actions":       list,
    "error":         bool,
}
"""

import os
import json
import httpx
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.user import User
from models.job import Job
from models.lead import Lead
from models.quote import Quote
from models.tradie_profile import TradieProfile
from models.home_asset import HomeAsset
from models.category import Category
from models.tradie_category import TradieCategory

from services.compliance_service import get_licence_requirements
from services.earnings_service import get_monthly_summary
from services.swms_service import generate_swms_with_ai
from services.vision_service import analyse_photo, build_vision_context
from services.component_selector import select_component, select_vision_component
from services.category_resolver import resolve_trade_category
from services.memory_service import get_user_context
from services.ai_tools import HOMEOWNER_TOOLS, TRADIE_TOOLS, SHARED_TOOLS

import uuid
from dotenv import load_dotenv

load_dotenv(
    dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
    override=True,
)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"


def get_system_prompt(user: User, profile: Optional[TradieProfile] = None, memory_context: str = "") -> str:
    name = user.full_name.split(" ")[0]
    memory_block = f"\n\n{memory_context}" if memory_context else ""

    if user.role == "homeowner":
        return f"""You are a friendly AI assistant for ProConnect, Australia's most trusted trades marketplace.
You are talking to {name}, a homeowner.

Your job is to help them:
- Post jobs to find tradies
- Check on their active jobs and quotes
- Browse and find tradies near them
- Track their home appliances and maintenance
- Understand what licences a tradie should have

IMPORTANT RULES:
- Always be conversational and friendly
- Ask for missing information naturally — do not list all questions at once
- Before posting a job or any write action, ALWAYS confirm the details with the user first
- If you are unsure about a location or category, ask
- Keep responses concise — 2-3 sentences maximum unless showing data
- You are Australian — use Australian English (e.g. "tradies" not "contractors")
- Never mention prices or suggest what something should cost
- When a photo has been analysed, acknowledge what you see and offer to post a job immediately

Current user: {name} (homeowner){memory_block}"""

    else:
        business = profile.business_name if profile else name
        return f"""You are a friendly AI assistant for ProConnect, Australia's most trusted trades marketplace.
You are talking to {name} from {business}, a verified tradie on the platform.

Your job is to help them:
- Find and respond to job leads
- Check their compliance and TradiePASS score
- Generate SWMS safety documents
- Track their earnings and GST
- Manage their job preferences

IMPORTANT RULES:
- Always be conversational and professional
- Keep responses concise — tradies are busy
- Before sending a quote, ALWAYS confirm the amount and message
- You are Australian — use Australian English

Current user: {name} — {business} (tradie){memory_block}"""


async def execute_tool(tool_name: str, tool_input: dict, user: User, db: AsyncSession) -> dict:
    """Execute a tool call and return the result."""

    if tool_name == "get_categories":
        result = await db.execute(select(Category).limit(20))
        cats = result.scalars().all()
        return {"categories": [{"id": c.id, "name": c.name, "slug": c.slug} for c in cats]}

    if tool_name == "check_licence_requirements":
        return get_licence_requirements(
            state=tool_input.get("state", "NSW"),
            category=tool_input.get("category", ""),
            job_type=tool_input.get("job_type", "residential"),
        )

    if tool_name == "post_job":
        slug = tool_input.get("category_slug", "")
        cat = await resolve_trade_category(
            db,
            " ".join(
                part for part in [
                    tool_input.get("title", ""),
                    tool_input.get("description", ""),
                    slug,
                ] if part
            ),
        )
        if not cat:
            cat = await resolve_trade_category(db, slug)
        if not cat:
            return {"error": f"Service '{slug}' not found."}

        job = Job(
            id=str(uuid.uuid4()),
            homeowner_id=user.id,
            category_id=cat.id,
            title=tool_input.get("title", ""),
            description=tool_input.get("description", ""),
            suburb=tool_input.get("suburb", ""),
            state=tool_input.get("state", ""),
            postcode=tool_input.get("postcode", ""),
            urgency=tool_input.get("urgency", "flexible"),
            job_type=tool_input.get("job_type", "residential"),
            service_type=tool_input.get("service_type", "other"),
            job_stage=tool_input.get("job_stage", "ready_to_hire"),
            intent_level=tool_input.get("intent_level", "high"),
            contact_name=tool_input.get("contact_name", user.full_name),
            contact_phone=tool_input.get("contact_phone", ""),
            status="open",
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        return {
            "success": True,
            "job_id": job.id,
            "title": job.title,
            "category": cat.name,
            "suburb": job.suburb,
            "state": job.state,
            "urgency": job.urgency,
            "status": "open",
        }

    if tool_name == "get_my_jobs":
        query = select(Job).where(Job.homeowner_id == user.id)
        if tool_input.get("status"):
            query = query.where(Job.status == tool_input["status"])
        query = query.order_by(Job.created_at.desc()).limit(10)
        result = await db.execute(query)
        jobs = result.scalars().all()
        return {
            "jobs": [
                {"id": j.id, "title": j.title, "suburb": j.suburb, "state": j.state,
                 "status": j.status, "urgency": j.urgency, "created": j.created_at.strftime("%d %b %Y")}
                for j in jobs
            ]
        }

    if tool_name == "get_job_quotes":
        result = await db.execute(select(Quote).where(Quote.job_id == tool_input.get("job_id", "")))
        quotes = result.scalars().all()
        return {
            "quotes": [
                {"id": q.id, "amount": q.amount, "message": q.message, "status": q.status}
                for q in quotes
            ]
        }

    if tool_name == "search_tradies":
        query = select(TradieProfile).where(TradieProfile.is_available == True)
        if tool_input.get("category_slug"):
            cat_r = await db.execute(select(Category).where(Category.slug == tool_input["category_slug"]))
            cat = cat_r.scalar_one_or_none()
            if cat:
                query = query.join(TradieCategory, TradieCategory.tradie_id == TradieProfile.id).where(TradieCategory.category_id == cat.id)
        if tool_input.get("suburb"):
            query = query.where(TradieProfile.suburb.ilike(f"%{tool_input['suburb']}%"))
        result = await db.execute(query.limit(5))
        tradies = result.scalars().all()
        return {
            "tradies": [
                {"id": t.id, "business_name": t.business_name, "suburb": t.suburb,
                 "state": t.state, "radius_km": t.radius_km, "is_available": t.is_available}
                for t in tradies
            ]
        }

    if tool_name == "get_home_assets":
        result = await db.execute(select(HomeAsset).where(HomeAsset.homeowner_id == user.id))
        assets = result.scalars().all()
        return {
            "assets": [
                {"id": a.id, "asset_type": a.asset_type, "brand_name": a.brand_name,
                 "installed": str(a.installation_date), "health": _asset_health(a)}
                for a in assets
            ]
        }

    if tool_name == "add_home_asset":
        from datetime import date as dt_date
        asset = HomeAsset(
            id=str(uuid.uuid4()),
            homeowner_id=user.id,
            asset_type=tool_input.get("asset_type", ""),
            brand_name=tool_input.get("brand_name", ""),
            installation_date=dt_date.fromisoformat(tool_input.get("installation_date", str(dt_date.today()))),
            warranty_months=tool_input.get("warranty_months", 12),
            tradie_name=tool_input.get("tradie_name"),
        )
        db.add(asset)
        await db.commit()
        return {"success": True, "asset_type": asset.asset_type, "brand_name": asset.brand_name}

    if tool_name == "get_my_leads":
        tradie_r = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user.id))
        profile = tradie_r.scalar_one_or_none()
        if not profile:
            return {"error": "Tradie profile not found"}
        leads_r = await db.execute(
            select(Lead).where(Lead.tradie_id == profile.id).order_by(Lead.sent_at.desc()).limit(10)
        )
        leads = leads_r.scalars().all()
        result = []
        for lead in leads:
            job_r = await db.execute(select(Job).where(Job.id == lead.job_id))
            job = job_r.scalar_one_or_none()
            if job:
                result.append({
                    "lead_id": lead.id, "job_id": job.id, "title": job.title,
                    "suburb": job.suburb, "state": job.state, "urgency": job.urgency,
                    "intent": job.intent_level, "job_type": job.job_type,
                    "sent": lead.sent_at.strftime("%d %b %Y %H:%M"), "lead_status": lead.status,
                })
        return {"leads": result}

    if tool_name == "send_quote":
        tradie_r = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user.id))
        profile = tradie_r.scalar_one_or_none()
        if not profile:
            return {"error": "Tradie profile not found"}
        lead_r = await db.execute(select(Lead).where(Lead.id == tool_input.get("lead_id", "")))
        lead = lead_r.scalar_one_or_none()
        if not lead:
            return {"error": "Lead not found"}
        quote = Quote(
            id=str(uuid.uuid4()), lead_id=tool_input.get("lead_id"),
            job_id=lead.job_id, tradie_id=profile.id,
            amount=tool_input.get("amount", 0), message=tool_input.get("message", ""),
            status="pending",
        )
        db.add(quote)
        await db.commit()
        return {"success": True, "quote_id": quote.id, "amount": quote.amount}

    if tool_name == "get_earnings_summary":
        tradie_r = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user.id))
        profile = tradie_r.scalar_one_or_none()
        if not profile:
            return {"error": "Tradie profile not found"}
        return await get_monthly_summary(profile.id, db)

    if tool_name == "get_tradie_pass":
        from models.tradie_pass import TradiePass
        tradie_r = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user.id))
        profile = tradie_r.scalar_one_or_none()
        if not profile:
            return {"error": "Tradie profile not found"}
        pass_r = await db.execute(select(TradiePass).where(TradiePass.tradie_id == profile.id))
        tp = pass_r.scalar_one_or_none()
        if not tp:
            return {"pass_score": 0, "badge_level": "bronze", "message": "No compliance data yet."}
        return {
            "pass_score": tp.pass_score, "badge_level": tp.badge_level,
            "abn_verified": tp.abn_verified, "licence_verified": tp.licence_verified,
            "pli_verified": tp.pli_verified, "wc_verified": tp.wc_verified,
            "white_card": tp.white_card_verified, "swms_uploaded": tp.swms_uploaded,
        }

    if tool_name == "generate_swms":
        tradie_r = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user.id))
        profile = tradie_r.scalar_one_or_none()
        if not profile:
            return {"error": "Tradie profile not found"}
        content = await generate_swms_with_ai(
            job_type=tool_input.get("job_type", ""),
            state=tool_input.get("state", "NSW"),
            tradie_name=user.full_name,
            business_name=profile.business_name or user.full_name,
            job_description=tool_input.get("job_description", ""),
        )
        from models.swms_document import SWMSDocument
        doc = SWMSDocument(
            id=str(uuid.uuid4()), tradie_id=profile.id,
            job_type=tool_input.get("job_type", ""),
            state=tool_input.get("state", "NSW"), content=content,
        )
        db.add(doc)
        await db.commit()
        return {"success": True, "doc_id": doc.id, "preview": content[:300] + "...",
                "message": "SWMS generated. Download from your documents."}

    if tool_name == "update_job_preference":
        from models.tradie_preference import TradiePreference
        tradie_r = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user.id))
        profile = tradie_r.scalar_one_or_none()
        if not profile:
            return {"error": "Tradie profile not found"}
        pref_r = await db.execute(select(TradiePreference).where(TradiePreference.tradie_id == profile.id))
        pref = pref_r.scalar_one_or_none()
        if not pref:
            pref = TradiePreference(id=str(uuid.uuid4()), tradie_id=profile.id)
            db.add(pref)
        for k, v in tool_input.items():
            if hasattr(pref, k):
                setattr(pref, k, v)
        await db.commit()
        return {"success": True, "updated": tool_input}

    if tool_name == "get_my_categories":
        tradie_r = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user.id))
        profile = tradie_r.scalar_one_or_none()
        if not profile:
            return {"error": "Profile not found"}
        cats_r = await db.execute(
            select(Category)
            .join(TradieCategory, TradieCategory.category_id == Category.id)
            .where(TradieCategory.tradie_id == profile.id)
        )
        cats = cats_r.scalars().all()
        return {"categories": [{"name": c.name, "slug": c.slug} for c in cats]}

    return {"error": f"Unknown tool: {tool_name}"}


def _asset_health(asset: HomeAsset) -> dict:
    from datetime import date
    today = date.today()
    age_months = (today - asset.installation_date).days / 30
    lifespan = asset.expected_lifespan or 120
    pct = min(age_months / lifespan, 1.0)
    score = max(0, int(100 - pct * 70))
    if score >= 90:   label = "Excellent"
    elif score >= 70: label = "Good"
    elif score >= 50: label = "Fair"
    elif score >= 30: label = "Poor"
    else:             label = "Critical"
    return {"score": score, "label": label}


async def _call_groq(messages: list, formatted_tools: list, system_prompt: str, force_text: bool = False) -> dict:
    """
    Single Groq API call. Extracted to avoid repetition.

    Args:
        force_text: When True, sets tool_choice='none' to prevent
                    the model from calling tools again after results
                    are already appended. Fixes the Groq 400 error
                    where llama re-generates tool calls in text format.
    """
    payload = {
        "model":      GROQ_MODEL,
        "max_tokens": 1024,
        "messages":   [{"role": "system", "content": system_prompt}, *messages],
        "tools":      formatted_tools,
        # ── KEY FIX ────────────────────────────────────────────────────────
        # After tool results are appended, force a plain text response.
        # Without this, llama-3.3-70b re-generates tool calls in malformed
        # XML/text format which Groq rejects with 400 "tool call validation failed".
        "tool_choice": "none" if force_text else "auto",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            GROQ_API_URL,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY', '')}",
            },
            json=payload,
        )

    return response


async def run_agent(
    message:      str,
    history:      list,
    user:         User,
    db:           AsyncSession,
    session_id:   str,
    image_base64: Optional[str] = None,
    image_mime:   str = "image/jpeg",
) -> dict:
    """
    Run one turn of the AI agent.
    Returns { response, ui_component, vision, actions, error }
    """

    # ── Step 1: Load tradie profile ───────────────────────────────────────────
    profile = None
    if user.role == "tradie":
        p_result = await db.execute(select(TradieProfile).where(TradieProfile.user_id == user.id))
        profile = p_result.scalar_one_or_none()

    # ── Step 2: Load memory context ───────────────────────────────────────────
    memory_context = await get_user_context(user.id, db)

    # ── Step 3: Vision analysis ───────────────────────────────────────────────
    vision_analysis = None
    vision_component = None
    vision_context = ""

    if image_base64:
        print(f"[AGENT] Photo uploaded — running vision analysis")
        vision_analysis = await analyse_photo(image_base64, image_mime)
        if not vision_analysis.get("error"):
            vision_context = build_vision_context(vision_analysis)
            vision_component = select_vision_component(vision_analysis)

    # ── Step 4: Build tools list ──────────────────────────────────────────────
    tools = (TRADIE_TOOLS if user.role == "tradie" else HOMEOWNER_TOOLS) + SHARED_TOOLS

    formatted_tools = [
        {
            "type": "function",
            "function": {
                "name":        t["name"],
                "description": t["description"],
                "parameters":  t["input_schema"],
            },
        }
        for t in tools
    ]

    # Inject vision context into user message
    effective_message = message
    if vision_context:
        effective_message = f"{vision_context}\n\nUser message: {message}"

    # Build running message list from history
    messages = []
    for h in history[-20:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": effective_message})

    system_prompt = get_system_prompt(user, profile, memory_context)
    actions_taken = []
    last_component = vision_component

    # ── Step 5: Agentic loop ──────────────────────────────────────────────────
    #
    # Structure:
    #   Pass 1 (force_text=False): model may call tools or respond directly
    #   Pass 2 (force_text=True):  after tool results appended, force text response
    #
    # This two-pass approach eliminates the Groq 400 error where llama
    # tries to re-call tools in a malformed text format on the second pass.

    tools_have_run = False

    for iteration in range(5):
        # Force text-only response once tools have already executed
        force_text = tools_have_run

        response = await _call_groq(messages, formatted_tools, system_prompt, force_text)

        if response.status_code != 200:
            error_msg = response.text
            if not force_text:
                # Fallback: model generated bad tool syntax. Retry with tools disabled so user gets the text.
                response = await _call_groq(messages, formatted_tools, system_prompt, force_text=True)

            if response.status_code != 200:
                print(f"[AGENT] Groq error {response.status_code}: {error_msg[:500]}")
                return {
                    "response":     "I'm having trouble connecting right now. Please try again in a moment.",
                "ui_component": None,
                "vision":       vision_analysis,
                "actions":      actions_taken,
                "error":        True,
            }

        data   = response.json()
        choice = data.get("choices", [{}])[0]
        msg    = choice.get("message", {})
        finish = choice.get("finish_reason", "")

        # Append assistant message to running history
        assistant_msg = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            assistant_msg["tool_calls"] = msg["tool_calls"]
        messages.append(assistant_msg)

        # ── No tool calls → final text response ──────────────────────────────
        if finish == "stop" or not msg.get("tool_calls"):
            return {
                "response":     msg.get("content", ""),
                "ui_component": last_component,
                "vision":       vision_analysis,
                "actions":      actions_taken,
                "error":        False,
            }

        # ── Tool calls → execute each one ────────────────────────────────────
        if msg.get("tool_calls"):
            tool_result_msgs = []

            for tool_call in msg["tool_calls"]:
                tool_name  = tool_call["function"]["name"]
                tool_input = json.loads(tool_call["function"]["arguments"])
                tool_id    = tool_call["id"]

                print(f"[AGENT] Tool call: {tool_name} {json.dumps(tool_input)[:120]}")
                result = await execute_tool(tool_name, tool_input, user, db)

                actions_taken.append({"tool": tool_name, "input": tool_input, "result": result})

                # Select UI component for this tool result
                tool_component = select_component(tool_name, result, vision_analysis)
                if tool_component:
                    # Vision component always wins if present; otherwise use tool's component
                    last_component = vision_component if vision_component else tool_component

                tool_result_msgs.append({
                    "role":         "tool",
                    "tool_call_id": tool_id,
                    "content":      json.dumps(result),
                })

            messages.extend(tool_result_msgs)
            tools_have_run = True  # ← Next iteration will use force_text=True
            continue

        break

    return {
        "response":     "I wasn't able to complete that request. Please try again.",
        "ui_component": last_component,
        "vision":       vision_analysis,
        "actions":      actions_taken,
        "error":        True,
    }
