"""
Tool definitions for the AI chat agent.
Each tool maps to a real backend operation.
Claude reads these descriptions and decides when to call them.
"""

HOMEOWNER_TOOLS = [
    {
        "name": "post_job",
        "description": "Post a new job on the platform. Use this when the homeowner describes work they need done. Always confirm the details before calling this tool.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title":        {"type": "string",  "description": "Short job title e.g. 'Fix leaking kitchen tap'"},
                "description":  {"type": "string",  "description": "Detailed description of the work needed"},
                "category_slug":{"type": "string",  "description": "Trade category slug e.g. plumbing, electrical, landscaping, cleaning, roofing, carpentry, painting, tiling, concreting, fencing, air-conditioning, pest-control, solar-installation"},
                "suburb":       {"type": "string",  "description": "Suburb name"},
                "state":        {"type": "string",  "description": "Australian state abbreviation: NSW, VIC, QLD, WA, SA, TAS, NT, ACT"},
                "postcode":     {"type": "string",  "description": "Australian postcode"},
                "urgency":      {"type": "string",  "description": "One of: flexible, asap, today, emergency, next_few_days, next_few_weeks, next_few_months"},
                "job_type":     {"type": "string",  "description": "residential or commercial"},
                "service_type": {"type": "string",  "description": "new_installation, repair, replace, or other"},
                "job_stage":    {"type": "string",  "description": "ready_to_hire or planning_budgeting"},
                "intent_level": {"type": "string",  "description": "high (ready to hire now) or planning (just exploring)"},
                "contact_name": {"type": "string",  "description": "Contact name for this job"},
                "contact_phone":{"type": "string",  "description": "Contact phone number"},
            },
            "required": ["title", "description", "category_slug", "suburb", "state", "urgency"],
        },
    },
    {
        "name": "get_my_jobs",
        "description": "Get the homeowner's posted jobs. Use when they ask about their jobs, quotes received, or job status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status: open, quoted, hired, in_progress, completed, cancelled. Leave empty for all."},
            },
            "required": [],
        },
    },
    {
        "name": "get_job_quotes",
        "description": "Get quotes for a specific job. Use when homeowner asks about quotes or wants to hire a tradie.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_id": {"type": "string", "description": "The job ID to get quotes for"},
            },
            "required": ["job_id"],
        },
    },
    {
        "name": "search_tradies",
        "description": "Search for available tradies. Use when homeowner asks to see tradies or browse professionals.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category_slug": {"type": "string", "description": "Trade category slug"},
                "suburb":        {"type": "string", "description": "Suburb to search near"},
            },
            "required": [],
        },
    },
    {
        "name": "get_home_assets",
        "description": "Get the homeowner's tracked home assets and their health scores.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "add_home_asset",
        "description": "Add a new home asset to track. Use when homeowner mentions an appliance or system they want to track.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_type":        {"type": "string", "description": "One of: Hot Water System, Air Conditioner, Electrical Board, Roof, Fence, Plumbing, Solar Panels, Gas System, Pool & Spa, Heating System, Security System, Garage Door, Pest Control, Painting, Flooring"},
                "brand_name":        {"type": "string", "description": "Brand name of the asset"},
                "installation_date": {"type": "string", "description": "Installation date in YYYY-MM-DD format"},
                "warranty_months":   {"type": "integer","description": "Warranty period in months"},
                "tradie_name":       {"type": "string", "description": "Name of tradie who installed it"},
            },
            "required": ["asset_type", "brand_name", "installation_date"],
        },
    },
    {
        "name": "check_licence_requirements",
        "description": "Check what licences and compliance a tradie needs for a specific job type in a state. Use when homeowner wants to verify a tradie.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state":    {"type": "string", "description": "Australian state abbreviation"},
                "category": {"type": "string", "description": "Trade category"},
                "job_type": {"type": "string", "description": "residential or commercial"},
            },
            "required": ["state", "category"],
        },
    },
]

TRADIE_TOOLS = [
    {
        "name": "get_my_leads",
        "description": "Get available job leads for the tradie. Use when tradie asks about new jobs, leads, or work available.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "send_quote",
        "description": "Send a quote for a job lead. Use when tradie wants to quote on a job. Always confirm amount and message before calling.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "description": "The lead ID to quote on"},
                "amount":  {"type": "number", "description": "Quote amount in AUD"},
                "message": {"type": "string", "description": "Message to the homeowner with the quote"},
            },
            "required": ["lead_id", "amount", "message"],
        },
    },
    {
        "name": "get_earnings_summary",
        "description": "Get the tradie's earnings summary, take-home estimate, and GST tracking.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_tradie_pass",
        "description": "Get the tradie's compliance score and verification status.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "generate_swms",
        "description": "Generate a Safe Work Method Statement for a job. Use when tradie needs safety documentation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "job_type":        {"type": "string", "description": "Type of trade work e.g. Electrical, Plumbing, Roofing"},
                "state":           {"type": "string", "description": "Australian state abbreviation"},
                "job_description": {"type": "string", "description": "Description of the specific work"},
            },
            "required": ["job_type", "state"],
        },
    },
    {
        "name": "check_licence_requirements",
        "description": "Check compliance requirements for a job type in a state before quoting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "state":    {"type": "string", "description": "Australian state abbreviation"},
                "category": {"type": "string", "description": "Trade category"},
                "job_type": {"type": "string", "description": "residential or commercial"},
            },
            "required": ["state", "category"],
        },
    },
    {
        "name": "update_job_preference",
        "description": "Update the tradie's job preferences — what types of leads they want to receive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "accept_high_intent": {"type": "boolean", "description": "Accept ready-to-hire leads"},
                "accept_planning":    {"type": "boolean", "description": "Accept planning-stage leads"},
                "accept_residential": {"type": "boolean", "description": "Accept residential jobs"},
                "accept_commercial":  {"type": "boolean", "description": "Accept commercial jobs"},
            },
            "required": [],
        },
    },
    {
        "name": "get_my_categories",
        "description": "Get the trade categories the tradie is registered for.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

SHARED_TOOLS = [
    {
        "name": "get_categories",
        "description": "Get all available trade categories on the platform.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]