"""
backend/seeds/seed_categories.py

Full 3-level Australian trades taxonomy seed.

Run ONCE after both migrations have been applied:
    cd backend
    python -m seeds.seed_categories

Structure:
  Level 1 — Trade category      (users see these in the booking wizard step 1)
  Level 2 — Subcategory         (users pick one after selecting a trade)
  Level 3 — Specific task       (optional — pre-fills the job title)
  ServiceQuestions              (attached at level-2; answers stored as JSONB on Job.brief_answers)

Australian state licence registry URLs (used in Django admin for manual verification):
  VIC  — VBA:             https://www.vba.vic.gov.au/plumbing/licence-registration-search
  NSW  — NSW Fair Trading: https://www.onlineservices.fairtrading.nsw.gov.au/
  QLD  — QBCC:            https://www.qbcc.qld.gov.au/licence-search
  WA   — Building Commission: https://www.bsc.wa.gov.au/
  SA   — CBS:             https://www.cbs.sa.gov.au/
  TAS  — CBOS:            https://www.cbos.tas.gov.au/
  NT   — NT.GOV:          https://nt.gov.au/industry/
  ACT  — Access Canberra: https://www.accesscanberra.act.gov.au/
"""
import asyncio
import uuid
from db.session import AsyncSessionLocal
from models.category import Category, CategoryLevel
from models.service_question import ServiceQuestion, AnswerType
from sqlalchemy import select


# ─────────────────────────────────────────────────────────────────────────────
# TAXONOMY DATA
# Each entry: (slug, name, icon_slug, description)
# ─────────────────────────────────────────────────────────────────────────────

LEVEL1_TRADES = [
    ("plumbing",              "Plumbing",                    "plumbing",       "Licensed plumbing work including pipes, drains, hot water and gas plumbing"),
    ("electrical",            "Electrical",                  "electrical",     "Licensed electrical work including wiring, switchboards and solar"),
    ("carpentry",             "Carpentry & Joinery",         "carpentry",      "Structural and decorative timber work, doors, frames, decking"),
    ("painting",              "Painting & Decorating",       "painting",       "Interior and exterior painting, wallpapering and surface preparation"),
    ("tiling",                "Tiling",                      "tiling",         "Floor and wall tiling, waterproofing, grout and restoration"),
    ("roofing",               "Roofing",                     "roofing",        "Roof installation, repair, guttering and downpipes"),
    ("hvac",                  "Air Conditioning & Heating",  "hvac",           "Supply and install of split systems, ducted AC and heating units"),
    ("landscaping",           "Landscaping & Gardening",     "landscaping",    "Garden design, lawn care, retaining walls and irrigation"),
    ("concreting",            "Concreting & Paving",         "concreting",     "Driveways, paths, patios and concrete slabs"),
    ("plastering",            "Plastering",                  "plastering",     "Cornice, wall and ceiling plaster, render and patching"),
    ("flooring",              "Flooring",                    "flooring",       "Timber, hybrid, carpet and vinyl floor supply and installation"),
    ("fencing",               "Fencing & Gates",             "fencing",        "Timber, colorbond, pool and glass fencing and gate installation"),
    ("glazing",               "Glazing & Window Repairs",    "glazing",        "Window and door glass replacement, splashbacks and mirrors"),
    ("pest-control",          "Pest Control",                "pest-control",   "Termite inspection and treatment, general pest management"),
    ("security",              "Security Systems",            "security",       "Alarm systems, CCTV, intercoms and access control"),
    ("solar",                 "Solar & Renewable Energy",    "solar",          "Solar panel supply and installation, battery storage systems"),
    ("gas-fitting",           "Gas Fitting",                 "gas-fitting",    "Licensed gas appliance installation, repair and leak detection"),
    ("demolition",            "Demolition",                  "demolition",     "Residential and commercial demolition and site clearance"),
    ("waterproofing",         "Waterproofing",               "waterproofing",  "Wet area, deck, balcony and below-slab waterproofing"),
    ("cleaning",              "Cleaning",                    "cleaning",       "End of lease, bond, builders and deep cleaning services"),
    ("handyman",              "Handyman",                    "handyman",       "General repairs, flat-pack assembly, odd jobs and maintenance"),
    ("building",              "Building & Construction",     "building",       "Residential extensions, renovations and structural building work"),
    ("air-conditioning",      "Air Conditioning",            "hvac",           "Split system, ducted and portable air conditioning installation and repair"),
    ("bathroom-renovation",   "Bathroom Renovation",         "bathroom",       "Full bathroom and ensuite renovations"),
    ("kitchen-renovation",    "Kitchen Renovation",          "kitchen",        "Full kitchen renovations and cabinet installation"),
]

