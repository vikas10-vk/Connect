"""
Memory Service
--------------
After each conversation turn, extracts structured insights from the
user's messages and stores them on the user profile.

These insights power:
  - Proactive suggestions ("Last week you mentioned your gutters...")
  - Smarter search (pre-fill suburb, trade category)
  - Gap analysis ("You haven't mentioned a roof inspection yet...")

Runs as a FastAPI BackgroundTask — non-blocking, fires after response is sent.
"""

import json
import os
import uuid

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
INSIGHT_MODEL = "llama-3.3-70b-versatile"

INSIGHT_SYSTEM_PROMPT = """You are a data extraction assistant. Extract structured insights from a homeowner or tradie conversation.

Respond ONLY with valid JSON — no explanation, no markdown fences.

JSON schema:
{
  "home_suburb": "suburb name if mentioned, else null",
  "home_state": "state abbreviation if mentioned, else null",
  "home_postcode": "postcode if mentioned, else null",
  "mentioned_problems": ["list of home problems mentioned e.g. leaking tap, broken fence"],
  "mentioned_assets": ["list of appliances or systems e.g. ducted AC, solar panels"],
  "trade_interests": ["trade categories mentioned e.g. plumbing, electrical"],
  "urgency_signals": ["phrases indicating urgency e.g. urgent, asap, flooding"],
  "unresolved_issues": ["problems mentioned but no job posted for them yet"],
  "user_intent": "browsing | ready_to_hire | just_posted | comparing_quotes | unknown",
  "sentiment": "positive | neutral | frustrated | urgent",
  "key_tags": ["up to 5 short tags summarising this conversation"]
}

If a field cannot be determined from the conversation, use null or empty array.
Only extract what is clearly stated — do not infer or assume."""


async def get_user_context(user_id: str, db: AsyncSession) -> str:
    """
    Load stored insights for a user and format as context
    to prepend to the AI system prompt.

    IMPORTANT: Always rolls back on any DB error so the session
    stays healthy for subsequent queries in the same request.
    """
    try:
        result = await db.execute(
            text("""
                SELECT home_suburb, home_state, home_postcode,
                       mentioned_problems, mentioned_assets, trade_interests,
                       unresolved_issues, user_intent, last_sentiment
                FROM user_insights
                WHERE user_id = :uid
            """),
            {"uid": user_id},
        )
        row = result.fetchone()
        if not row:
            return ""

        lines = ["[USER MEMORY — from past conversations]"]

        if row.home_suburb:
            lines.append(f"Home location: {row.home_suburb}, {row.home_state or ''} {row.home_postcode or ''}".strip())

        if row.mentioned_problems:
            problems = json.loads(row.mentioned_problems)
            if problems:
                lines.append(f"Problems mentioned before: {', '.join(problems[:5])}")

        if row.unresolved_issues:
            unresolved = json.loads(row.unresolved_issues)
            if unresolved:
                lines.append(f"Unresolved issues (no job posted yet): {', '.join(unresolved[:3])}")

        if row.trade_interests:
            trades = json.loads(row.trade_interests)
            if trades:
                lines.append(f"Trade categories of interest: {', '.join(trades[:5])}")

        if row.user_intent and row.user_intent != "unknown":
            lines.append(f"Last known intent: {row.user_intent}")

        if len(lines) == 1:
            return ""

        lines.append("Use this context naturally — don't mention that you 'remembered' it unless asked.")
        return "\n".join(lines)

    except Exception as e:
        print(f"[MEMORY] Context load failed: {e}")
        # ── CRITICAL: rollback the poisoned transaction so the DB session ──
        # remains usable for all subsequent queries in this request.
        try:
            await db.rollback()
        except Exception:
            pass
        return ""


