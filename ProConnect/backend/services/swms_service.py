import httpx
import json
from datetime import datetime


SWMS_TEMPLATES: dict[str, dict] = {
    "Electrical": {
        "hazards": [
            "Electric shock from live conductors",
            "Arc flash from short circuits",
            "Falls from ladders or elevated work areas",
            "Fire from overloaded circuits",
            "Asbestos exposure in older buildings",
        ],
        "controls": [
            "Isolate and lock out/tag out all circuits before commencing work",
            "Test before touch — use approved voltage detector",
            "Maintain safe clearance distances from live parts",
            "Use insulated tools rated for the voltage being worked on",
            "Wear appropriate PPE: safety glasses, insulated gloves, safety boots",
            "Ensure adequate lighting in work areas",
            "Do not work alone on live electrical systems",
        ],
        "ppe": ["Insulated gloves (Class 00 minimum)", "Safety glasses", "Safety boots with rubber soles", "Hard hat (if working overhead)", "Hi-vis vest on sites"],
        "legislation": ["Electrical Safety Act (state-specific)", "WHS Act 2011", "AS/NZS 3000 Wiring Rules"],
    },
    "Plumbing": {
        "hazards": [
            "Manual handling injuries from heavy pipe and equipment",
            "Cuts from pipe cutting tools",
            "Burns from hot water or steam",
            "Confined space hazards in service areas",
            "Asbestos in older pipe lagging",
            "Slips and falls on wet surfaces",
        ],
        "controls": [
            "Use mechanical aids for lifting heavy pipe sections",
            "Isolate water supply before commencing work",
            "Allow hot water systems to cool before disconnecting",
            "Test confined spaces for oxygen levels before entry",
            "Do not disturb suspected asbestos — call licensed removalist",
            "Place non-slip matting around wet work areas",
        ],
        "ppe": ["Safety boots", "Cut-resistant gloves", "Safety glasses", "Hard hat (on construction sites)", "Waterproof clothing"],
        "legislation": ["Plumbing and Drainage Act (state-specific)", "WHS Act 2011", "AS/NZS 3500 Plumbing Standards"],
    },
    "Roofing": {
        "hazards": [
            "Falls from height — primary risk",
            "Falls through fragile roof materials",
            "Struck by falling tools or materials",
            "Heat stress in summer conditions",
            "Asbestos in old roofing materials",
            "Electrical hazards from overhead lines",
        ],
        "controls": [
            "Install edge protection or safety mesh before commencing roof work",
            "Use a rated safety harness with lanyard attached to anchor point",
            "Conduct inspection for fragile materials before walking on roof",
            "Use tool tethers to prevent dropped tools",
            "Schedule work to avoid peak heat hours — hydration breaks mandatory",
            "Maintain 3m clearance from overhead power lines or call electricity provider",
            "Assume all old roofing materials contain asbestos until tested",
        ],
        "ppe": ["Full body safety harness", "Hard hat", "Safety boots with ankle support", "Hi-vis vest", "Safety glasses", "Sunscreen and hat"],
        "legislation": ["WHS Act 2011", "AS/NZS 1891.1 Industrial Fall Arrest", "RIIWHS204D Working at Heights", "Code of Practice: Managing the Risk of Falls"],
    },
    "default": {
        "hazards": [
            "Manual handling injuries",
            "Slips trips and falls",
            "Tool and equipment injuries",
            "Exposure to hazardous materials",
            "Working in traffic or near plant",
        ],
        "controls": [
            "Conduct a site inspection before commencing work",
            "Use appropriate tools for the task",
            "Keep work area clean and free from trip hazards",
            "Wear appropriate PPE at all times",
            "Report all incidents and near misses immediately",
        ],
        "ppe": ["Safety boots", "Safety glasses", "Hi-vis vest", "Gloves as appropriate"],
        "legislation": ["WHS Act 2011", "WHS Regulations (state-specific)", "Relevant Australian Standards"],
    },
}