# ── Level 2: subcategories per Level 1 ───────────────────────────────────────
# Format: { level1_slug: [(slug, name, description), ...] }

LEVEL2_SUBCATEGORIES = {
    "plumbing": [
        ("plumbing-hot-water",       "Hot Water Systems",         "Hot water system supply, installation and repair"),
        ("plumbing-blocked-drains",  "Blocked Drains",            "Drain clearing, CCTV inspection and high-pressure jetting"),
        ("plumbing-leak-repair",     "Leak Detection & Repair",   "Finding and fixing leaks in pipes, taps and fittings"),
        ("plumbing-bathroom",        "Bathroom Plumbing",         "Toilet, basin, shower and bath installation and repair"),
        ("plumbing-kitchen",         "Kitchen Plumbing",          "Sink, dishwasher and kitchen tap plumbing"),
        ("plumbing-stormwater",      "Stormwater & Drainage",     "Stormwater drains, sumps and surface drainage"),
        ("plumbing-gas",             "Gas Plumbing",              "Gas line installation, appliance connection and leak repair"),
        ("plumbing-pipe-relining",   "Pipe Relining",             "No-dig pipe relining and structural pipe repair"),
    ],
    "electrical": [
        ("electrical-switchboard",   "Switchboard Upgrades",      "Meter box and switchboard upgrades and rewiring"),
        ("electrical-power-points",  "Power Points & Lighting",   "Power point installation, light fitting and LED upgrades"),
        ("electrical-solar",         "Solar Electrical",          "Solar inverter installation and grid connection"),
        ("electrical-ev-charger",    "EV Charger Installation",   "Home EV charger supply and installation"),
        ("electrical-safety",        "Electrical Safety Checks",  "RCD testing, safety inspections and smoke alarm installation"),
        ("electrical-data",          "Data & Communications",     "Data points, NBN, CCTV and structured cabling"),
        ("electrical-outdoor",       "Outdoor & Garden Lighting", "Garden, deck, driveway and security lighting"),
        ("electrical-fault-finding", "Fault Finding & Repair",    "Tripping circuits, dead power points and wiring faults"),
    ],
    "carpentry": [
        ("carpentry-decking",        "Decking",                   "Timber and composite deck construction and repair"),
        ("carpentry-doors-windows",  "Doors & Windows",           "Door and window installation, frames and jambs"),
        ("carpentry-framing",        "Structural Framing",        "Wall framing, floor joists and structural carpentry"),
        ("carpentry-cabinets",       "Cabinetry & Built-ins",     "Custom built-in wardrobes, shelving and cabinet installation"),
        ("carpentry-stairs",         "Stairs & Balustrades",      "Staircase construction and balustrade installation"),
        ("carpentry-pergola",        "Pergolas & Carports",       "Pergola, carport and shade structure construction"),
        ("carpentry-cladding",       "Cladding & Linings",        "Internal and external wall cladding installation"),
    ],
    "painting": [
        ("painting-interior",        "Interior Painting",         "Walls, ceilings, trims and feature walls"),
        ("painting-exterior",        "Exterior Painting",         "House exterior, fence, eaves and fascia painting"),
        ("painting-roof",            "Roof Painting",             "Roof restoration and painting"),
        ("painting-commercial",      "Commercial Painting",       "Office, retail and commercial space painting"),
        ("painting-render",          "Render Painting",           "Painting over rendered surfaces"),
        ("painting-wallpaper",       "Wallpaper Installation",    "Wallpaper hanging, removal and preparation"),
    ],
    "roofing": [
        ("roofing-repair",           "Roof Repairs",              "Broken tiles, flashing, ridge capping and leak repair"),
        ("roofing-replacement",      "Roof Replacement",          "Full roof replacement in tile, colorbond or metal"),
        ("roofing-gutters",          "Gutters & Downpipes",       "Gutter installation, repair, cleaning and downpipes"),
        ("roofing-skylights",        "Skylight Installation",     "Skylight and roof window supply and installation"),
        ("roofing-insulation",       "Roof Insulation",           "Roof space insulation installation and upgrades"),
    ],
    "hvac": [
        ("hvac-split-install",       "Split System Installation", "Wall-mounted split system supply and installation"),
        ("hvac-ducted",              "Ducted Air Conditioning",   "Ducted system installation and duct replacement"),
        ("hvac-service",             "AC Service & Repair",       "Air conditioning servicing, cleaning and fault repair"),
        ("hvac-evaporative",         "Evaporative Cooling",       "Evaporative cooler installation and service"),
        ("hvac-heating",             "Heating Systems",           "Gas ducted heating and hydronic heating installation"),
    ],
    "landscaping": [
        ("landscaping-design",       "Garden Design",             "Full garden design and landscape planning"),
        ("landscaping-lawn",         "Lawn & Turf",               "Turf laying, lawn care and lawn mowing"),
        ("landscaping-retaining",    "Retaining Walls",           "Timber, sleeper and block retaining wall construction"),
        ("landscaping-irrigation",   "Irrigation Systems",        "Irrigation system design, installation and repair"),
        ("landscaping-tree",         "Tree Services",             "Tree removal, pruning and stump grinding"),
        ("landscaping-paving",       "Garden Paving",             "Garden path and patio paving in brick or stone"),
    ],
    "concreting": [
        ("concreting-driveway",      "Driveways",                 "Concrete driveway supply and pour"),
        ("concreting-path",          "Paths & Footpaths",         "Garden and pedestrian path concreting"),
        ("concreting-slab",          "Concrete Slabs",            "House, shed and garage slab construction"),
        ("concreting-resurfacing",   "Concrete Resurfacing",      "Concrete grinding, polishing and resurfacing"),
        ("concreting-paving-bricks", "Brick & Paver Driveways",   "Brick and paver driveway and path installation"),
    ],
    "plastering": [
        ("plastering-walls",         "Wall & Ceiling Plaster",    "Plasterboard installation, jointing and set"),
        ("plastering-cornice",       "Cornice & Mouldings",       "Plaster cornice and decorative moulding installation"),
        ("plastering-render",        "External Render",           "External wall render application"),
        ("plastering-patch",         "Patch & Repair",            "Hole filling, crack repair and surface prep"),
    ],
    "flooring": [
        ("flooring-timber",          "Timber Flooring",           "Solid and engineered timber floor supply and installation"),
        ("flooring-hybrid",          "Hybrid & Laminate",         "Hybrid and laminate plank installation"),
        ("flooring-carpet",          "Carpet",                    "Carpet supply and installation"),
        ("flooring-vinyl",           "Vinyl & Sheet Flooring",    "Vinyl plank and sheet flooring installation"),
        ("flooring-polish",          "Floor Sanding & Polishing", "Timber floor sanding, staining and polishing"),
    ],
    "fencing": [
        ("fencing-colorbond",        "Colorbond Fencing",         "Colorbond steel fence supply and installation"),
        ("fencing-timber",           "Timber Fencing",            "Timber paling and picket fence construction"),
        ("fencing-pool",             "Pool Fencing",              "Glass and aluminium pool fence supply and install"),
        ("fencing-retaining",        "Retaining Fence",           "Combined retaining wall and fence structures"),
        ("fencing-gates",            "Gates & Automation",        "Driveway gate supply, installation and motor automation"),
    ],
    "glazing": [
        ("glazing-window-repair",    "Window Glass Repair",       "Broken window glass replacement"),
        ("glazing-shower",           "Shower Screens",            "Frameless and semi-frameless shower screen installation"),
        ("glazing-splashback",       "Glass Splashbacks",         "Kitchen and bathroom glass splashback supply and install"),
        ("glazing-mirrors",          "Mirror Installation",       "Large format and custom mirror installation"),
        ("glazing-double-glaze",     "Double Glazing",            "Double glazed window upgrade and installation"),
    ],
    "pest-control": [
        ("pest-termite",             "Termite Inspection",        "Termite inspection, treatment and management plans"),
        ("pest-general",             "General Pest Treatment",    "Cockroaches, ants, spiders, rodents and wasps"),
        ("pest-possum",              "Possum Removal",            "Possum removal and roof entry point sealing"),
        ("pest-bird",                "Bird & Pigeon Control",     "Bird deterrent installation and removal"),
    ],
    "security": [
        ("security-alarm",           "Alarm Systems",             "Intruder alarm system supply and installation"),
        ("security-cctv",            "CCTV & Cameras",            "Security camera and surveillance system installation"),
        ("security-intercom",        "Intercoms & Access",        "Intercom and access control system installation"),
        ("security-locks",           "Locks & Deadbolts",         "Deadbolt, smart lock and door lock installation"),
    ],
    "solar": [
        ("solar-panels",             "Solar Panel Installation",  "Rooftop solar panel system supply and installation"),
        ("solar-battery",            "Battery Storage",           "Home battery system supply and installation"),
        ("solar-hot-water",          "Solar Hot Water",           "Solar hot water system supply and installation"),
        ("solar-maintenance",        "Solar System Maintenance",  "Solar system cleaning, inspection and fault repair"),
    ],
    "gas-fitting": [
        ("gas-appliance",            "Appliance Installation",    "Gas cooktop, oven, heater and BBQ connection"),
        ("gas-leak",                 "Gas Leak Detection",        "Gas leak detection and emergency pipe repair"),
        ("gas-line",                 "Gas Line Installation",     "New gas line supply and connection"),
        ("gas-hot-water",            "Gas Hot Water",             "Gas hot water system installation and repair"),
    ],
    "building": [
        ("building-extension",       "Home Extensions",           "Single and double storey home extensions"),
        ("building-renovation",      "Renovations",               "Internal renovation, reconfiguration and structural changes"),
        ("building-granny-flat",     "Granny Flats",              "Detached and attached granny flat construction"),
        ("building-shed",            "Sheds & Garages",           "Steel and timber garage and shed construction"),
    ],
    "cleaning": [
        ("cleaning-end-of-lease",    "End of Lease Cleaning",     "Complete bond and end of lease clean"),
        ("cleaning-builders",        "Builders Clean",            "Post-construction dust and debris cleaning"),
        ("cleaning-deep",            "Deep Cleaning",             "Full house deep clean and sanitisation"),
        ("cleaning-windows",         "Window Cleaning",           "Internal and external window cleaning"),
        ("cleaning-pressure",        "Pressure Washing",          "Driveway, deck, roof and wall pressure washing"),
        ("cleaning-carpet",          "Carpet Steam Cleaning",     "Professional carpet steam clean and stain treatment"),
    ],
    "bathroom-renovation": [
        ("bathroom-full-reno",       "Full Bathroom Renovation",  "Complete bathroom strip-out and rebuild"),
        ("bathroom-ensuite",         "Ensuite Renovation",        "Ensuite strip-out and rebuild"),
        ("bathroom-vanity",          "Vanity & Basin",            "Vanity unit replacement and basin installation"),
        ("bathroom-shower",          "Shower Replacement",        "Remove existing shower and install new"),
    ],
    "kitchen-renovation": [
        ("kitchen-full-reno",        "Full Kitchen Renovation",   "Complete kitchen strip-out and rebuild"),
        ("kitchen-cabinets",         "Cabinet Replacement",       "Kitchen cabinet and benchtop replacement"),
        ("kitchen-splashback",       "Splashback Installation",   "Tile or glass splashback supply and install"),
        ("kitchen-appliances",       "Appliance Installation",    "Dishwasher, oven and cooktop installation"),
    ],
    "handyman": [
        ("handyman-flatpack",        "Flat Pack Assembly",        "IKEA, flat-pack furniture assembly"),
        ("handyman-repairs",         "General Repairs",           "Door handles, hinges, shelves and minor repairs"),
        ("handyman-tv-mounting",     "TV Mounting",               "TV wall bracket supply and installation"),
        ("handyman-gutter-clean",    "Gutter Cleaning",           "Gutter clearing and downpipe flush"),
        ("handyman-painting-minor",  "Minor Painting",            "Touch-up painting, single room or feature wall"),
    ],
}

