"use client";

import React, { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  AlertCircle, Bell, BriefcaseBusiness, Building2,
  CheckCircle, Info,
  Loader2, Mail, MapPin, Phone, Save, Search,
  SlidersHorizontal, X,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/src/lib/api";
import {
  getDocumentLabel, getRequiredDocuments, getServiceRule, getLevelLabel,
  type RequiredDocumentType, type ServiceCategory, type VerificationLevel,
} from "@/src/lib/tradie-verification";
import TradieStudioLayout from "@/src/components/tradie/TradieStudioLayout";

// ─── Design tokens — exact match with TradieDashboard ────────────────────────
const C = {
  bg: '#FFF8E7', paper: '#FFF8E7', panel: '#F5EDD0', card: '#FFFFFF',
  line: '#E8D9B0', lineSoft: '#F5EDD0',
  ink: '#071D36', ink2: '#173452', ink3: '#56677A', ink4: '#8A785A',
  brass: '#D4AA3A', brassL: '#F7EBC5', brassB: '#E8C766',
  sage: '#5B7560', sageL: '#EDF3EE',
  amber: '#9A6B1E', amberL: '#F7EED8',
  rose: '#A8423A', roseL: '#F7E6E4',
};
const SHADOW_SM = '0 1px 3px rgba(26,26,26,0.05), 0 1px 2px rgba(26,26,26,0.03)';
const DISPLAY = "'Fraunces', 'Playfair Display', Georgia, serif";
const UI = "'Inter', 'DM Sans', -apple-system, system-ui, sans-serif";
const AU_STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"];

// ─── Shared style objects ─────────────────────────────────────────────────────
const panelStyle: React.CSSProperties = {
  background: C.card, border: `1px solid ${C.line}`,
  borderRadius: 14, overflow: 'hidden', boxShadow: SHADOW_SM,
};
const secLabel: React.CSSProperties = {
  fontSize: 10, fontWeight: 700, color: C.ink3,
  textTransform: 'uppercase', letterSpacing: '0.14em', margin: 0,
};
const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 14px', borderRadius: 10,
  border: `1px solid ${C.line}`, background: C.paper,
  fontSize: 13.5, color: C.ink, outline: 'none',
  boxSizing: 'border-box', fontFamily: UI,
};

const SERVICE_SYNONYMS: Record<string, string> = {
  plumber: 'plumbing',
  electrician: 'electrical',
  'gas-fitter': 'gas-fitting',
  'gas-fitting': 'gas-fitting',
  roofer: 'roofing',
  waterproofer: 'waterproofing',
  glazier: 'glazing',
  builder: 'building',
  concretor: 'concreting',
  carpenter: 'carpentry',
  painter: 'painting',
  tiler: 'tiling',
  landscaper: 'landscaping',
  'air-conditioning-installer': 'hvac',
  'air-conditioning': 'hvac',
};

const normaliseServiceKey = (value?: string | null) => {
  const key = (value || '').toLowerCase().trim().replace(/&/g, 'and').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return SERVICE_SYNONYMS[key] || key;
};

// ─── Types ────────────────────────────────────────────────────────────────────
interface CategoryItem extends ServiceCategory { subcategories?: unknown[] }
interface ServiceSuburb { suburb: string; postcode: string; state_code: string }
interface Settings {
  accept_residential: boolean; accept_commercial: boolean;
  accept_high_intent: boolean; accept_planning: boolean;
  notify_new_lead: boolean; notify_email: boolean; notify_sms: boolean;
}
interface CompliancePass {
  abn_verified?: boolean;
  white_card_verified?: boolean;
  wc_verified?: boolean;
  swms_uploaded?: boolean;
}
const DEFAULT_SETTINGS: Settings = {
  accept_residential: true, accept_commercial: true,
  accept_high_intent: true, accept_planning: true,
  notify_new_lead: true, notify_email: true, notify_sms: false,
};

