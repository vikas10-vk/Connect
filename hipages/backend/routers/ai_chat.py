"""
AI Chat Router
--------------
Handles all AI chat endpoints.

New in Generative UI version:
  - Accepts optional base64 image for vision analysis
  - Returns ui_component in every response
  - Stores ui_component JSON in chat history
  - Fires background memory extraction after each turn
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.session import get_db
from models.user import User
from models.chat_conversation import ChatConversation
from services.auth_service import get_current_user
from services.ai_agent_service import run_agent
from services.memory_service import extract_insights
from pydantic import BaseModel
from typing import Optional
import uuid
import json

router = APIRouter(prefix="/api/v1/ai", tags=["AI Chat"])


class ChatRequest(BaseModel):
    message:      str
    session_id:   Optional[str]  = None
    # Vision — base64 encoded image (client strips the data URI prefix)
    image_base64: Optional[str]  = None
    image_mime:   Optional[str]  = "image/jpeg"   # image/jpeg | image/png | image/webp


class ChatResponse(BaseModel):
    response:     str
    ui_component: Optional[dict] = None
    vision:       Optional[dict] = None
    actions:      list           = []
    session_id:   str
    error:        bool           = False

class AnalyseJobRequest(BaseModel):
    description: str
    category:    str
    photo_urls:  Optional[list[str]] = []

class AnalyseJobResponse(BaseModel):
    title:        str
    job_type:     str
    service_type: str
    explanation:  str
    missing_info: str = ""



@router.post("/chat", response_model=ChatResponse)
async def chat(
    body:             ChatRequest,
    background_tasks: BackgroundTasks,
    current_user:     User          = Depends(get_current_user),
    db:               AsyncSession  = Depends(get_db),
):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    # Validate image if provided
    if body.image_base64 and len(body.image_base64) > 10_000_000:
        raise HTTPException(status_code=400, detail="Image too large. Please use an image under 7MB.")

    # Generate or reuse session ID
    session_id = body.session_id or str(uuid.uuid4())

    # ── Load conversation history for this session ────────────────────────────
    history_result = await db.execute(
        select(ChatConversation)
        .where(
            ChatConversation.user_id    == current_user.id,
            ChatConversation.session_id == session_id,
        )
        .order_by(ChatConversation.created_at.asc())
        .limit(40)
    )
    history_rows = history_result.scalars().all()
    history = [{"role": h.role, "content": h.content} for h in history_rows]

    import traceback
    try:
        # ── Run the agent ─────────────────────────────────────────────────────────
        result = await run_agent(
            message      = body.message,
            history      = history,
            user         = current_user,
            db           = db,
            session_id   = session_id,
            image_base64 = body.image_base64,
            image_mime   = body.image_mime or "image/jpeg",
        )

        # ── Persist user message ──────────────────────────────────────────────────
        user_msg = ChatConversation(
            id         = str(uuid.uuid4()),
            user_id    = current_user.id,
            session_id = session_id,
            role       = "user",
            content    = body.message,
            image_url  = None,   # Could store R2 URL here if client uploads first
        )
        db.add(user_msg)

        # ── Persist assistant response ────────────────────────────────────────────
        ui_component_json = json.dumps(result.get("ui_component")) if result.get("ui_component") else None

        assistant_msg = ChatConversation(
            id           = str(uuid.uuid4()),
            user_id      = current_user.id,
            session_id   = session_id,
            role         = "assistant",
            content      = result["response"],
            ui_component = ui_component_json,
        )
        db.add(assistant_msg)
        await db.commit()

        # ── Fire background memory extraction (non-blocking) ─────────────────────
        # Runs after response is sent to user — never delays the chat
        background_tasks.add_task(
            extract_insights,
            user_message       = body.message,
            assistant_response = result["response"],
            user_id            = current_user.id,
            db                 = db,
        )

        return ChatResponse(
            response     = result["response"],
            ui_component = result.get("ui_component"),
            vision       = result.get("vision"),
            actions      = result.get("actions", []),
            session_id   = session_id,
            error        = result.get("error", False),
        )
    except Exception as e:
        with open("chat_error.log", "w") as f:
            f.write(traceback.format_exc())
        print("CHAT ERROR SAVED TO chat_error.log")
        raise e


@router.get("/history/{session_id}")
async def get_history(
    session_id:   str,
    current_user: User          = Depends(get_current_user),
    db:           AsyncSession  = Depends(get_db),
):
    """
    Returns full conversation history for a session,
    including ui_component specs so the frontend can re-render
    components when loading a past conversation.
    """
    result = await db.execute(
        select(ChatConversation)
        .where(
            ChatConversation.user_id    == current_user.id,
            ChatConversation.session_id == session_id,
        )
        .order_by(ChatConversation.created_at.asc())
    )
    history = result.scalars().all()

    return [
        {
            "role":         h.role,
            "content":      h.content,
            "ui_component": json.loads(h.ui_component) if h.ui_component else None,
            "image_url":    h.image_url,
            "created_at":   h.created_at.isoformat(),
        }
        for h in history
    ]


@router.delete("/history/{session_id}")
async def clear_history(
    session_id:   str,
    current_user: User          = Depends(get_current_user),
    db:           AsyncSession  = Depends(get_db),
):
    result = await db.execute(
        select(ChatConversation)
        .where(
            ChatConversation.user_id    == current_user.id,
            ChatConversation.session_id == session_id,
        )
    )
    rows = result.scalars().all()
    for row in rows:
        await db.delete(row)
    await db.commit()
    return {"cleared": True, "count": len(rows)}


@router.get("/sessions")
async def get_sessions(
    current_user: User          = Depends(get_current_user),
    db:           AsyncSession  = Depends(get_db),
):
    result = await db.execute(
        select(
            ChatConversation.session_id,
            ChatConversation.created_at,
        )
        .where(ChatConversation.user_id == current_user.id)
        .order_by(ChatConversation.created_at.desc())
        .distinct()
        .limit(20)
    )
    rows = result.all()
    return [{"session_id": r.session_id, "started": r.created_at.isoformat()} for r in rows]

@router.post("/analyse-job", response_model=AnalyseJobResponse)
async def analyse_job(body: AnalyseJobRequest):
    import os, json
    from groq import AsyncGroq

    client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))

    has_photos = len(body.photo_urls or []) > 0

    prompt = f"""You are a professional trades job writer for an Australian marketplace.

