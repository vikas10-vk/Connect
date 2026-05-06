// ── Problem suggestions with auto-detected category ───────────────────────────
export const PROBLEM_SUGGESTIONS: { problem: string; category: string; icon: string }[] = [
  // Plumbing
  { problem: 'Fix a leaking tap', category: 'Plumbing', icon: '🚿' },
  { problem: 'Unblock a drain or toilet', category: 'Plumbing', icon: '🚽' },
  { problem: 'Hot water system not working', category: 'Plumbing', icon: '🌡️' },
  { problem: 'Burst or leaking pipe', category: 'Plumbing', icon: '💧' },
  { problem: 'Low water pressure', category: 'Plumbing', icon: '💦' },
  { problem: 'Install a new tap or shower', category: 'Plumbing', icon: '🚿' },
  { problem: 'Bathroom plumbing renovation', category: 'Plumbing', icon: '🛁' },
  // Electrical
  { problem: 'Power point not working', category: 'Electrical', icon: '🔌' },
  { problem: 'Lights flickering or not working', category: 'Electrical', icon: '💡' },
  { problem: 'Safety switch keeps tripping', category: 'Electrical', icon: '⚡' },
  { problem: 'Install a ceiling fan', category: 'Electrical', icon: '🌀' },
  { problem: 'Install downlights or LED lighting', category: 'Electrical', icon: '💡' },
  { problem: 'Switchboard upgrade or replacement', category: 'Electrical', icon: '🔋' },
  // Painting
  { problem: 'Paint interior walls and ceilings', category: 'Painting', icon: '🎨' },
  { problem: 'Paint exterior of house', category: 'Painting', icon: '🏠' },
  { problem: 'Paint fence or deck', category: 'Painting', icon: '🖌️' },
  // Carpentry
  { problem: 'Build or repair a deck', category: 'Carpentry', icon: '🪵' },
  { problem: 'Install shelving or wardrobes', category: 'Carpentry', icon: '🗄️' },
  { problem: 'Repair or replace doors', category: 'Carpentry', icon: '🚪' },
  { problem: 'Build a pergola or outdoor area', category: 'Carpentry', icon: '🏡' },
  // Tiling
  { problem: 'Replace cracked bathroom tiles', category: 'Tiling', icon: '🧱' },
  { problem: 'Tile a bathroom or kitchen', category: 'Tiling', icon: '🛁' },
  { problem: 'Regrout floor or wall tiles', category: 'Tiling', icon: '🔲' },
  // Roofing
  { problem: 'Fix a leaking roof', category: 'Roofing', icon: '🏠' },
  { problem: 'Clean or replace gutters', category: 'Roofing', icon: '🌧️' },
  { problem: 'Replace damaged roof tiles', category: 'Roofing', icon: '🏚️' },
  // Landscaping
  { problem: 'Regular lawn mowing and maintenance', category: 'Landscaping', icon: '🌿' },
  { problem: 'Garden clean-up and weeding', category: 'Landscaping', icon: '🌱' },
  { problem: 'Design and install a new garden', category: 'Landscaping', icon: '🌳' },
  // Air conditioning
  { problem: 'Install a split system air conditioner', category: 'Air Conditioning', icon: '❄️' },
  { problem: 'Air con service or repair', category: 'Air Conditioning', icon: '🌡️' },
  { problem: 'Ducted air conditioning installation', category: 'Air Conditioning', icon: '❄️' },
  // Fencing
  { problem: 'Build or replace a fence', category: 'Fencing', icon: '🔩' },
  { problem: 'Repair damaged fence panels or posts', category: 'Fencing', icon: '🔧' },
  // Pest control
  { problem: 'Termite inspection or treatment', category: 'Pest Control', icon: '🐛' },
  { problem: 'General pest control treatment', category: 'Pest Control', icon: '🐜' },
  // Handyman
  { problem: 'General handyman repairs', category: 'Handyman', icon: '🔨' },
  { problem: 'Assemble furniture', category: 'Handyman', icon: '🪑' },
  { problem: 'Fix or patch holes in walls', category: 'Handyman', icon: '🧱' },
  // Solar
  { problem: 'Install solar panels', category: 'Solar', icon: '☀️' },
  // Concretor
  { problem: 'Pour a concrete driveway or path', category: 'Concretor', icon: '🛣️' },
  // Plasterer
  { problem: 'Repair cracked or damaged plaster', category: 'Plasterer', icon: '🏗️' },
];

export const CATEGORY_KEYWORDS: [string[], string][] = [
  [['tap', 'drain', 'pipe', 'plumb', 'toilet', 'water', 'hot water', 'burst', 'shower', 'bath'], 'Plumbing'],
  [['electr', 'power', 'light', 'switch', 'wir', 'circuit', 'fan', 'switchboard', 'downlight'], 'Electrical'],
  [['paint', 'colour', 'color', 'wall paint', 'exterior paint', 'interior paint'], 'Painting'],
  [['tile', 'tiling', 'grout', 'regroup', 'mosaic'], 'Tiling'],
  [['roof', 'gutter', 'ceiling leak', 'fascia'], 'Roofing'],
  [['garden', 'lawn', 'mow', 'hedge', 'landscap', 'weed', 'turf'], 'Landscaping'],
  [['fence', 'gate', 'fencing'], 'Fencing'],
  [['air con', 'aircon', 'hvac', 'heating', 'cooling', 'split system', 'ducted'], 'Air Conditioning'],
  [['carpentr', 'timber', 'wood', 'deck', 'shelf', 'pergola', 'wardrobe', 'door', 'cabinet'], 'Carpentry'],
  [['pest', 'termite', 'rodent', 'cockroach', 'ant', 'spider'], 'Pest Control'],
  [['handyman', 'assembly', 'furniture', 'odd job', 'fix', 'repair'], 'Handyman'],
  [['solar', 'panel', 'photovoltaic'], 'Solar'],
  [['concrete', 'driveway', 'path', 'paving'], 'Concretor'],
  [['plaster', 'cornice', 'render'], 'Plasterer'],
];

export function detectCategory(text: string): string {
  const lower = text.toLowerCase();
  for (const [keywords, category] of CATEGORY_KEYWORDS) {
    if (keywords.some(k => lower.includes(k))) return category;
  }
  return '';
}
