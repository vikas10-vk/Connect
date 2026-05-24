from datetime import date

from models.tradie_pass import TradiePass


def calculate_pass_score(tp: TradiePass) -> int:
    """
    Calculate TradiePASS score 0-100.
    Weights reflect real-world importance for winning jobs.
    """
    score = 0
    today = date.today()

    # ABN verified — 20 points
    if tp.abn_verified:
        score += 20

    # Licence — 25 points
    if tp.licence_verified:
        score += 15
        # Extra 10 if not expired
        if tp.licence_expiry and tp.licence_expiry > today:
            score += 10

    # Public Liability Insurance — 25 points
    if tp.pli_verified:
        score += 15
        if tp.pli_expiry and tp.pli_expiry > today:
            score += 5
        if tp.pli_amount_m and tp.pli_amount_m >= 10:
            score += 5

    # Workers Compensation — 10 points
    if tp.wc_verified:
        score += 10

    # White Card — 10 points
    if tp.white_card_verified:
        score += 10

    # SWMS uploaded — 10 points
    if tp.swms_uploaded:
        score += 5
        # Extra 5 if updated within 12 months
        if tp.swms_updated_at:
            from datetime import datetime
            months_old = (datetime.utcnow() - tp.swms_updated_at).days / 30
            if months_old <= 12:
                score += 5

    return min(100, score)


def calculate_badge(score: int, review_count: int, response_rate: float) -> str:
    """
    Badge levels:
    Elite  → score ≥ 90, 20+ reviews, 95%+ response rate
    Gold   → score ≥ 70, 5+ reviews
    Silver → score ≥ 50
    Bronze → everything else
    """
    if score >= 90 and review_count >= 20 and response_rate >= 0.95:
        return "elite"
    if score >= 70 and review_count >= 5:
        return "gold"
    if score >= 50:
        return "silver"
    return "bronze"


# ── State × Category compliance requirements ──────────────────
LICENCE_REQUIREMENTS: dict[str, dict[str, list[str]]] = {
    "NSW": {
        "Electrical":    ["Electrical Contractor Licence (NSW Fair Trading)", "Public Liability $5M min", "Workers Compensation (if employing)"],
        "Plumbing":      ["Plumbing Contractor Licence (NSW Fair Trading)", "Public Liability $5M min", "Drainage Contractor Licence for drainage work"],
        "Building":      ["Builder Licence (NSW Fair Trading)", "Home Building Compensation Fund cover for jobs over $20k"],
        "Air Conditioning": ["Refrigerant Handling Licence (ARC)", "Electrical Licence for electrical connections", "Public Liability $5M min"],
        "Gas System":    ["Gas Fitting Licence (NSW Fair Trading)", "Public Liability $5M min"],
        "Roofing":       ["Builder Licence for structural work", "Public Liability $5M min"],
        "default":       ["Public Liability Insurance", "ABN registration"],
    },
    "VIC": {
        "Electrical":    ["Electrical Contractor Licence (Energy Safe Victoria)", "Public Liability $10M min", "Workers Compensation"],
        "Plumbing":      ["Plumbing Licence (VBA)", "Public Liability $5M min"],
        "Building":      ["Building Practitioner Registration (VBA)", "Domestic Building Insurance for jobs over $16k"],
        "Air Conditioning": ["Refrigerant Handling Licence (ARC)", "Electrical Licence for electrical work"],
        "Gas System":    ["Gasfitting Licence (VBA)", "Public Liability $5M min"],
        "default":       ["Public Liability Insurance", "ABN registration"],
    },
    "QLD": {
        "Electrical":    ["Electrical Contractor Licence (Electrical Safety Office)", "Public Liability $5M min", "Workers Compensation"],
        "Plumbing":      ["Plumbing Licence (QBCC)", "Public Liability $5M min"],
        "Building":      ["QBCC Contractor Licence", "Home Warranty Insurance for jobs over $3,300"],
        "Air Conditioning": ["Refrigerant Handling Licence (ARC)", "Electrical Licence", "QBCC Licence"],
        "Gas System":    ["Gas Work Licence (QBCC)", "Public Liability $5M min"],
        "default":       ["Public Liability Insurance", "ABN registration"],
    },
    "WA": {
        "Electrical":    ["Electrical Contractor Licence (EnergySafety WA)", "Public Liability $5M min"],
        "Plumbing":      ["Plumbing Contractor Licence (Building and Energy WA)", "Public Liability $5M min"],
        "Building":      ["Builder Registration (Building Commission WA)", "Home Indemnity Insurance for jobs over $20k"],
        "default":       ["Public Liability Insurance", "ABN registration"],
    },
    "SA": {
        "Electrical":    ["Electrical Contractor Licence (Consumer and Business Services SA)", "Public Liability $5M min"],
        "Plumbing":      ["Plumbing Contractor Licence (CBS SA)", "Public Liability $5M min"],
        "Building":      ["Building Work Contractor Licence (CBS SA)"],
        "default":       ["Public Liability Insurance", "ABN registration"],
    },
    "default": {
        "default": ["Public Liability Insurance", "ABN registration", "Check your state licensing authority"],
    },
}

HIGH_RISK_WARNINGS: dict[str, list[str]] = {
    "Electrical":    ["Working near live wires", "Working in ceiling spaces — High Risk Work Licence may apply", "Solar installations require additional accreditation"],
    "Plumbing":      ["Working on gas — separate gas licence required", "Backflow prevention — specialist licence required"],
    "Building":      ["Work above 2m — Working at Heights training required", "Asbestos removal — licensed removalist required for non-friable, licensed contractor for friable"],
    "Roofing":       ["Working at Heights — RIIWHS204D required", "Asbestos awareness mandatory"],
    "Air Conditioning": ["Refrigerant handling — ARC certification mandatory", "Electrical connections require electrical licence"],
}


def get_licence_requirements(state: str, category: str, job_type: str = "residential") -> dict:
    """
    Return compliance requirements for a given state + category + job_type.
    """
    state_rules   = LICENCE_REQUIREMENTS.get(state, LICENCE_REQUIREMENTS["default"])
    requirements  = state_rules.get(category, state_rules.get("default", ["Public Liability Insurance", "ABN registration"]))
    warnings      = HIGH_RISK_WARNINGS.get(category, [])

    commercial_extras = []
    if job_type == "commercial":
        commercial_extras = [
            "SWMS required before starting work",
            "Site induction records required",
            "WHS management plan may be required",
            "Builders may require evidence of compliance upfront",
        ]

    return {
        "state":             state,
        "category":          category,
        "job_type":          job_type,
        "requirements":      requirements,
        "high_risk_warnings": warnings,
        "commercial_extras": commercial_extras,
        "reference":         f"Check {state} licensing authority for current requirements",
    }