Category: {body.category}
Customer wrote: "{body.description}"
Photos provided: {"yes" if has_photos else "no"}

Your job is to write a clear, professional job brief that a tradie can quote from accurately.

Rules:
- Extract every specific detail from the description (materials, quantities, measurements, room, brand, urgency)
- If a detail is not mentioned, do NOT invent it — write "not specified"
- The brief must be written in third person, professional tone
- Title must be specific — include material/room/action e.g. "Replace cracked porcelain floor tiles in main bathroom"
- service_type must be exactly one of: repair, new_installation, replace, other
- job_type must be exactly one of: residential, commercial

Return ONLY this JSON, no markdown:
{{
  "title": "specific job title under 70 chars",
  "job_type": "residential or commercial",
  "service_type": "repair or new_installation or replace or other",
  "brief": "2-3 sentence professional scope of work. State what needs doing, specific materials/quantities if mentioned, location in property, and any urgency. Example: Customer requires replacement of approximately 15sqm of cracked porcelain floor tiles in the main bathroom. Grout lines also need repointing throughout. Access is available via rear entrance and job is needed within the next few days.",
  "missing_info": "comma-separated list of key details not provided, e.g. tile type, area in sqm — or empty string if sufficient"
}}"""

    try:
        res = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a professional trades job writer. Write clear scopes of work. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
            temperature=0.1,
        )
        text = res.choices[0].message.content.strip().replace("```json","").replace("```","").strip()
        data = json.loads(text)

        job_type = data.get("job_type", "residential").lower()
        if job_type not in ("residential", "commercial"):
            job_type = "residential"
        service_type = data.get("service_type", "repair").lower()
        if service_type not in ("repair", "new_installation", "replace", "other"):
            service_type = "repair"

        return AnalyseJobResponse(
            title=data.get("title", f"{body.category} job")[:100],
            job_type=job_type,
            service_type=service_type,
            explanation=data.get("brief", ""),
            missing_info=data.get("missing_info", ""),
        )
    except Exception:
        return AnalyseJobResponse(
            title=f"{body.category} job",
            job_type="residential",
            service_type="repair",
            explanation="",
            missing_info="",
        )