// ─── Toggle ───────────────────────────────────────────────────────────────────
function Toggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return (
    <button type="button" onClick={onChange} style={{ width: 40, height: 22, borderRadius: 11, flexShrink: 0, background: on ? C.ink : C.line, border: 'none', cursor: 'pointer', position: 'relative', transition: 'background 0.2s' }}>
      <div style={{ width: 16, height: 16, borderRadius: '50%', background: C.card, position: 'absolute', top: 3, left: on ? 21 : 3, transition: 'left 0.2s cubic-bezier(0.4,0,0.2,1)', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
    </button>
  );
}

function ToggleRow({ title, sub, on, onChange, icon: Icon }: { title: string; sub: string; on: boolean; onChange: () => void; icon: React.ElementType }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 18px', borderRadius: 10, background: C.paper, border: `1px solid ${C.line}`, gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ width: 34, height: 34, borderRadius: 9, background: C.card, border: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <Icon size={14} color={C.ink3} />
        </div>
        <div>
          <p style={{ fontSize: 13.5, fontWeight: 600, color: C.ink, margin: '0 0 2px', fontFamily: UI }}>{title}</p>
          <p style={{ fontSize: 12, color: C.ink3, margin: 0, fontFamily: UI }}>{sub}</p>
        </div>
      </div>
      <Toggle on={on} onChange={onChange} />
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function Preferences() {
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [selectedCatIds, setSelectedCatIds] = useState<string[]>([]);
  const [initialCatIds, setInitialCatIds] = useState<string[]>([]);
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [initialSettings, setInitialSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [serviceAreas, setServiceAreas] = useState<ServiceSuburb[]>([]);
  const [initialAreas, setInitialAreas] = useState<ServiceSuburb[]>([]);

  const [areaSuburb, setAreaSuburb] = useState('');
  const [areaPostcode, setAreaPostcode] = useState('');
  const [areaState, setAreaState] = useState('');
  const [activeState, setActiveState] = useState('');

  // Suburb autocomplete
  const [suburbSuggestions, setSuburbSuggestions] = useState<{ suburb: string; postcode: string; state_code: string }[]>([]);
  const [suburbSuggestionsOpen, setSuburbSuggestionsOpen] = useState(false);
  const [suburbLoading, setSuburbLoading] = useState(false);
  const suburbDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const [catSearch, setCatSearch] = useState('');
  const [levelFilter, setLevelFilter] = useState<'all' | VerificationLevel>('all');
  const [previewCatId, setPreviewCatId] = useState<string | null>(null);
  const [confirmAddCat, setConfirmAddCat] = useState<CategoryItem | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [verifiedCertCatIds, setVerifiedCertCatIds] = useState<string[]>([]);
  const [verifiedCertKeys, setVerifiedCertKeys] = useState<string[]>([]);
  const [hasVerifiedInsurance, setHasVerifiedInsurance] = useState(false);
  const [compliancePass, setCompliancePass] = useState<CompliancePass>({});
  const [profileVerified, setProfileVerified] = useState(false);

  // ── Load ──────────────────────────────────────────────────────────────────
  useEffect(() => {
    let alive = true;
    async function load() {
      setLoading(true); setLoadError('');
      try {
        const [treeRes, myRes, prefRes, profileRes, onboardingRes, passRes] = await Promise.allSettled([
          api.get('/categories'),          // flat list of 24 canonical trade categories
          api.get('/categories/my-categories'),
          api.get('/tradies/preferences/me'),
          api.get('/tradies/profile/me'),
          api.get('/tradies/onboarding/status'),
          api.get('/compliance/my-pass'),
        ]);
        if (!alive) return;
        // /categories returns a flat array (not wrapped in {categories:[...]})
        const cats = (treeRes.status === 'fulfilled' ? treeRes.value.data || [] : []) as CategoryItem[];
        const ids = ((myRes.status === 'fulfilled' ? myRes.value.data || [] : []) as { category_id: string }[]).map(x => x.category_id);
        const s = { ...DEFAULT_SETTINGS, ...(prefRes.status === 'fulfilled' ? prefRes.value.data || {} : {}) } as Settings;
        const areas = prefRes.status === 'fulfilled' ? prefRes.value.data?.service_suburbs || [] : [];
        const state = profileRes.status === 'fulfilled' ? profileRes.value.data?.state || '' : '';
        const verifiedProfile = profileRes.status === 'fulfilled' && profileRes.value.data?.verification_status === 'verified';
        const onboardingData = onboardingRes.status === 'fulfilled' ? onboardingRes.value.data : null;
        const passData = passRes.status === 'fulfilled' ? passRes.value.data || {} : {};

        // Verified cert IDs and insurance — used for missing-doc gap warnings
        const verifiedCerts = (onboardingData?.certifications || [])
          .filter((c: { status: string }) => c.status === 'verified');
        const verifiedCertCategoryIds: string[] = verifiedCerts.map((c: { category_id: string }) => c.category_id);
        const verifiedCategoryKeys: string[] = verifiedCerts.flatMap((c: { category_name?: string | null; category_slug?: string | null }) => [
          normaliseServiceKey(c.category_slug),
          normaliseServiceKey(c.category_name),
        ]).filter(Boolean);
        const verifiedIns = (onboardingData?.insurance_policies || [])
          .some((p: { status: string; insurance_type: string }) =>
            p.status === 'verified' && p.insurance_type === 'public_liability');

        setCategories(cats);
        setSelectedCatIds(ids); setInitialCatIds(ids);
        setSettings(s); setInitialSettings(s);
        setServiceAreas(areas); setInitialAreas(areas);
        if (state) setAreaState(state);
        setVerifiedCertCatIds(verifiedCertCategoryIds);
        setVerifiedCertKeys(verifiedCategoryKeys);
        setHasVerifiedInsurance(verifiedIns);
        setCompliancePass(passData);
        setProfileVerified(verifiedProfile);
      } catch (e: any) {
        const d = e?.response?.data?.detail;
        setLoadError(typeof d === 'string' ? d : 'Could not load preferences.');
      } finally { if (alive) setLoading(false); }
    }
    load();
    return () => { alive = false; };
  }, []);

  // ── Computed ──────────────────────────────────────────────────────────────
  const selectedCategories = useMemo(() => categories.filter(c => selectedCatIds.includes(c.id)), [categories, selectedCatIds]);
  const requiredDocs = useMemo(() => getRequiredDocuments(selectedCategories), [selectedCategories]);

  const missingDocumentTypesForCategory = (cat: CategoryItem): RequiredDocumentType[] => {
    const rule = getServiceRule(cat);
    const missing: RequiredDocumentType[] = [];

    for (const doc of rule.documents) {
      if (doc === 'abn' && !(profileVerified || compliancePass.abn_verified)) {
        missing.push(doc);
      }
      if (doc === 'public_liability' && !hasVerifiedInsurance) {
        missing.push(doc);
      }
      const serviceKeys = [normaliseServiceKey(cat.slug), normaliseServiceKey(cat.name)];
      const hasMatchingLicence =
        verifiedCertCatIds.includes(cat.id) ||
        serviceKeys.some(key => key && verifiedCertKeys.includes(key));

      if (doc === 'trade_licence' && !hasMatchingLicence) {
        missing.push(doc);
      }
      if (doc === 'white_card' && !(compliancePass.white_card_verified || compliancePass.wc_verified)) {
        missing.push(doc);
      }
      if (doc === 'swms' && !compliancePass.swms_uploaded) {
        missing.push(doc);
      }
    }

    return missing;
  };

  // For each selected service, list only the documents that are not already verified.
  const missingDocsByService = useMemo(() => {
    const result: { catName: string; missing: string[] }[] = [];
    for (const cat of selectedCategories) {
      const missing = missingDocumentTypesForCategory(cat).map(getDocumentLabel);
      if (missing.length > 0) result.push({ catName: cat.name, missing });
    }
    return result;
  }, [selectedCategories, verifiedCertCatIds, verifiedCertKeys, hasVerifiedInsurance, compliancePass, profileVerified]);

  const outstandingDocs = useMemo(() => {
    const labels = new Set<string>();
    for (const cat of selectedCategories) {
      for (const doc of missingDocumentTypesForCategory(cat)) {
        labels.add(getDocumentLabel(doc));
      }
    }
    return Array.from(labels);
  }, [selectedCategories, verifiedCertCatIds, verifiedCertKeys, hasVerifiedInsurance, compliancePass, profileVerified]);

  const groupedCategories = useMemo(() => {
    const q = catSearch.trim().toLowerCase();
    const filtered = categories.filter(c => {
      const rule = getServiceRule(c);
      return (!q || c.name.toLowerCase().includes(q)) && (levelFilter === 'all' || rule.level === levelFilter);
    }).sort((a, b) => {
      const rank = { strict: 0, standard: 1, basic: 2 } as const;
      return rank[getServiceRule(a).level] - rank[getServiceRule(b).level] || a.name.localeCompare(b.name);
    });
    return filtered.reduce<Record<string, CategoryItem[]>>((acc, cat) => {
      const g = getServiceRule(cat).group; (acc[g] = acc[g] || []).push(cat); return acc;
    }, {});
  }, [categories, catSearch, levelFilter]);

  // ── Suburb autocomplete fetch ──────────────────────────────────────────────
  const fetchSuburbSuggestions = (q: string) => {
    if (suburbDebounceRef.current) clearTimeout(suburbDebounceRef.current);
    if (q.trim().length < 2) { setSuburbSuggestions([]); setSuburbSuggestionsOpen(false); return; }
    suburbDebounceRef.current = setTimeout(async () => {
      setSuburbLoading(true);
      try {
        const params = new URLSearchParams({ q: q.trim(), limit: '10' });
        if (activeState) params.set('state', activeState);
        const res = await api.get(`/suburbs/search?${params.toString()}`);
        const data = res.data as { suburb: string; postcode: string; state_code: string }[];
        setSuburbSuggestions(data || []);
        setSuburbSuggestionsOpen((data || []).length > 0);
      } catch { setSuburbSuggestions([]); setSuburbSuggestionsOpen(false); }
      finally { setSuburbLoading(false); }
    }, 280);
  };

  const pickSuburbSuggestion = (s: { suburb: string; postcode: string; state_code: string }) => {
    setAreaSuburb(s.suburb);
    setAreaPostcode(s.postcode);
    setAreaState(s.state_code);
    setActiveState(s.state_code);
    setSuburbSuggestions([]);
    setSuburbSuggestionsOpen(false);
  };

  // ── Handlers ──────────────────────────────────────────────────────────────
  const addArea = () => {
    if (!areaSuburb.trim() || !areaPostcode.trim() || !areaState) { toast.error('Enter suburb, postcode and state.'); return; }
    if (serviceAreas.length >= 20) { toast.error('Maximum 20 service areas.'); return; }
    if (serviceAreas.some(a => a.suburb.toLowerCase() === areaSuburb.toLowerCase() && a.postcode === areaPostcode && a.state_code === areaState)) { toast.error('Already added.'); return; }
    setServiceAreas(prev => [...prev, { suburb: areaSuburb.trim(), postcode: areaPostcode.trim(), state_code: areaState }]);
    setAreaSuburb(''); setAreaPostcode('');
  };
  const removeArea = (a: ServiceSuburb) =>
    setServiceAreas(prev => prev.filter(x => !(x.suburb === a.suburb && x.postcode === a.postcode && x.state_code === a.state_code)));

  const handleServiceClick = (cat: CategoryItem) => {
    if (selectedCatIds.includes(cat.id)) {
      setSelectedCatIds(prev => prev.filter(id => id !== cat.id)); setConfirmAddCat(null);
    } else if (getServiceRule(cat).level === 'strict') {
      setConfirmAddCat(cat); setPreviewCatId(null);
    } else {
      setSelectedCatIds(prev => [...prev, cat.id]);
    }
  };
  const confirmAdd = () => {
    if (!confirmAddCat) return;
    setSelectedCatIds(prev => [...prev, confirmAddCat.id]);
    setPreviewCatId(confirmAddCat.id); setConfirmAddCat(null);
  };

  const hasChanges =
    JSON.stringify([...selectedCatIds].sort()) !== JSON.stringify([...initialCatIds].sort()) ||
    JSON.stringify(settings) !== JSON.stringify(initialSettings) ||
    JSON.stringify(serviceAreas) !== JSON.stringify(initialAreas);

  const saveChanges = async () => {
    setSaving(true);
    const toAdd    = selectedCatIds.filter(id => !initialCatIds.includes(id));
    const toRemove = initialCatIds.filter(id => !selectedCatIds.includes(id));

    // ── Use allSettled so partial failures are visible, not silently swallowed ──
    // Promise.all would hide whether it was the preferences patch or a category
    // add/remove that failed. allSettled lets us report exactly what succeeded
    // and what didn't, which is critical for matching accuracy.
    const catAddResults    = await Promise.allSettled(toAdd.map(id => api.post(`/categories/my-categories/${id}`).then(() => ({ id, op: 'add' as const }))));
    const catRemoveResults = await Promise.allSettled(toRemove.map(id => api.delete(`/categories/my-categories/${id}`).then(() => ({ id, op: 'remove' as const }))));
    const prefResult       = await Promise.allSettled([api.patch('/tradies/preferences/me', { ...settings, service_suburbs: serviceAreas })]);

    // Collect failures
    const addFailures    = catAddResults.filter(r => r.status === 'rejected');
    const removeFailures = catRemoveResults.filter(r => r.status === 'rejected');
    const prefFailure    = prefResult[0]?.status === 'rejected';

    const totalFailures = addFailures.length + removeFailures.length + (prefFailure ? 1 : 0);
    const totalOps      = toAdd.length + toRemove.length + 1; // +1 for the prefs patch

    if (totalFailures === 0) {
      // All succeeded — update local state baseline
      setInitialCatIds([...selectedCatIds]);
      setInitialSettings({ ...settings });
      setInitialAreas([...serviceAreas]);
      toast.success('Preferences saved.');
    } else if (totalFailures === totalOps) {
      // Everything failed
      toast.error('Could not save preferences. Please check your connection and try again.');
    } else {
      // Partial failure — tell the user exactly what failed
      const parts: string[] = [];
      if (addFailures.length)    parts.push(`${addFailures.length} service${addFailures.length > 1 ? 's' : ''} could not be added`);
      if (removeFailures.length) parts.push(`${removeFailures.length} service${removeFailures.length > 1 ? 's' : ''} could not be removed`);
      if (prefFailure)           parts.push('notification settings could not be saved');

      // Update local state only for the parts that succeeded
      const succeededAddIds    = catAddResults.filter(r => r.status === 'fulfilled').map((r: any) => r.value.id);
      const succeededRemoveIds = catRemoveResults.filter(r => r.status === 'fulfilled').map((r: any) => r.value.id);
      const newCatIds = [
        ...initialCatIds.filter(id => !succeededRemoveIds.includes(id)),
        ...succeededAddIds,
      ];
      setInitialCatIds(newCatIds);
      if (!prefFailure) { setInitialSettings({ ...settings }); setInitialAreas([...serviceAreas]); }

      toast.warning(`Partially saved — ${parts.join('; ')}. Please retry.`);
    }

    setSaving(false);
  };

  // ── Left panel — computed variable, never IIFEs ───────────────────────────
  let leftContent: React.ReactNode;

  if (confirmAddCat) {
    const rule = getServiceRule(confirmAddCat);
    leftContent = (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
        <span style={{ alignSelf: 'flex-start', fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20, background: C.amberL, color: C.amber, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
          {getLevelLabel(rule.level)}
        </span>
        <div>
          <p style={{ fontFamily: DISPLAY, fontSize: 18, fontWeight: 500, color: C.ink, margin: '0 0 5px', letterSpacing: '-0.01em' }}>{confirmAddCat.name}</p>
          <p style={{ fontSize: 13, color: C.ink3, margin: 0, lineHeight: 1.65 }}>{rule.reason}</p>
        </div>
        <div style={{ background: C.paper, border: `1px solid ${C.line}`, borderRadius: 10, padding: '12px 16px' }}>
          <p style={{ ...secLabel, margin: '0 0 10px' }}>Documents required</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {rule.documents.map(d => (
              <div key={d} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: C.amber, flexShrink: 0 }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: C.ink2 }}>{getDocumentLabel(d)}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{ padding: '10px 14px', background: C.sageL, borderRadius: 10, border: `1px solid ${C.sage}30`, display: 'flex', gap: 8 }}>
          <Info size={13} color={C.sage} style={{ flexShrink: 0, marginTop: 1 }} />
          <p style={{ fontSize: 12, color: C.ink2, margin: 0, lineHeight: 1.55 }}>Your existing verified services and leads <strong>will not be affected</strong> by adding this service.</p>
        </div>
        <div style={{ marginTop: 'auto' }}>
          <p style={{ fontSize: 13, fontWeight: 600, color: C.ink, margin: '0 0 10px' }}>Add <em style={{ fontStyle: 'italic', color: C.brass }}>{confirmAddCat.name}</em>?</p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => setConfirmAddCat(null)} style={{ flex: 1, padding: '10px', borderRadius: 8, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: UI }}>Cancel</button>
            <button onClick={confirmAdd} style={{ flex: 1, padding: '10px', borderRadius: 8, border: 'none', background: C.ink, color: C.card, fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: UI }}>Yes, add service</button>
          </div>
        </div>
      </div>
    );
  } else if (previewCatId) {
    const cat = categories.find(c => c.id === previewCatId);
    if (!cat) {
      leftContent = null;
    } else {
      const rule = getServiceRule(cat);
      const isSelected = selectedCatIds.includes(previewCatId);
      const badgeBg = rule.level === 'strict' ? C.amberL : rule.level === 'standard' ? C.brassL : C.panel;
      const badgeColor = rule.level === 'strict' ? C.amber : rule.level === 'standard' ? C.brass : C.ink3;
      leftContent = (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20, background: badgeBg, color: badgeColor, textTransform: 'uppercase', letterSpacing: '0.1em' }}>{getLevelLabel(rule.level)}</span>
            {isSelected && <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20, background: C.sageL, color: C.sage }}>✓ Selected</span>}
          </div>
          <div>
            <p style={{ fontFamily: DISPLAY, fontSize: 18, fontWeight: 500, color: C.ink, margin: '0 0 5px', letterSpacing: '-0.01em' }}>{cat.name}</p>
            <p style={{ fontSize: 13, color: C.ink3, margin: 0, lineHeight: 1.65 }}>{rule.reason}</p>
          </div>
          <div style={{ background: C.paper, border: `1px solid ${C.line}`, borderRadius: 10, padding: '12px 16px' }}>
            <p style={{ ...secLabel, margin: '0 0 10px' }}>Documents required</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {rule.documents.map(d => (
                <div key={d} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: C.brass, flexShrink: 0 }} />
                  <span style={{ fontSize: 13, color: C.ink2 }}>{getDocumentLabel(d)}</span>
                </div>
              ))}
            </div>
          </div>
          <p style={{ fontSize: 12, color: C.ink4, margin: 'auto 0 0' }}>Click to {isSelected ? 'remove from' : 'add to'} your services</p>
        </div>
      );
    }
  } else if (selectedCatIds.length === 0) {
    leftContent = (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, textAlign: 'center', color: C.ink4, padding: '32px 0' }}>
        <Search size={24} color={C.ink4} />
        <p style={{ fontSize: 13, margin: 0, lineHeight: 1.65, maxWidth: 200, color: C.ink3 }}>Hover a service on the right to see what documents it needs</p>
      </div>
    );
  } else {
    leftContent = (
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p style={{ ...secLabel }}>Selected services ({selectedCatIds.length})</p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, overflowY: 'auto', maxHeight: 300 }}>
          {selectedCategories.map(cat => {
            const rule = getServiceRule(cat);
            return (
              <div key={cat.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px', borderRadius: 8, background: C.paper, border: `1px solid ${C.line}` }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 13, fontWeight: 600, color: C.ink, margin: '0 0 2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cat.name}</p>
                  <p style={{ fontSize: 11, color: rule.level === 'strict' ? C.amber : C.ink3, margin: 0, fontWeight: 600 }}>{getLevelLabel(rule.level)}</p>
                </div>
                <button onClick={() => { toast('Removing won\'t affect your verified licence data', { icon: '⚠️' }); setSelectedCatIds(prev => prev.filter(id => id !== cat.id)); }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.ink4, padding: 2, display: 'flex' }}>
                  <X size={13} />
                </button>
              </div>
            );
          })}
        </div>
        {requiredDocs.length > 0 && (
          <div style={{ marginTop: 'auto', background: C.paper, border: `1px solid ${C.line}`, borderRadius: 10, padding: '12px 14px' }}>
            <p style={{ ...secLabel, marginBottom: 8 }}>
              {outstandingDocs.length > 0 ? 'Outstanding documents' : 'Documents verified for selected services'}
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(outstandingDocs.length > 0 ? outstandingDocs : ['All required documents are covered']).map(label => (
                <span key={label} style={{ fontSize: 10.5, fontWeight: 600, padding: '3px 10px', borderRadius: 20, background: C.card, border: `1px solid ${C.line}`, color: outstandingDocs.length > 0 ? C.ink2 : C.sage }}>{label}</span>
              ))}
            </div>
            <Link href="/tradie/licences" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 10, fontSize: 11, fontWeight: 700, color: C.brass, textDecoration: 'none', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              View in Licences &amp; Docs →
            </Link>
          </div>
        )}
      </div>
    );
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <TradieStudioLayout>
      {(ctx) => {
        if (loading) {
          return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', gap: 12, fontFamily: UI }}>
              <Loader2 size={18} color={C.brass} className="animate-spin" />
              <span style={{ fontSize: 12, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.16em' }}>Loading preferences</span>
            </div>
          );
        }
        return (
        <>
        {/* Sticky top bar */}
        <div style={{ position: 'sticky', top: 0, zIndex: 50, background: `${C.bg}F2`, backdropFilter: 'blur(12px)', borderBottom: `1px solid ${C.line}`, padding: '0 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 52 }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.2em' }}>Preferences</span>
          <button onClick={saveChanges} disabled={!hasChanges || saving}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 18px', borderRadius: 9, border: `1px solid ${hasChanges ? C.ink : C.line}`, background: hasChanges ? C.ink : C.panel, color: hasChanges ? C.card : C.ink3, fontWeight: 600, fontSize: 12, cursor: hasChanges ? 'pointer' : 'not-allowed', fontFamily: UI, transition: 'all 0.15s' }}>
            {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>

        <div style={{ maxWidth: 900, margin: '0 auto', padding: '28px 28px 80px', display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Header */}
          <div style={{ marginBottom: 4 }}>
            <p style={{ fontSize: 10, fontWeight: 700, color: C.brass, textTransform: 'uppercase', letterSpacing: '0.2em', margin: '0 0 6px' }}>Tradie setup</p>
            <h1 style={{ fontFamily: DISPLAY, fontSize: 30, fontWeight: 500, color: C.ink, margin: '0 0 6px', letterSpacing: '-0.02em' }}>Preferences</h1>
            <p style={{ fontSize: 13.5, color: C.ink3, margin: 0, lineHeight: 1.6 }}>Set your service areas, choose what work you want, then tune your lead feed.</p>
          </div>

          {loadError && (
            <div style={{ display: 'flex', gap: 10, padding: '12px 16px', background: C.roseL, border: `1px solid ${C.rose}30`, borderRadius: 10 }}>
              <AlertCircle size={15} color={C.rose} style={{ flexShrink: 0 }} />
              <p style={{ fontSize: 13, color: C.rose, margin: 0, fontWeight: 600 }}>{loadError}</p>
            </div>
          )}

          {/* ── 1. Service areas ── */}
          <div style={{ ...panelStyle, overflow: 'visible', position: 'relative', zIndex: 30 }}>
            <div style={{ padding: '12px 24px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', gap: 10 }}>
              <MapPin size={13} color={C.brass} />
              <p style={{ fontSize: 12.5, fontWeight: 700, color: C.ink, margin: 0 }}>1. Service areas &amp; states</p>
              <span style={{ fontSize: 11.5, color: C.ink3 }}>— determines which state licences are required</span>
            </div>
            <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 14, overflow: 'visible' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {AU_STATES.map(s => {
                  const active = activeState === s;
                  return (
                    <button key={s} onClick={() => { setActiveState(p => p === s ? '' : s); setAreaState(s); }}
                      style={{ padding: '6px 14px', borderRadius: 8, border: `1.5px solid ${active ? C.brass : C.line}`, background: active ? C.brassL : C.paper, color: active ? C.brass : C.ink3, fontSize: 12.5, fontWeight: 600, cursor: 'pointer', fontFamily: UI }}>
                      {s}
                    </button>
                  );
                })}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 140px 90px auto', gap: 8, alignItems: 'end', overflow: 'visible' }}>
                {/* Suburb autocomplete */}
                <div style={{ position: 'relative', zIndex: 60 }}>
                  <label style={{ ...secLabel, display: 'block', marginBottom: 6 }}>Suburb</label>
                  <input
                    value={areaSuburb}
                    onChange={e => { setAreaSuburb(e.target.value); fetchSuburbSuggestions(e.target.value); }}
                    onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; if (areaSuburb.trim().length >= 2) setSuburbSuggestionsOpen(suburbSuggestions.length > 0); }}
                    onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; setTimeout(() => setSuburbSuggestionsOpen(false), 180); }}
                    placeholder={activeState ? `Search suburb in ${activeState}…` : 'Search suburb…'}
                    style={inputStyle}
                    autoComplete="off"
                  />
                  {suburbLoading && (
                    <Loader2 size={12} className="animate-spin" style={{ position: 'absolute', right: 10, top: '72%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                  )}
                  {suburbSuggestionsOpen && suburbSuggestions.length > 0 && (
                    <div style={{ position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, background: C.card, border: `1px solid ${C.brass}`, borderRadius: 10, boxShadow: '0 12px 32px rgba(7,29,54,0.16)', zIndex: 999, overflow: 'hidden', maxHeight: 220, overflowY: 'auto' }}>
                      {suburbSuggestions.map((s, i) => (
                        <button
                          key={i}
                          type="button"
                          onMouseDown={() => pickSuburbSuggestion(s)}
                          style={{ width: '100%', padding: '9px 14px', border: 'none', borderBottom: i < suburbSuggestions.length - 1 ? `1px solid ${C.lineSoft}` : 'none', background: 'transparent', cursor: 'pointer', textAlign: 'left', fontFamily: UI, display: 'flex', alignItems: 'center', gap: 8 }}
                          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = C.panel; }}
                          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; }}
                        >
                          <MapPin size={11} color={C.brass} style={{ flexShrink: 0 }} />
                          <span style={{ fontSize: 13, color: C.ink, fontWeight: 500 }}>{s.suburb}</span>
                          <span style={{ fontSize: 11.5, color: C.ink3, marginLeft: 'auto' }}>{s.state_code} {s.postcode}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div>
                  <label style={{ ...secLabel, display: 'block', marginBottom: 6 }}>Postcode</label>
                  <input value={areaPostcode} onChange={e => setAreaPostcode(e.target.value)} placeholder="2150" style={inputStyle}
                    onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; }}
                    onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; }} />
                </div>
                <div>
                  <label style={{ ...secLabel, display: 'block', marginBottom: 6 }}>State</label>
                  <select value={areaState} onChange={e => setAreaState(e.target.value)} style={{ ...inputStyle, cursor: 'pointer' }}>
                    <option value="">—</option>
                    {AU_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <button onClick={addArea} style={{ padding: '10px 18px', borderRadius: 10, background: C.ink, color: C.card, border: 'none', fontWeight: 600, fontSize: 13, cursor: 'pointer', whiteSpace: 'nowrap', fontFamily: UI }}>Add</button>
              </div>
              {serviceAreas.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {serviceAreas.map(a => (
                    <span key={`${a.suburb}-${a.postcode}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 8px 5px 12px', borderRadius: 20, background: C.brassL, border: `1px solid ${C.brassB}`, fontSize: 12, fontWeight: 600, color: C.ink2 }}>
                      <MapPin size={10} color={C.brass} />{a.suburb}, {a.state_code} {a.postcode}
                      <button onClick={() => removeArea(a)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 0 0 2px', display: 'flex', color: C.ink3 }}><X size={12} /></button>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── 2. Services picker ── */}
          <div style={panelStyle}>
            <div style={{ padding: '12px 24px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <p style={{ fontSize: 12.5, fontWeight: 700, color: C.ink, margin: 0 }}>2. Services you offer</p>
              <span style={{ fontSize: 11, color: C.ink3 }}>{selectedCatIds.length} selected · syncs to Licences &amp; Docs</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', minHeight: 460 }}>

              {/* LEFT */}
              <div style={{ padding: '20px 22px', borderRight: `1px solid ${C.lineSoft}`, display: 'flex', flexDirection: 'column', gap: 14 }}>
                {leftContent}
              </div>

              {/* RIGHT */}
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <div style={{ padding: '12px 16px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ position: 'relative' }}>
                    <Search size={13} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                    <input value={catSearch} onChange={e => setCatSearch(e.target.value)} placeholder="Search services…"
                      style={{ ...inputStyle, paddingLeft: 32, padding: '9px 10px 9px 32px', fontSize: 13 }}
                      onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; }}
                      onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; }} />
                    {catSearch && <button onClick={() => setCatSearch('')} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: C.ink3, padding: 2 }}><X size={12} /></button>}
                  </div>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    {(['all', 'strict', 'standard', 'basic'] as const).map(f => {
                      const active = levelFilter === f;
                      return (
                        <button key={f} onClick={() => setLevelFilter(f)}
                          style={{ padding: '5px 10px', borderRadius: 7, border: `1px solid ${active ? C.brass : C.line}`, background: active ? C.brassL : C.card, color: active ? C.brass : C.ink3, fontSize: 11, fontWeight: 700, cursor: 'pointer', fontFamily: UI }}>
                          {f === 'all' ? 'All' : getLevelLabel(f)}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div style={{ overflowY: 'auto', maxHeight: 390 }}>
                  {Object.keys(groupedCategories).length === 0
                    ? <div style={{ padding: '32px 16px', textAlign: 'center', color: C.ink3, fontSize: 13 }}>No services match.</div>
                    : Object.entries(groupedCategories).map(([group, items]) => (
                      <div key={group}>
                        <div style={{ padding: '7px 16px', background: C.panel, borderBottom: `1px solid ${C.line}`, position: 'sticky', top: 0 }}>
                          <p style={{ ...secLabel, margin: 0 }}>{group}</p>
                        </div>
                        {items.map(cat => {
                          const selected = selectedCatIds.includes(cat.id);
                          const rule = getServiceRule(cat);
                          const isPrev = previewCatId === cat.id;
                          const isConfirm = confirmAddCat?.id === cat.id;
                          return (
                            <button key={cat.id}
                              onMouseEnter={() => { if (!confirmAddCat) setPreviewCatId(cat.id); }}
                              onMouseLeave={() => { if (!confirmAddCat) setPreviewCatId(null); }}
                              onClick={() => handleServiceClick(cat)}
                              style={{ width: '100%', padding: '11px 16px', border: 'none', borderBottom: `1px solid ${C.lineSoft}`, background: isConfirm ? C.amberL : selected ? C.brassL : isPrev ? C.panel : C.card, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10, textAlign: 'left', transition: 'background 0.1s', fontFamily: UI }}>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <p style={{ fontSize: 13, fontWeight: selected ? 700 : 500, color: selected ? C.brass : C.ink, margin: '0 0 2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cat.name}</p>
                                <p style={{ fontSize: 10.5, color: rule.level === 'strict' ? C.amber : C.ink3, margin: 0, fontWeight: 600 }}>{getLevelLabel(rule.level)}</p>
                              </div>
                              {selected
                                ? <CheckCircle size={14} color={C.brass} style={{ flexShrink: 0 }} />
                                : isConfirm
                                  ? <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: C.amberL, color: C.amber, flexShrink: 0 }}>Confirm?</span>
                                  : rule.level === 'strict'
                                    ? <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: C.panel, color: C.ink3, flexShrink: 0 }}>Licence</span>
                                    : null}
                            </button>
                          );
                        })}
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>

          {/* ── Missing document warning ── */}
          {missingDocsByService.length > 0 && (
            <div style={{ background: C.amberL, border: `1px solid ${C.brassB}`, borderRadius: 12, padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertCircle size={15} color={C.amber} style={{ flexShrink: 0 }} />
                <p style={{ fontSize: 13, fontWeight: 700, color: C.amber, margin: 0 }}>
                  Documents missing for selected services
                </p>
              </div>
              <p style={{ fontSize: 12.5, color: C.ink2, margin: 0, lineHeight: 1.6 }}>
                You&apos;ve selected strict-verification services that require verified documents.
                Upload them in <a href="/tradie/licences" style={{ color: C.brass, fontWeight: 700, textDecoration: 'none' }}>Licences &amp; Docs</a> to start receiving leads for these services.
              </p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {missingDocsByService.map(({ catName, missing }) => (
                  <div key={catName} style={{ background: C.card, border: `1px solid ${C.brassB}`, borderRadius: 8, padding: '9px 14px' }}>
                    <p style={{ fontSize: 12, fontWeight: 700, color: C.ink, margin: '0 0 4px' }}>{catName}</p>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                      {missing.map(doc => (
                        <span key={doc} style={{ fontSize: 11, fontWeight: 600, padding: '2px 9px', borderRadius: 20, background: C.amberL, color: C.amber, border: `1px solid ${C.brassB}` }}>
                          Missing: {doc}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── 3. Job types ── */}
          <div style={panelStyle}>
            <div style={{ padding: '12px 24px', borderBottom: `1px solid ${C.lineSoft}` }}>
              <p style={{ fontSize: 12.5, fontWeight: 700, color: C.ink, margin: 0 }}>3. Job types</p>
            </div>
            <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <ToggleRow title="Residential" sub="Houses, apartments, townhouses" on={settings.accept_residential} onChange={() => setSettings(s => ({ ...s, accept_residential: !s.accept_residential }))} icon={MapPin} />
              <ToggleRow title="Commercial" sub="Offices, retail, worksites" on={settings.accept_commercial} onChange={() => setSettings(s => ({ ...s, accept_commercial: !s.accept_commercial }))} icon={Building2} />
              <ToggleRow title="Ready-to-hire leads" sub="Customers ready to book now" on={settings.accept_high_intent} onChange={() => setSettings(s => ({ ...s, accept_high_intent: !s.accept_high_intent }))} icon={BriefcaseBusiness} />
              <ToggleRow title="Planning leads" sub="Early research and budgeting" on={settings.accept_planning} onChange={() => setSettings(s => ({ ...s, accept_planning: !s.accept_planning }))} icon={SlidersHorizontal} />
            </div>
          </div>

          {/* ── 4. Notifications ── */}
          <div style={panelStyle}>
            <div style={{ padding: '12px 24px', borderBottom: `1px solid ${C.lineSoft}` }}>
              <p style={{ fontSize: 12.5, fontWeight: 700, color: C.ink, margin: 0 }}>4. Notifications</p>
            </div>
            <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <ToggleRow title="New lead alerts" sub="Master switch for all lead notifications" on={settings.notify_new_lead} onChange={() => setSettings(s => ({ ...s, notify_new_lead: !s.notify_new_lead }))} icon={Bell} />
              <ToggleRow title="Email" sub="Lead details and document reminders" on={settings.notify_email} onChange={() => setSettings(s => ({ ...s, notify_email: !s.notify_email }))} icon={Mail} />
              <ToggleRow title="SMS" sub="Urgent new lead alerts by text" on={settings.notify_sms} onChange={() => setSettings(s => ({ ...s, notify_sms: !s.notify_sms }))} icon={Phone} />
            </div>
          </div>

          {/* Save */}
          <button onClick={saveChanges} disabled={!hasChanges || saving}
            style={{ alignSelf: 'flex-start', padding: '11px 22px', borderRadius: 10, background: hasChanges ? C.ink : C.panel, color: hasChanges ? C.card : C.ink3, border: 'none', fontWeight: 600, fontSize: 13, cursor: hasChanges ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', gap: 8, fontFamily: UI }}>
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {saving ? 'Saving…' : 'Save preferences'}
          </button>
        </div>{/* end max-width wrapper */}

        {/* Mobile save bar — shown below 768px, layout handles the nav drawer */}
        <div className="pref-save-bar" style={{ position: 'fixed', bottom: 0, left: 0, right: 0, padding: '12px 16px', background: `${C.bg}F0`, backdropFilter: 'blur(12px)', borderTop: `1px solid ${C.line}`, zIndex: 60 }}>
          <button onClick={saveChanges} disabled={!hasChanges || saving}
            style={{ width: '100%', padding: '13px', borderRadius: 10, background: hasChanges ? C.ink : C.panel, color: hasChanges ? C.card : C.ink3, border: 'none', fontWeight: 600, fontSize: 13, cursor: hasChanges ? 'pointer' : 'not-allowed', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, fontFamily: UI }}>
            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {saving ? 'Saving…' : hasChanges ? 'Save changes' : 'No changes'}
          </button>
        </div>
        <style>{`.pref-save-bar { display: none; } @media (max-width: 768px) { .pref-save-bar { display: block; } }`}</style>
        </>
        );
      }}
    </TradieStudioLayout>
  );
}
