/**
 * Problem suggestions with auto-detected categories.
 * Category names MUST match TRADIE_CATEGORIES[].name exactly so that
 * getCategorySlug() resolves them to the correct DB slug.
 */
export const PROBLEM_SUGGESTIONS: { problem: string; category: string; icon: string }[] = [
  // Plumbing
  { problem: 'Fix a leaking tap',                      category: 'Plumbing',                   icon: '🚿' },
  { problem: 'Unblock a drain or toilet',              category: 'Plumbing',                   icon: '🚽' },
  { problem: 'Hot water system not working',           category: 'Plumbing',                   icon: '🌡️' },
  { problem: 'Burst or leaking pipe',                  category: 'Plumbing',                   icon: '💧' },
  { problem: 'Low water pressure',                     category: 'Plumbing',                   icon: '💦' },
  { problem: 'Install a new tap or shower',            category: 'Plumbing',                   icon: '🚿' },
  { problem: 'Bathroom plumbing renovation',           category: 'Plumbing',                   icon: '🛁' },
  // Electrical
  { problem: 'Power point not working',                category: 'Electrical',                 icon: '🔌' },
  { problem: 'Lights flickering or not working',       category: 'Electrical',                 icon: '💡' },
  { problem: 'Safety switch keeps tripping',           category: 'Electrical',                 icon: '⚡' },
  { problem: 'Install a ceiling fan',                  category: 'Electrical',                 icon: '🌀' },
  { problem: 'Install downlights or LED lighting',     category: 'Electrical',                 icon: '💡' },
  { problem: 'Switchboard upgrade or replacement',     category: 'Electrical',                 icon: '🔋' },
  // Painting & Decorating
  { problem: 'Paint interior walls and ceilings',      category: 'Painting & Decorating',      icon: '🎨' },
  { problem: 'Paint exterior of house',                category: 'Painting & Decorating',      icon: '🏠' },
  { problem: 'Paint fence or deck',                    category: 'Painting & Decorating',      icon: '🖌️' },
  // Carpentry & Joinery
  { problem: 'Build or repair a deck',                 category: 'Carpentry & Joinery',        icon: '🪵' },
  { problem: 'Install shelving or wardrobes',          category: 'Carpentry & Joinery',        icon: '🗄️' },
  { problem: 'Repair or replace doors',                category: 'Carpentry & Joinery',        icon: '🚪' },
  { problem: 'Build a pergola or outdoor area',        category: 'Carpentry & Joinery',        icon: '🏡' },
  // Tiling
  { problem: 'Replace cracked bathroom tiles',         category: 'Tiling',                     icon: '🧱' },
  { problem: 'Tile a bathroom or kitchen',             category: 'Tiling',                     icon: '🛁' },
  { problem: 'Regrout floor or wall tiles',            category: 'Tiling',                     icon: '🔲' },
  // Roofing
  { problem: 'Fix a leaking roof',                     category: 'Roofing',                    icon: '🏠' },
  { problem: 'Clean or replace gutters',               category: 'Roofing',                    icon: '🌧️' },
  { problem: 'Replace damaged roof tiles',             category: 'Roofing',                    icon: '🏚️' },
  // Landscaping & Gardening
  { problem: 'Regular lawn mowing and maintenance',    category: 'Landscaping & Gardening',    icon: '🌿' },
  { problem: 'Garden clean-up and weeding',            category: 'Landscaping & Gardening',    icon: '🌱' },
  { problem: 'Design and install a new garden',        category: 'Landscaping & Gardening',    icon: '🌳' },
  { problem: 'Tree removal or pruning',                category: 'Landscaping & Gardening',    icon: '🌲' },
  // Air Conditioning & Heating
  { problem: 'Install a split system air conditioner', category: 'Air Conditioning & Heating', icon: '❄️' },
  { problem: 'Air con service or repair',              category: 'Air Conditioning & Heating', icon: '🌡️' },
  { problem: 'Ducted air conditioning installation',   category: 'Air Conditioning & Heating', icon: '❄️' },
  { problem: 'Heating system install or repair',       category: 'Air Conditioning & Heating', icon: '🔥' },
  // Fencing & Gates
  { problem: 'Build or replace a fence',               category: 'Fencing & Gates',            icon: '🔩' },
  { problem: 'Repair damaged fence panels or posts',   category: 'Fencing & Gates',            icon: '🔧' },
  { problem: 'Install or automate a driveway gate',    category: 'Fencing & Gates',            icon: '🚗' },
  // Pest Control
  { problem: 'Termite inspection or treatment',        category: 'Pest Control',               icon: '🐛' },
  { problem: 'General pest control treatment',         category: 'Pest Control',               icon: '🐜' },
  // Handyman
  { problem: 'General handyman repairs',               category: 'Handyman',                   icon: '🔨' },
  { problem: 'Assemble flat-pack furniture',           category: 'Handyman',                   icon: '🪑' },
  { problem: 'Fix or patch holes in walls',            category: 'Handyman',                   icon: '🧱' },
  { problem: 'TV wall mounting',                       category: 'Handyman',                   icon: '📺' },
  // Solar & Renewable Energy
  { problem: 'Install solar panels',                   category: 'Solar & Renewable Energy',   icon: '☀️' },
  { problem: 'Install a home battery system',          category: 'Solar & Renewable Energy',   icon: '🔋' },
  // Concreting & Paving
  { problem: 'Pour a concrete driveway or path',       category: 'Concreting & Paving',        icon: '🛣️' },
  { problem: 'Lay bricks or pavers',                   category: 'Concreting & Paving',        icon: '🟫' },
  // Plastering
  { problem: 'Repair cracked or damaged plaster',      category: 'Plastering',                 icon: '🏗️' },
  { problem: 'Install new plasterboard or cornice',    category: 'Plastering',                 icon: '🔲' },
  // Glazing & Window Repairs
  { problem: 'Replace a broken window',                category: 'Glazing & Window Repairs',   icon: '🪟' },
  { problem: 'Install a shower screen',                category: 'Glazing & Window Repairs',   icon: '🚿' },
  // Flooring
  { problem: 'Install timber or hybrid flooring',      category: 'Flooring',                   icon: '🪜' },
  { problem: 'Lay carpet or vinyl flooring',           category: 'Flooring',                   icon: '🏠' },
  { problem: 'Sand and polish timber floors',          category: 'Flooring',                   icon: '✨' },
  // Gas Fitting
  { problem: 'Connect a gas cooktop or oven',          category: 'Gas Fitting',                icon: '🍳' },
  { problem: 'Gas leak detection or repair',           category: 'Gas Fitting',                icon: '⚠️' },
  // Cleaning
  { problem: 'End of lease or bond clean',             category: 'Cleaning',                   icon: '🧹' },
  { problem: 'Deep clean or builders clean',           category: 'Cleaning',                   icon: '🧽' },
  { problem: 'Pressure wash driveway or deck',         category: 'Cleaning',                   icon: '💦' },
  // Security Systems
  { problem: 'Install security cameras (CCTV)',        category: 'Security Systems',            icon: '📷' },
  { problem: 'Install an alarm system',                category: 'Security Systems',            icon: '🔔' },
  // Bathroom Renovation
  { problem: 'Full bathroom renovation',               category: 'Bathroom Renovation',         icon: '🛁' },
  { problem: 'Replace vanity or shower',               category: 'Bathroom Renovation',         icon: '🚿' },
  // Kitchen Renovation
  { problem: 'Full kitchen renovation',                category: 'Kitchen Renovation',          icon: '🍳' },
  { problem: 'Replace kitchen cabinets or benchtops',  category: 'Kitchen Renovation',          icon: '🔪' },
  // Building & Construction
  { problem: 'Build a home extension or addition',     category: 'Building & Construction',     icon: '🏗️' },
  { problem: 'Granny flat construction',               category: 'Building & Construction',     icon: '🏠' },
  // Waterproofing
  { problem: 'Waterproof a bathroom or laundry',       category: 'Waterproofing',               icon: '💧' },
  { problem: 'Waterproof a deck or balcony',           category: 'Waterproofing',               icon: '🌊' },
  // Demolition
  { problem: 'Demolish a garage or structure',         category: 'Demolition',                  icon: '🔨' },
];

