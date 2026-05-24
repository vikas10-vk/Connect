export type VerificationLevel = "basic" | "standard" | "strict";

export type RequiredDocumentType =
  | "abn"
  | "public_liability"
  | "trade_licence"
  | "white_card"
  | "swms";

export interface ServiceVerificationRule {
  level: VerificationLevel;
  group: string;
  documents: RequiredDocumentType[];
  reason: string;
}

export interface ServiceCategory {
  id: string;
  name: string;
  slug?: string;
  description?: string | null;
}

export interface RequiredDocument {
  type: RequiredDocumentType;
  label: string;
  level: VerificationLevel;
  serviceNames: string[];
  description: string;
}

const BASE_DOCUMENTS: RequiredDocumentType[] = ["abn"];
const INSURANCE_DOCUMENTS: RequiredDocumentType[] = ["abn", "public_liability"];
const SITE_DOCUMENTS: RequiredDocumentType[] = ["abn", "public_liability", "white_card"];
const STRICT_DOCUMENTS: RequiredDocumentType[] = ["abn", "public_liability", "trade_licence", "white_card"];
const HIGH_RISK_DOCUMENTS: RequiredDocumentType[] = ["abn", "public_liability", "trade_licence", "white_card", "swms"];

const RULES_BY_SLUG: Record<string, ServiceVerificationRule> = {
  cleaning: {
    level: "basic",
    group: "Cleaning & Maintenance",
    documents: BASE_DOCUMENTS,
    reason: "Low-risk maintenance work. ABN is enough to identify the business.",
  },
  handyman: {
    level: "basic",
    group: "Cleaning & Maintenance",
    documents: BASE_DOCUMENTS,
    reason: "General minor repairs can start with light verification.",
  },
  painting: {
    level: "standard",
    group: "Home Improvement",
    documents: INSURANCE_DOCUMENTS,
    reason: "Insurance should be checked before interior or exterior work.",
  },
  plastering: {
    level: "standard",
    group: "Home Improvement",
    documents: INSURANCE_DOCUMENTS,
    reason: "Property work should have public liability cover.",
  },
  flooring: {
    level: "standard",
    group: "Home Improvement",
    documents: INSURANCE_DOCUMENTS,
    reason: "Flooring work should have business and insurance checks.",
  },
  carpentry: {
    level: "standard",
    group: "Home Improvement",
    documents: SITE_DOCUMENTS,
    reason: "Carpentry can involve site and structural risk, so site safety evidence is useful.",
  },
  tiling: {
    level: "standard",
    group: "Home Improvement",
    documents: INSURANCE_DOCUMENTS,
    reason: "Tiling usually needs insurance; waterproofing work is stricter separately.",
  },
  landscaping: {
    level: "standard",
    group: "Outdoor & Garden",
    documents: INSURANCE_DOCUMENTS,
    reason: "Garden and outdoor work should have public liability cover.",
  },
  concreting: {
    level: "standard",
    group: "Outdoor & Garden",
    documents: SITE_DOCUMENTS,
    reason: "Concrete work can involve site hazards and property damage risk.",
  },
  fencing: {
    level: "standard",
    group: "Outdoor & Garden",
    documents: SITE_DOCUMENTS,
    reason: "Fencing and gates should have insurance and site safety checks.",
  },
  glazing: {
    level: "standard",
    group: "Specialist Work",
    documents: INSURANCE_DOCUMENTS,
    reason: "Glass work has property and injury risk, so insurance is required.",
  },
  "pest-control": {
    level: "standard",
    group: "Specialist Work",
    documents: INSURANCE_DOCUMENTS,
    reason: "Pest control should have insurance before handling treatments on site.",
  },
  roofing: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: HIGH_RISK_DOCUMENTS,
    reason: "Roofing is high-risk work and may require trade or height-safety evidence.",
  },
  // ── Electrical  -  both slug variants so DB naming doesn't matter ──────────
  electrical: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Electrical work must be strictly verified before leads are sent.",
  },
  electrician: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Electrical work must be strictly verified before leads are sent.",
  },
  // ── Plumbing variants ────────────────────────────────────────────────────
  plumbing: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Plumbing work needs licence and insurance verification.",
  },
  plumber: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Plumbing work needs licence and insurance verification.",
  },
  // ── Gas ─────────────────────────────────────────────────────────────────
  "gas-fitting": {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Gas work requires strict licence verification.",
  },
  "gas-fitter": {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Gas work requires strict licence verification.",
  },
  // ── HVAC / Air Conditioning ──────────────────────────────────────────────
  hvac: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Heating and cooling can involve electrical and refrigerant compliance.",
  },
  "air-conditioning": {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Air conditioning installation often needs licensed electrical or refrigerant work.",
  },
  "air-conditioner": {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Air conditioning installation often needs licensed electrical or refrigerant work.",
  },
  // ── Solar ────────────────────────────────────────────────────────────────
  solar: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: HIGH_RISK_DOCUMENTS,
    reason: "Solar work needs strict electrical, roof, and safety verification.",
  },
  "solar-installation": {
    level: "strict",
    group: "Licensed & High Risk",
    documents: HIGH_RISK_DOCUMENTS,
    reason: "Solar work needs strict electrical, roof, and safety verification.",
  },
  // ── Security ─────────────────────────────────────────────────────────────
  security: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Security work can require licensing and identity-sensitive access.",
  },
  // ── Construction ─────────────────────────────────────────────────────────
  demolition: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: HIGH_RISK_DOCUMENTS,
    reason: "Demolition is high-risk and needs strict compliance checks.",
  },
  waterproofing: {
    level: "strict",
    group: "Licensed & High Risk",
    documents: STRICT_DOCUMENTS,
    reason: "Waterproofing failure can cause major damage, so verification is strict.",
  },
  building: {
    level: "strict",
    group: "Renovations & Construction",
    documents: HIGH_RISK_DOCUMENTS,
    reason: "Building and structural work needs the strongest verification.",
  },
  "bathroom-renovation": {
    level: "strict",
    group: "Renovations & Construction",
    documents: HIGH_RISK_DOCUMENTS,
    reason: "Bathroom renovation can involve plumbing, waterproofing, electrical, and site safety.",
  },
  "kitchen-renovation": {
    level: "strict",
    group: "Renovations & Construction",
    documents: STRICT_DOCUMENTS,
    reason: "Kitchen renovation can involve electrical, plumbing, gas, and installation risk.",
  },
};

