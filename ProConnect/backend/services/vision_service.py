"""
Vision Service
--------------
Analyses user-uploaded photos using Groq's vision model.
Returns structured damage/problem assessment to feed into the main agent.

Model: llama-3.2-11b-vision-preview (free on Groq)
Input: base64-encoded image (JPEG / PNG / WEBP)
Output: structured dict with problem, urgency, trade, and description
"""

import json
import os

import httpx

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
VISION_MODEL = "llama-3.2-11b-vision-preview"

VISION_SYSTEM_PROMPT = """You are an expert Australian building and home maintenance inspector.
Analyse the provided photo and respond ONLY with a valid JSON object — no explanation, no markdown.

JSON schema:
{
  "problem_detected": true | false,
  "problem_title": "Short title e.g. Burst flexi hose under kitchen sink",
  "problem_description": "2-3 sentence description of what you see and why it needs attention",
  "trade_required": "One of: Plumbing, Electrical, Roofing, Carpentry, Painting, Tiling, Pest Control, Air Conditioning, Landscaping, General Maintenance, Unknown",
  "urgency": "One of: emergency, asap, next_few_days, flexible",
  "urgency_reason": "One sentence explaining urgency rating",
  "estimated_job_type": "repair | replace | new_installation | inspection",
  "confidence": "high | medium | low",
  "visible_damage": ["list", "of", "specific", "damage", "items", "observed"],
  "safety_risk": true | false,
  "safety_note": "Brief safety note if risk is true, else null"
}

Be practical and specific. If the image is unclear or not a home/building issue, set problem_detected to false."""


async def analyse_photo(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    """
    Call the Groq vision model to analyse a photo.

    Args:
        image_base64: Base64-encoded image string (no data URI prefix needed)
        mime_type: Image MIME type — image/jpeg, image/png, image/webp

    Returns:
        Structured dict with analysis, or error dict if call fails
    """
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        return {"error": True, "message": "Vision service not configured"}

    # Build the data URI Groq expects
    data_uri = f"data:{mime_type};base64,{image_base64}"

    payload = {
        "model": VISION_MODEL,
        "max_tokens": 1024,
        "messages": [
            {
                "role": "system",
                "content": VISION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    },
                    {
                        "type": "text",
                        "text": "Please analyse this photo and provide the JSON assessment.",
                    },
                ],
            },
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {groq_api_key}",
                },
                json=payload,
            )

        if response.status_code != 200:
            print(f"[VISION] Groq error {response.status_code}: {response.text[:300]}")
            return {
                "error": True,
                "message": f"Vision API error: {response.status_code}",
            }

        data = response.json()
        raw_text = data["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if model wraps response
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()

        analysis = json.loads(raw_text)
        analysis["error"] = False
        return analysis

    except json.JSONDecodeError as e:
        print(f"[VISION] JSON parse error: {e} | raw: {raw_text[:200]}")
        return {
            "error": True,
            "message": "Could not parse vision response",
            "raw": raw_text[:200],
        }
    except Exception as e:
        print(f"[VISION] Unexpected error: {e}")
        return {"error": True, "message": str(e)}


def build_vision_context(analysis: dict) -> str:
    """
    Convert vision analysis dict into a natural language context string
    to inject into the AI agent's user message.
    """
    if analysis.get("error") or not analysis.get("problem_detected"):
        return ""

    lines = [
        "[PHOTO ANALYSIS] The user has uploaded a photo.",
        f"Problem detected: {analysis.get('problem_title', 'Unknown issue')}",
        f"Description: {analysis.get('problem_description', '')}",
        f"Trade required: {analysis.get('trade_required', 'Unknown')}",
        f"Urgency: {analysis.get('urgency', 'flexible')} — {analysis.get('urgency_reason', '')}",
        f"Job type: {analysis.get('estimated_job_type', 'repair')}",
    ]

    if analysis.get("safety_risk"):
        lines.append(f"⚠️ SAFETY RISK: {analysis.get('safety_note', '')}")

    if analysis.get("visible_damage"):
        lines.append(f"Visible damage: {', '.join(analysis['visible_damage'])}")

    return "\n".join(lines)
