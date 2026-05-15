/**
 * Canonical trade categories — exactly 24 entries matching the backend DB seed.
 * Each slug matches the Level-1 category slug in the categories table.
 *
 * DO NOT add free-form entries here. If a new trade is needed, add it to
 * backend/seeds/seed_categories.py first, then mirror it here.
 */
export interface TradieCategory {
  name: string;   // Display name shown to users
  slug: string;   // DB slug — used when posting a job
  icon: string;   // Emoji icon for the category grid
  description: string;
}

export const TRADIE_CATEGORIES: TradieCategory[] = [
  { name: 'Plumbing',                    slug: 'plumbing',             icon: '🔧', description: 'Taps, pipes, drains, hot water & gas plumbing' },
  { name: 'Electrical',                  slug: 'electrical',           icon: '⚡', description: 'Wiring, switchboards, power points & lighting' },
  { name: 'Carpentry & Joinery',         slug: 'carpentry',            icon: '🪵', description: 'Decking, doors, frames, built-ins & pergolas' },
  { name: 'Painting & Decorating',       slug: 'painting',             icon: '🎨', description: 'Interior, exterior & commercial painting' },
  { name: 'Tiling',                      slug: 'tiling',               icon: '🧱', description: 'Floor & wall tiling, waterproofing & grout' },
  { name: 'Roofing',                     slug: 'roofing',              icon: '🏠', description: 'Roof repairs, replacement, gutters & downpipes' },
  { name: 'Air Conditioning & Heating',  slug: 'hvac',                 icon: '❄️', description: 'Split systems, ducted AC, heating units & service' },
  { name: 'Landscaping & Gardening',     slug: 'landscaping',          icon: '🌿', description: 'Garden design, lawn care, irrigation & trees' },
  { name: 'Concreting & Paving',         slug: 'concreting',           icon: '🛣️', description: 'Driveways, paths, slabs & concrete resurfacing' },
  { name: 'Plastering',                  slug: 'plastering',           icon: '🏗️', description: 'Plasterboard, cornice, render & patch repairs' },
  { name: 'Flooring',                    slug: 'flooring',             icon: '🪜', description: 'Timber, hybrid, carpet & vinyl floor installation' },
  { name: 'Fencing & Gates',             slug: 'fencing',              icon: '🔩', description: 'Colorbond, timber, pool fencing & gate automation' },
  { name: 'Glazing & Window Repairs',    slug: 'glazing',              icon: '🪟', description: 'Window glass, shower screens, splashbacks & mirrors' },
  { name: 'Pest Control',                slug: 'pest-control',         icon: '🐛', description: 'Termite inspection, treatment & general pest control' },
  { name: 'Security Systems',            slug: 'security',             icon: '🔒', description: 'Alarms, CCTV, intercoms & access control' },
  { name: 'Solar & Renewable Energy',    slug: 'solar',                icon: '☀️', description: 'Solar panels, battery storage & solar hot water' },
  { name: 'Gas Fitting',                 slug: 'gas-fitting',          icon: '🔥', description: 'Gas appliance installation, repair & leak detection' },
  { name: 'Demolition',                  slug: 'demolition',           icon: '🔨', description: 'Residential & commercial demolition & site clearance' },
  { name: 'Waterproofing',               slug: 'waterproofing',        icon: '💧', description: 'Wet areas, decks, balconies & below-slab waterproofing' },
  { name: 'Cleaning',                    slug: 'cleaning',             icon: '🧹', description: 'End of lease, builders, deep cleaning & pressure washing' },
  { name: 'Handyman',                    slug: 'handyman',             icon: '🛠️', description: 'General repairs, flat-pack assembly & odd jobs' },
  { name: 'Building & Construction',     slug: 'building',             icon: '🏗️', description: 'Extensions, renovations & structural building work' },
  { name: 'Bathroom Renovation',         slug: 'bathroom-renovation',  icon: '🛁', description: 'Full bathroom & ensuite renovations' },
  { name: 'Kitchen Renovation',          slug: 'kitchen-renovation',   icon: '🍳', description: 'Full kitchen renovations & cabinet installation' },
];

/**
 * Map from display name → DB slug.
 * Used by getCategorySlug() to convert a selected category name to the correct slug.
 */
export const CATEGORY_SLUG_MAP: Record<string, string> = Object.fromEntries(
  TRADIE_CATEGORIES.map(c => [c.name, c.slug])
);

/**
 * Convert a category display name to its DB slug.
 * Falls back to a safe kebab-case slug if the name is not in the canonical list.
 */
export function getCategorySlug(name: string): string {
  if (!name) return '';
  // 1. Exact match against canonical map
  if (CATEGORY_SLUG_MAP[name]) return CATEGORY_SLUG_MAP[name];
  // 2. Case-insensitive name match
  const lower = name.toLowerCase();
  const found = TRADIE_CATEGORIES.find(c => c.name.toLowerCase() === lower);
  if (found) return found.slug;
  // 3. If the input already looks like a valid slug (e.g. "plumbing"), pass it through
  const knownSlug = TRADIE_CATEGORIES.find(c => c.slug === lower || c.slug === name);
  if (knownSlug) return knownSlug.slug;
  // 4. Fallback: kebab-case (strips '&' and extra symbols)
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

/**
 * List of category display names (for backwards-compatible filtering, search etc.)
 */
export const CATEGORY_NAMES: string[] = TRADIE_CATEGORIES.map(c => c.name);