const DOCUMENT_LABELS: Record<RequiredDocumentType, string> = {
  abn: "ABN",
  public_liability: "Public Liability Insurance",
  trade_licence: "Trade Licence / Certification",
  white_card: "White Card",
  swms: "SWMS",
};

const DOCUMENT_DESCRIPTIONS: Record<RequiredDocumentType, string> = {
  abn: "Confirms the business identity.",
  public_liability: "Protects homeowners and tradies if property damage or injury occurs.",
  trade_licence: "Required for licensed or regulated trade work.",
  white_card: "Shows construction site safety training.",
  swms: "Required for high-risk construction or commercial site work.",
};

const LEVEL_RANK: Record<VerificationLevel, number> = {
  basic: 1,
  standard: 2,
  strict: 3,
};

export function getServiceRule(category: Pick<ServiceCategory, "name" | "slug">): ServiceVerificationRule {
  // 1. Try exact slug match first
  const slug = category.slug?.toLowerCase().trim();
  if (slug && RULES_BY_SLUG[slug]) return RULES_BY_SLUG[slug];

  // 2. Try normalised name as slug (handles DB categories named "Electrician" with slug "electrician")
  const nameAsSlug = category.name.toLowerCase().trim().replace(/\s+/g, "-");
  if (RULES_BY_SLUG[nameAsSlug]) return RULES_BY_SLUG[nameAsSlug];

  // 3. Substring name matching  -  use broad prefixes so "electrician", "electrical",
  //    "plumber", "plumbing", "gas fitter", "gas fitting" etc. all match.
  const name = category.name.toLowerCase();

  const strictPatterns = [
    "electric",   // catches "electrician" AND "electrical"
    "plumb",      // catches "plumber" AND "plumbing"
    "gas",
    "solar",
    "building",
    "demolition",
    "waterproof",
    "roof",
    "security",
    "air condition",  // catches "air conditioning" AND "air conditioner"
    "hvac",
    "refriger",
  ];
  if (strictPatterns.some((p) => name.includes(p))) {
    return {
      level: "strict",
      group: "Licensed & High Risk",
      documents: STRICT_DOCUMENTS,
      reason: "This service can involve licensed or high-risk work.",
    };
  }

  const basicPatterns = ["cleaning", "handyman", "lawn mowing", "garden maintenance", "mowing"];
  if (basicPatterns.some((p) => name.includes(p))) {
    return {
      level: "basic",
      group: "Cleaning & Maintenance",
      documents: BASE_DOCUMENTS,
      reason: "This service can start with light business verification.",
    };
  }

  return {
    level: "standard",
    group: "Home Improvement",
    documents: INSURANCE_DOCUMENTS,
    reason: "This service should have business and insurance checks.",
  };
}

export function getLevelLabel(level: VerificationLevel) {
  if (level === "basic") return "Basic";
  if (level === "standard") return "Insurance required";
  return "Strict verification";
}

export function getDocumentLabel(type: RequiredDocumentType) {
  return DOCUMENT_LABELS[type];
}

export function getRequiredDocuments(categories: ServiceCategory[]): RequiredDocument[] {
  const docs = new Map<RequiredDocumentType, RequiredDocument>();

  for (const category of categories) {
    const rule = getServiceRule(category);
    for (const type of rule.documents) {
      const existing = docs.get(type);
      if (existing) {
        existing.serviceNames.push(category.name);
        if (LEVEL_RANK[rule.level] > LEVEL_RANK[existing.level]) {
          existing.level = rule.level;
        }
      } else {
        docs.set(type, {
          type,
          label: DOCUMENT_LABELS[type],
          level: rule.level,
          serviceNames: [category.name],
          description: DOCUMENT_DESCRIPTIONS[type],
        });
      }
    }
  }

  return Array.from(docs.values()).sort((a, b) => {
    const order: RequiredDocumentType[] = ["abn", "public_liability", "trade_licence", "white_card", "swms"];
    return order.indexOf(a.type) - order.indexOf(b.type);
  });
}

export function getHighestVerificationLevel(categories: ServiceCategory[]): VerificationLevel {
  return categories.reduce<VerificationLevel>((highest, category) => {
    const level = getServiceRule(category).level;
    return LEVEL_RANK[level] > LEVEL_RANK[highest] ? level : highest;
  }, "basic");
}