def generate_swms_text(
    job_type:       str,
    state:          str,
    tradie_name:    str,
    business_name:  str,
    job_description: str = "",
) -> str:
    """
    Generate a SWMS document as formatted text.
    Uses template data enhanced with job-specific details.
    """
    template = SWMS_TEMPLATES.get(job_type, SWMS_TEMPLATES["default"])
    now      = datetime.utcnow().strftime("%d %B %Y")

    hazards_text  = "\n".join(f"  {i+1}. {h}" for i, h in enumerate(template["hazards"]))
    controls_text = "\n".join(f"  {i+1}. {c}" for i, c in enumerate(template["controls"]))
    ppe_text      = "\n".join(f"  • {p}" for p in template["ppe"])
    leg_text      = "\n".join(f"  • {l}" for l in template["legislation"])

    return f"""
SAFE WORK METHOD STATEMENT (SWMS)
==================================

Document No:    SWMS-{datetime.utcnow().strftime("%Y%m%d%H%M")}
Date:           {now}
State:          {state}
Business:       {business_name}
Responsible Person: {tradie_name}
Work Type:      {job_type}

JOB DESCRIPTION
---------------
{job_description or f"{job_type} work as required."}

HAZARD IDENTIFICATION
---------------------
The following hazards have been identified for this work:

{hazards_text}

RISK CONTROLS
-------------
The following controls will be implemented to manage identified risks:

{controls_text}

PERSONAL PROTECTIVE EQUIPMENT (PPE)
------------------------------------
The following PPE is required for this work:

{ppe_text}

APPLICABLE LEGISLATION AND STANDARDS
--------------------------------------
This work is conducted in accordance with:

{leg_text}

EMERGENCY PROCEDURES
---------------------
  1. In the event of injury — call 000 immediately
  2. Notify the site manager/client
  3. Preserve the scene for investigation
  4. Complete an incident report within 24 hours
  5. Notify WorkSafe/SafeWork {state} if a notifiable incident occurs

SIGN OFF
---------
By commencing this work, the worker confirms they have:
  • Read and understood this SWMS
  • Been briefed on the hazards and controls
  • Inspected the work area and found conditions safe to proceed
  • Raised any concerns before commencing

Worker Signature: _____________________    Date: ___________

Supervisor/Authorised Person: ___________  Date: ___________

REVIEW
-------
This SWMS is to be reviewed:
  • Before each new job of this type
  • When site conditions change significantly
  • After any incident or near miss
  • At least annually

Generated by ProConnect platform | {now}
""".strip()


async def generate_swms_with_ai(
    job_type:        str,
    state:           str,
    tradie_name:     str,
    business_name:   str,
    job_description: str,
) -> str:
    """
    Enhanced SWMS generation using Claude API.
    Falls back to template if API call fails.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2000,
                    "messages": [{
                        "role": "user",
                        "content": f"""Generate a professional Safe Work Method Statement (SWMS) for Australian workplace safety compliance.

Job Type: {job_type}
State: {state}
Business: {business_name}
Tradie: {tradie_name}
Job Description: {job_description}

Generate a complete SWMS including:
1. Hazard identification specific to {job_type} work
2. Risk controls and safe work procedures
3. PPE requirements
4. Applicable Australian legislation ({state})
5. Emergency procedures

Format it as a professional document. Be specific and practical. Include state-specific requirements for {state}."""
                    }],
                }
            )

            if res.status_code == 200:
                data      = res.json()
                ai_content = data["content"][0]["text"]

                # Prepend header
                header = f"""SAFE WORK METHOD STATEMENT (SWMS)
==================================
Document No:    SWMS-{datetime.utcnow().strftime("%Y%m%d%H%M")}
Date:           {datetime.utcnow().strftime("%d %B %Y")}
Business:       {business_name}
Responsible:    {tradie_name}
State:          {state}

"""
                return header + ai_content
    except Exception:
        pass

    # Fallback to template
    return generate_swms_text(job_type, state, tradie_name, business_name, job_description)