async def extract_insights(
    user_message: str,
    assistant_response: str,
    user_id: str,
    db: AsyncSession,
) -> dict | None:
    """
    Extract structured insights from one conversation turn.
    Saves insights to the user's profile in the DB.

    This runs in the background — errors are logged but never raised.
    """
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        return None

    conversation_text = f"User said: {user_message}\nAssistant replied: {assistant_response}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {groq_api_key}",
                },
                json={
                    "model": INSIGHT_MODEL,
                    "max_tokens": 512,
                    "messages": [
                        {"role": "system", "content": INSIGHT_SYSTEM_PROMPT},
                        {"role": "user", "content": conversation_text},
                    ],
                    "temperature": 0.1,
                },
            )

        if response.status_code != 200:
            print(f"[MEMORY] Groq insight error {response.status_code}")
            return None

        data = response.json()
        raw = data["choices"][0]["message"]["content"].strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        insights = json.loads(raw)
        await _upsert_user_insights(user_id, insights, db)
        return insights

    except Exception as e:
        print(f"[MEMORY] Insight extraction failed: {e}")
        return None


async def _upsert_user_insights(user_id: str, insights: dict, db: AsyncSession) -> None:
    """
    Upsert extracted insights into user_insights table.
    Merges arrays so we accumulate knowledge over time.
    """
    try:
        result = await db.execute(
            text("SELECT id, mentioned_problems, mentioned_assets, trade_interests, unresolved_issues, key_tags FROM user_insights WHERE user_id = :uid"),
            {"uid": user_id},
        )
        existing = result.fetchone()

        def merge_lists(existing_json: str | None, new_list: list) -> str:
            existing_list = json.loads(existing_json) if existing_json else []
            merged = list(set(existing_list + (new_list or [])))
            return json.dumps(merged[:50])

        if existing:
            await db.execute(
                text("""
                    UPDATE user_insights SET
                        home_suburb         = COALESCE(:suburb, home_suburb),
                        home_state          = COALESCE(:state, home_state),
                        home_postcode       = COALESCE(:postcode, home_postcode),
                        mentioned_problems  = :problems,
                        mentioned_assets    = :assets,
                        trade_interests     = :trades,
                        unresolved_issues   = :unresolved,
                        key_tags            = :tags,
                        user_intent         = COALESCE(:intent, user_intent),
                        last_sentiment      = :sentiment,
                        updated_at          = NOW()
                    WHERE user_id = :uid
                """),
                {
                    "uid":        user_id,
                    "suburb":     insights.get("home_suburb"),
                    "state":      insights.get("home_state"),
                    "postcode":   insights.get("home_postcode"),
                    "problems":   merge_lists(existing.mentioned_problems,  insights.get("mentioned_problems", [])),
                    "assets":     merge_lists(existing.mentioned_assets,    insights.get("mentioned_assets", [])),
                    "trades":     merge_lists(existing.trade_interests,     insights.get("trade_interests", [])),
                    "unresolved": merge_lists(existing.unresolved_issues,   insights.get("unresolved_issues", [])),
                    "tags":       merge_lists(existing.key_tags,            insights.get("key_tags", [])),
                    "intent":     insights.get("user_intent"),
                    "sentiment":  insights.get("sentiment"),
                },
            )
        else:
            await db.execute(
                text("""
                    INSERT INTO user_insights
                        (id, user_id, home_suburb, home_state, home_postcode,
                         mentioned_problems, mentioned_assets, trade_interests,
                         unresolved_issues, key_tags, user_intent, last_sentiment,
                         created_at, updated_at)
                    VALUES
                        (:id, :uid, :suburb, :state, :postcode,
                         :problems, :assets, :trades,
                         :unresolved, :tags, :intent, :sentiment,
                         NOW(), NOW())
                """),
                {
                    "id":         str(uuid.uuid4()),
                    "uid":        user_id,
                    "suburb":     insights.get("home_suburb"),
                    "state":      insights.get("home_state"),
                    "postcode":   insights.get("home_postcode"),
                    "problems":   json.dumps(insights.get("mentioned_problems", [])),
                    "assets":     json.dumps(insights.get("mentioned_assets", [])),
                    "trades":     json.dumps(insights.get("trade_interests", [])),
                    "unresolved": json.dumps(insights.get("unresolved_issues", [])),
                    "tags":       json.dumps(insights.get("key_tags", [])),
                    "intent":     insights.get("user_intent"),
                    "sentiment":  insights.get("sentiment"),
                },
            )

        await db.commit()

    except Exception as e:
        print(f"[MEMORY] DB upsert failed: {e}")
        try:
            await db.rollback()
        except Exception:
            pass