/**
 * Keyword → canonical category name mapping.
 * detectCategory() returns names that match TRADIE_CATEGORIES[].name exactly.
 */
export const CATEGORY_KEYWORDS: [string[], string][] = [
  // Specific phrases first, so broad words like "shower", "screen", "panel", or "floor"
  // do not steal jobs from the service the user actually described.
  [['shower screen', 'window glass', 'broken window', 'glazing', 'glass door', 'mirror install', 'splashback glass', 'double glaz'], 'Glazing & Window Repairs'],
  [['bathroom reno', 'bathroom renovation', 'ensuite', 'vanity', 'shower replace', 'bath replace'], 'Bathroom Renovation'],
  [['kitchen reno', 'kitchen renovation', 'cabinet replace', 'benchtop', 'kitchen install'], 'Kitchen Renovation'],
  [['solar', 'solar panel', 'photovoltaic', 'battery storage', 'home battery', 'pv system'], 'Solar & Renewable Energy'],
  [['gas fitting', 'gas fitter', 'gas leak', 'gas appliance', 'gas cooktop', 'gas oven', 'gas heater', 'gas bbq', 'gas line'], 'Gas Fitting'],
  [['air con', 'aircon', 'air conditioning', 'hvac', 'heating system', 'cooling', 'split system', 'ducted', 'heat pump', 'evaporative'], 'Air Conditioning & Heating'],
  [['security camera', 'alarm', 'cctv', 'camera', 'security system', 'intercom', 'deadbolt', 'smart lock', 'access control'], 'Security Systems'],
  [['tap', 'drain', 'pipe', 'plumb', 'toilet', 'hot water', 'burst pipe', 'sewage', 'blocked drain', 'water heater', 'cistern', 'low water pressure', 'stormwater'], 'Plumbing'],
  [['electr', 'electrician', 'power point', 'light', 'switch', 'wir', 'circuit', 'fan', 'switchboard', 'downlight', 'powerpoint', 'ev charger', 'data point', 'smoke alarm'], 'Electrical'],
  [['painting', 'paint exterior', 'paint interior', 'wall paint', 'colour', 'color', 'wallpaper', 'exterior paint', 'interior paint', 'roof painting'], 'Painting & Decorating'],
  [['tile', 'tiling', 'grout', 'regrout', 'mosaic', 'splashback tile'], 'Tiling'],
  [['roof', 'gutter', 'ceiling leak', 'fascia', 'downpipe', 'colorbond roof', 'roof tile', 'skylight', 'flashing'], 'Roofing'],
  [['garden', 'lawn', 'mow', 'hedge', 'landscap', 'weed', 'turf', 'retaining wall', 'irrigation', 'tree removal', 'tree trim', 'prune', 'stump grinding'], 'Landscaping & Gardening'],
  [['fence', 'fencing', 'gate', 'pool fence', 'driveway gate', 'colorbond'], 'Fencing & Gates'],
  [['carpentr', 'timber', 'wood', 'deck', 'shelf', 'pergola', 'wardrobe', 'door', 'cabinet', 'built-in', 'joinery', 'frame', 'stair', 'balustrade'], 'Carpentry & Joinery'],
  [['pest', 'termite', 'rodent', 'cockroach', 'ant', 'spider', 'possum'], 'Pest Control'],
  [['handyman', 'assembly', 'flat.?pack', 'furniture assem', 'odd job', 'tv mount', 'minor repair', 'general repair'], 'Handyman'],
  [['concrete', 'driveway', 'concreting', 'paving', 'paver', 'brick path', 'slab', 'resurfacing'], 'Concreting & Paving'],
  [['plaster', 'cornice', 'render', 'gyprock', 'plasterboard', 'hole in wall'], 'Plastering'],
  [['floor', 'timber floor', 'hybrid floor', 'carpet', 'vinyl floor', 'laminate', 'floor sand', 'floor polish'], 'Flooring'],
  [['clean', 'bond clean', 'end of lease', 'deep clean', 'builders clean', 'pressure wash', 'window clean', 'carpet clean'], 'Cleaning'],
  [['extension', 'addition', 'granny flat', 'building work', 'structural'], 'Building & Construction'],
  [['waterproof', 'wet area', 'deck waterproof', 'balcony waterproof'], 'Waterproofing'],
  [['demolition', 'demolish', 'knockdown', 'site clearance'], 'Demolition'],
];

/**
 * Detect a canonical category from free text.
 * Returns the TRADIE_CATEGORIES display name or '' if not detected.
 */
export function detectCategory(text: string): string {
  const lower = text.toLowerCase();
  for (const [keywords, category] of CATEGORY_KEYWORDS) {
    if (keywords.some(k => new RegExp(k).test(lower))) return category;
  }
  return '';
}