# ── Service Questions per Level-2 subcategory ─────────────────────────────────
# Format: { subcategory_slug: [ (question_text, answer_type, options, placeholder, is_required, sort_order) ] }

SERVICE_QUESTIONS = {
    "plumbing-hot-water": [
        ("What type of hot water system do you have?", AnswerType.SELECT,
         ["Electric storage", "Gas storage", "Gas continuous flow", "Heat pump", "Solar", "Not sure"],
         None, True, 0),
        ("What is the issue?", AnswerType.SELECT,
         ["No hot water", "Not enough hot water", "Water too hot", "Leaking", "Strange noise", "Want to upgrade"],
         None, True, 1),
        ("How old is the system approximately?", AnswerType.SELECT,
         ["Less than 5 years", "5–10 years", "10+ years", "Not sure"],
         None, False, 2),
        ("Is the system accessible (not inside a wall or locked cabinet)?", AnswerType.BOOLEAN,
         None, None, True, 3),
        ("Upload a photo of the current system if possible", AnswerType.PHOTO,
         None, "Photo helps the tradie quote accurately", False, 4),
    ],
    "plumbing-blocked-drains": [
        ("Which drain is blocked?", AnswerType.SELECT,
         ["Kitchen sink", "Bathroom sink", "Shower", "Toilet", "Laundry", "External drain", "Multiple drains"],
         None, True, 0),
        ("How severe is the blockage?", AnswerType.SELECT,
         ["Completely blocked — no flow", "Draining very slowly", "Gurgling but still draining", "Overflowing"],
         None, True, 1),
        ("Is there any sewage smell or visible water backing up?", AnswerType.BOOLEAN,
         None, None, True, 2),
        ("How long has it been blocked?", AnswerType.SELECT,
         ["Just happened", "1–2 days", "3–7 days", "More than a week"],
         None, False, 3),
    ],
    "plumbing-leak-repair": [
        ("Where is the leak coming from?", AnswerType.SELECT,
         ["Tap", "Pipe under sink", "Pipe in wall", "Toilet", "Shower", "Hot water system", "Not sure"],
         None, True, 0),
        ("How serious is the leak?", AnswerType.SELECT,
         ["Just dripping", "Steady stream", "Spraying / burst pipe", "Damp patch / suspected leak"],
         None, True, 1),
        ("Have you been able to turn off the water supply?", AnswerType.BOOLEAN,
         None, None, True, 2),
        ("Upload a photo of the leak area", AnswerType.PHOTO,
         None, "Clear photo helps the tradie prepare the right parts", False, 3),
    ],
    "electrical-switchboard": [
        ("Why do you need a switchboard upgrade?", AnswerType.SELECT,
         ["Tripping breakers", "Old fuse wire board", "Adding more circuits", "Solar installation", "Safety inspection failed", "Not sure"],
         None, True, 0),
        ("Is your current board a fuse wire type (ceramic fuses)?", AnswerType.BOOLEAN,
         None, None, True, 1),
        ("How many people live in the property?", AnswerType.SELECT,
         ["1–2", "3–4", "5+"],
         None, False, 2),
        ("Are there any specific appliances you're adding (e.g. EV charger, spa, AC)?", AnswerType.TEXT,
         None, "List any high-draw appliances being added", False, 3),
    ],
    "electrical-power-points": [
        ("What do you need done?", AnswerType.MULTISELECT,
         ["Add new power point", "Move existing power point", "Replace damaged power point", "Add USB power point", "Install new light fitting", "Replace light fitting", "Install dimmer switch"],
         None, True, 0),
        ("How many points / fittings are involved?", AnswerType.NUMBER,
         {"min": 1, "max": 50, "unit": "items"},
         "Enter number of items", True, 1),
        ("Is the area where work is needed accessible (not behind tiles or concrete)?", AnswerType.BOOLEAN,
         None, None, True, 2),
    ],
    "hvac-split-install": [
        ("Is this a new installation or a replacement?", AnswerType.SELECT,
         ["New installation — no existing unit", "Replacing an existing unit"],
         None, True, 0),
        ("What size room is the unit for?", AnswerType.SELECT,
         ["Small bedroom (< 15m²)", "Medium bedroom (15–25m²)", "Living room (25–40m²)", "Open plan (40–60m²)", "Large open plan (60m²+)"],
         None, True, 1),
        ("Do you have a preference for brand?", AnswerType.TEXT,
         None, "e.g. Daikin, Mitsubishi, Fujitsu — or leave blank for tradie recommendation", False, 2),
        ("Is there a suitable outdoor location for the compressor unit?", AnswerType.BOOLEAN,
         None, None, True, 3),
        ("Upload a photo of the wall where the indoor unit will go", AnswerType.PHOTO,
         None, None, False, 4),
    ],
    "roofing-repair": [
        ("What type of roof do you have?", AnswerType.SELECT,
         ["Concrete tile", "Terracotta tile", "Colorbond / metal", "Corrugated iron", "Slate", "Not sure"],
         None, True, 0),
        ("What is the problem?", AnswerType.MULTISELECT,
         ["Leaking in rain", "Broken / cracked tiles", "Damaged flashing", "Sagging section", "Ridge capping loose", "Gutter damage", "Other"],
         None, True, 1),
        ("How long has the issue been occurring?", AnswerType.SELECT,
         ["Just noticed", "After recent storm", "Past few weeks", "Ongoing for months"],
         None, False, 2),
        ("Upload a photo of the damaged area if accessible", AnswerType.PHOTO,
         None, "Safety first — only if the roof is accessible from the ground", False, 3),
    ],
    "carpentry-decking": [
        ("Is this a new deck or repair / replacement?", AnswerType.SELECT,
         ["Brand new deck", "Repair existing deck", "Replace existing deck"],
         None, True, 0),
        ("What material do you prefer?", AnswerType.SELECT,
         ["Hardwood timber", "Treated pine", "Composite / low-maintenance", "Not sure — open to advice"],
         None, True, 1),
        ("Approximate size of the deck?", AnswerType.SELECT,
         ["Small (< 15m²)", "Medium (15–30m²)", "Large (30–50m²)", "Very large (50m²+)"],
         None, True, 2),
        ("What height off the ground?", AnswerType.SELECT,
         ["Ground level / low (< 300mm)", "Raised (300mm – 1m)", "High (1m+)"],
         None, True, 3),
    ],
    "painting-interior": [
        ("What areas need painting?", AnswerType.MULTISELECT,
         ["Walls", "Ceiling", "Trims / skirting", "Doors", "Feature wall"],
         None, True, 0),
        ("How many rooms?", AnswerType.NUMBER,
         {"min": 1, "max": 30, "unit": "rooms"},
         "Enter number of rooms", True, 1),
        ("What is the current wall condition?", AnswerType.SELECT,
         ["Good — just want a colour change", "Some cracks / holes to fill", "Many imperfections — needs prep", "Previously wallpapered"],
         None, True, 2),
        ("Do you have a colour in mind?", AnswerType.TEXT,
         None, "e.g. Dulux White on White, or leave blank to discuss with tradie", False, 3),
    ],
    "painting-exterior": [
        ("What surfaces need painting?", AnswerType.MULTISELECT,
         ["Walls / render", "Fascia & eaves", "Window frames", "Fence", "Front door", "Gutters"],
         None, True, 0),
        ("What is the current condition of the surface?", AnswerType.SELECT,
         ["Good — just faded", "Peeling / flaking in areas", "Significant peeling — needs full prep", "Previously bare wood / fresh render"],
         None, True, 1),
        ("Single or double storey?", AnswerType.SELECT,
         ["Single storey", "Double storey", "Mix — part single part double"],
         None, True, 2),
    ],
    "tiling": [
        ("What area is being tiled?", AnswerType.MULTISELECT,
         ["Bathroom floor", "Bathroom walls", "Shower recess", "Kitchen splashback", "Living / dining floor", "Outdoor / alfresco"],
         None, True, 0),
        ("Approximate area in square metres?", AnswerType.NUMBER,
         {"min": 1, "max": 500, "unit": "m²"},
         "Enter total area in square metres", True, 1),
        ("Do you have tiles already selected / purchased?", AnswerType.SELECT,
         ["Yes — tiles are ready", "No — need tradie to supply", "Not yet — open to advice"],
         None, True, 2),
        ("Is there existing tiling to remove?", AnswerType.BOOLEAN,
         None, None, True, 3),
    ],
    "cleaning-end-of-lease": [
        ("How many bedrooms?", AnswerType.NUMBER,
         {"min": 1, "max": 10, "unit": "bedrooms"},
         "Enter number of bedrooms", True, 0),
        ("How many bathrooms?", AnswerType.NUMBER,
         {"min": 1, "max": 10, "unit": "bathrooms"},
         "Enter number of bathrooms", True, 1),
        ("Do you need carpet steam cleaning as well?", AnswerType.BOOLEAN,
         None, None, True, 2),
        ("Do you need oven cleaning included?", AnswerType.BOOLEAN,
         None, None, True, 3),
        ("Is the property furnished or unfurnished?", AnswerType.SELECT,
         ["Unfurnished / empty", "Partially furnished", "Fully furnished"],
         None, True, 4),
    ],
    "fencing-colorbond": [
        ("What do you need?", AnswerType.SELECT,
         ["New fence — no existing", "Replace existing fence", "Extend existing fence", "Repair / partial replacement"],
         None, True, 0),
        ("Approximate length of fence run?", AnswerType.NUMBER,
         {"min": 1, "max": 500, "unit": "metres"},
         "Enter approximate length in metres", True, 1),
        ("What height do you need?", AnswerType.SELECT,
         ["1.2m (boundary / garden)", "1.5m (standard boundary)", "1.8m (privacy / security)", "2.1m (high security)"],
         None, True, 2),
        ("Is the ground level or sloped?", AnswerType.SELECT,
         ["Flat / level", "Gently sloped", "Steeply sloped"],
         None, True, 3),
    ],
    "solar-panels": [
        ("Is this a new system or an upgrade / addition?", AnswerType.SELECT,
         ["Brand new — no existing solar", "Adding more panels to existing system", "Replacing faulty system"],
         None, True, 0),
        ("Do you want to include a battery?", AnswerType.BOOLEAN,
         None, None, True, 1),
        ("What is your average quarterly electricity bill?", AnswerType.SELECT,
         ["Under $300", "$300–$600", "$600–$1000", "Over $1000", "Not sure"],
         None, False, 2),
        ("What is your roof material?", AnswerType.SELECT,
         ["Colorbond / metal", "Concrete tile", "Terracotta tile", "Flat / membrane", "Not sure"],
         None, True, 3),
        ("Upload a photo of your roof and meter box if possible", AnswerType.PHOTO,
         None, "Helps the tradie assess shading and connection requirements", False, 4),
    ],
    "gas-appliance": [
        ("What appliance is being connected?", AnswerType.MULTISELECT,
         ["Gas cooktop", "Gas oven", "Gas BBQ / outdoor", "Gas heater / fireplace", "Gas dryer"],
         None, True, 0),
        ("Is this a new appliance or replacement?", AnswerType.SELECT,
         ["New appliance — no existing gas point", "Replacing existing gas appliance", "Moving existing gas point"],
         None, True, 1),
        ("Do you have the appliance already or does the tradie need to supply it?", AnswerType.SELECT,
         ["I have the appliance", "Tradie to supply — open to recommendations"],
         None, True, 2),
    ],
    "landscaping-lawn": [
        ("What lawn work do you need?", AnswerType.MULTISELECT,
         ["Regular mowing", "One-off mow", "Turf supply and lay", "Lawn renovation / scarify", "Weed and fertilise"],
         None, True, 0),
        ("Approximate lawn area?", AnswerType.NUMBER,
         {"min": 1, "max": 5000, "unit": "m²"},
         "Enter approximate area in square metres", True, 1),
        ("Is the lawn accessible by ride-on mower or hand mower only?", AnswerType.SELECT,
         ["Ride-on accessible", "Hand mower only — tight / sloped", "Not sure"],
         None, False, 2),
    ],
    "building-extension": [
        ("What type of extension?", AnswerType.SELECT,
         ["Single storey extension", "Second storey addition", "Garage conversion", "Carport enclosure", "Other"],
         None, True, 0),
        ("Do you have council-approved plans?", AnswerType.SELECT,
         ["Yes — DA / CDC approved", "Plans drawn but not yet approved", "No plans yet — need full service"],
         None, True, 1),
        ("Approximate floor area being added?", AnswerType.NUMBER,
         {"min": 5, "max": 500, "unit": "m²"},
         "Enter approximate floor area in square metres", True, 2),
        ("What is your approximate budget?", AnswerType.SELECT,
         ["Under $50,000", "$50,000–$100,000", "$100,000–$200,000", "$200,000+", "Not sure yet"],
         None, False, 3),
    ],
    "bathroom-full-reno": [
        ("Is this a full strip-out and rebuild or partial renovation?", AnswerType.SELECT,
         ["Full strip-out and rebuild", "Partial — keeping some existing fixtures", "Cosmetic only — no plumbing / tiling changes"],
         None, True, 0),
        ("What is the approximate size of the bathroom?", AnswerType.SELECT,
         ["Small (< 4m²)", "Medium (4–7m²)", "Large (7–12m²)", "Very large (12m²+)"],
         None, True, 1),
        ("Do you have a design / fixtures selected?", AnswerType.SELECT,
         ["Yes — full design and fixtures ready", "Partial — some decisions made", "No — need tradie or designer input"],
         None, True, 2),
        ("What is your approximate budget?", AnswerType.SELECT,
         ["Under $15,000", "$15,000–$25,000", "$25,000–$40,000", "$40,000+"],
         None, False, 3),
        ("Upload photos of the existing bathroom", AnswerType.PHOTO,
         None, "Before photos help the tradie plan accurately", False, 4),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# SEED RUNNER
# ─────────────────────────────────────────────────────────────────────────────

async def seed() -> None:
    async with AsyncSessionLocal() as session:
        print("Starting category seed...")

        # ── Level 1 ───────────────────────────────────────────────
        l1_map: dict[str, str] = {}   # slug → id

        for slug, name, icon_slug, description in LEVEL1_TRADES:
            # Check if already exists (idempotent)
            existing = await session.execute(
                select(Category).where(Category.slug == slug)
            )
            cat = existing.scalar_one_or_none()
            if cat:
                l1_map[slug] = cat.id
                print(f"  [SKIP] L1 {name}")
                continue

            cat = Category(
                id=str(uuid.uuid4()),
                name=name,
                slug=slug,
                parent_id=None,
                level=CategoryLevel.TRADE,
                is_active=True,
                icon_slug=icon_slug,
                description=description,
            )
            session.add(cat)
            await session.flush()
            l1_map[slug] = cat.id
            print(f"  [ADD]  L1 {name}")

        # ── Level 2 ───────────────────────────────────────────────
        l2_map: dict[str, str] = {}   # slug → id

        for parent_slug, subcats in LEVEL2_SUBCATEGORIES.items():
            parent_id = l1_map.get(parent_slug)
            if not parent_id:
                print(f"  [WARN] parent not found for {parent_slug} — skipping subcategories")
                continue

            for slug, name, description in subcats:
                existing = await session.execute(
                    select(Category).where(Category.slug == slug)
                )
                cat = existing.scalar_one_or_none()
                if cat:
                    l2_map[slug] = cat.id
                    print(f"    [SKIP] L2 {name}")
                    continue

                cat = Category(
                    id=str(uuid.uuid4()),
                    name=name,
                    slug=slug,
                    parent_id=parent_id,
                    level=CategoryLevel.SUBCATEGORY,
                    is_active=True,
                    icon_slug=None,
                    description=description,
                )
                session.add(cat)
                await session.flush()
                l2_map[slug] = cat.id
                print(f"    [ADD]  L2 {name}")

        # ── Service Questions ──────────────────────────────────────
        for subcat_slug, questions in SERVICE_QUESTIONS.items():
            cat_id = l2_map.get(subcat_slug)
            if not cat_id:
                print(f"  [WARN] subcategory not found for questions: {subcat_slug}")
                continue

            for q_text, a_type, options, placeholder, required, sort in questions:
                existing = await session.execute(
                    select(ServiceQuestion).where(
                        ServiceQuestion.category_id == cat_id,
                        ServiceQuestion.question_text == q_text,
                    )
                )
                if existing.scalar_one_or_none():
                    print(f"      [SKIP] Q: {q_text[:50]}")
                    continue

                q = ServiceQuestion(
                    id=str(uuid.uuid4()),
                    category_id=cat_id,
                    question_text=q_text,
                    answer_type=a_type,
                    options=options,
                    placeholder=placeholder,
                    is_required=required,
                    sort_order=sort,
                )
                session.add(q)
                print(f"      [ADD]  Q: {q_text[:50]}")

        await session.commit()
        print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())