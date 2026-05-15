"use client";

import React, { Suspense, useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Zap, Loader2, AlertCircle, MapPin, Clock, ChevronRight,
  Send, X, User, FileText,
  Bell, Upload, CheckCircle, Shield, Phone, Mail, Save, Camera,
  LayoutDashboard, Inbox, Briefcase, FolderOpen, SlidersHorizontal, UserCircle,
  Search, ArrowUpRight, Star, CircleDot, Plus, Eye,
  ZapOff, ImageIcon, Hourglass, ShieldCheck, Award, ExternalLink,
  AlertTriangle, Building2, Info,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { toast } from 'sonner';
import { useAuth } from '@/src/contexts/AuthContext';
import api from '@/src/lib/api';
import TradieStudioLayout from "@/src/components/tradie/TradieStudioLayout";
import MarkCompleteModal from "@/src/components/tradie/MarkCompleteModal";
import {
  getDocumentLabel,
  getLevelLabel,
  getRequiredDocuments,
  getServiceRule,
} from '@/src/lib/tradie-verification';

// ─── Design Tokens ────────────────────────────────────────────────────────────
const C = {
  paper: '#FFF8E7', panel: '#F5EDD0', card: '#FFFFFF',
  line: '#E8D9B0', lineSoft: '#F5EDD0',
  ink: '#071D36', ink2: '#173452', ink3: '#56677A', ink4: '#8A785A',
  brass: '#D4AA3A', brassL: '#F7EBC5', brassB: '#E8C766',
  sage: '#5B7560', sageL: '#EDF3EE',
  amber: '#9A6B1E', amberL: '#F7EED8',
  rose: '#A8423A', roseL: '#F7E6E4',
};
const SHADOW_XS = '0 1px 2px rgba(26,26,26,0.04)';
const SHADOW_SM = '0 1px 3px rgba(26,26,26,0.05), 0 1px 2px rgba(26,26,26,0.03)';
const SHADOW_MD = '0 4px 14px rgba(26,26,26,0.06), 0 1px 3px rgba(26,26,26,0.04)';
const SHADOW_LG = '0 20px 60px rgba(26,26,26,0.14), 0 4px 12px rgba(26,26,26,0.06)';
const DISPLAY = "'Fraunces', 'Playfair Display', Georgia, serif";
const UI = "'Inter', 'DM Sans', -apple-system, system-ui, sans-serif";

// ─── State registry URLs ──────────────────────────────────────────────────────
const STATE_REGISTRY: Record<string, { name: string; url: string }> = {
  VIC: { name: 'VBA', url: 'https://www.vba.vic.gov.au/tools/check-a-licence' },
  NSW: { name: 'NSW Fair Trading', url: 'https://www.onlineservices.fairtrading.nsw.gov.au/RLSearch.aspx' },
  QLD: { name: 'QBCC', url: 'https://www.qbcc.qld.gov.au/licence-search' },
  WA: { name: 'WA Building Comm', url: 'https://www.bsc.wa.gov.au/search-contractors.aspx' },
  SA: { name: 'CBS SA', url: 'https://www.sa.gov.au/topics/housing/building-and-renovation/licensing-search' },
  TAS: { name: 'CBOS', url: 'https://www.cbos.tas.gov.au/topics/licensing/search' },
  NT: { name: 'NT Government', url: 'https://nt.gov.au/industry/licences-and-permits' },
  ACT: { name: 'Access Canberra', url: 'https://www.accesscanberra.act.gov.au' },
};

// ─── Interfaces ───────────────────────────────────────────────────────────────
interface LeadCard {
  id: string; job_id: string; tradie_id: string;
  credits_charged: number; status: string; sent_at: string;
  job_title?: string; job_suburb?: string; job_state?: string;
  job_description?: string; job_budget_min?: number; job_budget_max?: number;
  job_urgency?: string; job_type?: string; service_type?: string;
  job_stage?: string; is_urgent?: boolean; is_high_value?: boolean;
  job_status?: string;
}
interface DashboardStats {
  avg_rating: number; review_count: number; credits: number;
  total_leads: number; response_rate: number;
  total_credits_spent: number; is_available: boolean;
}
interface ProfileForm {
  business_name: string; bio: string; phone: string;
  suburb: string; state: string; postcode: string;
  radius_km: number; is_available: boolean; abn: string; avatar_url: string;
}
interface PrefForm {
  accept_residential: boolean; accept_commercial: boolean;
  notifications_email: boolean; notifications_sms: boolean;
}
interface ServiceArea { suburb: string; postcode: string; state_code: string; }
interface CategoryItem { id: string; name: string; slug?: string; description?: string | null; }

interface TradiePass {
  abn_verified?: boolean;
  white_card_verified?: boolean;
  wc_verified?: boolean;
}
interface CertEntry {
  id: string; category_id: string; category_name?: string;
  licence_number: string; issuing_state: string; issuing_body?: string;
  holder_name: string; issued_at?: string; expires_at?: string;
  photo_url?: string; status: string; rejection_reason?: string;
  rejection_note?: string; verified_at?: string; team_member_id?: string;
  created_at: string;
}
interface InsurancePolicyEntry {
  id: string; insurance_type: string; insurer_name: string;
  policy_number: string; coverage_amount_cents: number;
  holder_name: string; expires_at: string; status: string;
  rejection_reason?: string; rejection_note?: string; verified_at?: string;
  created_at: string;
}
interface TeamMemberSummary {
  id: string; full_name: string; email: string; role: string;
  is_active: boolean; can_accept_jobs: boolean;
  certifications: CertEntry[];
  no_show_count: number; jobs_completed: number;
}
interface OnboardingStatusData {
  profile: {
    id: string; business_name: string; verification_status: string;
    is_available: boolean; solo_or_team: string; verification_notes?: string;
  };
  certifications: CertEntry[];
  insurance_policies: InsurancePolicyEntry[];
  team_members: TeamMemberSummary[];
  gates: {
    profile_approved: boolean; has_verified_cert: boolean;
    has_verified_insurance: boolean; ready_to_receive_jobs: boolean;
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const isNew = (s: string) => s === 'sent' || s === 'pending';
const daysUntil = (d: string) => Math.ceil((new Date(d).getTime() - Date.now()) / 86400000);
const timeAgo = (d: string) => {
  try {
    const m = Math.floor((Date.now() - new Date(d).getTime()) / 60000);
    if (m < 1) return 'just now'; if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h`; return `${Math.floor(h / 24)}d`;
  } catch { return ''; }
};
const fmtBudget = (a?: number, b?: number) => {
  if (!a && !b) return null;
  if (a && b) return `$${a.toLocaleString()}–$${b.toLocaleString()}`;
  return b ? `Up to $${b.toLocaleString()}` : `From $${a!.toLocaleString()}`;
};
const fmtDate = (d?: string) => {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { return d; }
};
const fmtCoverage = (cents: number) =>
  `$${(cents / 100).toLocaleString('en-AU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

const URGENCY: Record<string, { label: string; dot: string; weight: number }> = {
  emergency: { label: 'Emergency', dot: C.rose, weight: 5 },
  asap: { label: 'ASAP', dot: C.amber, weight: 4 },
  today: { label: 'Today', dot: C.amber, weight: 4 },
  next_few_days: { label: 'This week', dot: C.brass, weight: 3 },
  next_few_weeks: { label: 'Soon', dot: C.ink3, weight: 2 },
  flexible: { label: 'Flexible', dot: C.ink4, weight: 1 },
};
const AU_STATES = ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT'];
const SUBURB_COORDS: Record<string, [number, number]> = {
  'surry hills': [-33.886, 151.211], 'redfern': [-33.893, 151.204], 'newtown': [-33.897, 151.179],
  'pyrmont': [-33.870, 151.194], 'bondi': [-33.891, 151.274], 'parramatta': [-33.815, 151.002],
  'sydney': [-33.868, 151.209], 'melbourne': [-37.814, 144.963], 'brisbane': [-27.469, 153.025],
  'council of the city of sydney': [-33.868, 151.209], 'surfers paradise': [-27.999, 153.431],
};
function getCoords(s?: string): [number, number] | null {
  if (!s) return null; const k = s.toLowerCase();
  for (const [key, val] of Object.entries(SUBURB_COORDS)) {
    if (k.includes(key) || key.includes(k.split(',')[0].trim())) return val;
  }
  return null;
}

// ─── Category icon / accent helpers ──────────────────────────────────────────
const getCatIcon = (name: string): any => {
  const n = name.toLowerCase();
  if (n.includes('electric')) return Zap;
  if (n.includes('build') || n.includes('construct')) return Building2;
  if (n.includes('security') || n.includes('plumb') || n.includes('gas')) return Shield;
  return Award;
};
const getCatAccent = (name: string) => {
  const n = name.toLowerCase();
  if (n.includes('electric')) return { bg: '#FFF7ED', color: '#C2410C', border: '#FED7AA' };
  if (n.includes('build') || n.includes('construct')) return { bg: '#EFF6FF', color: '#1D4ED8', border: '#BFDBFE' };
  if (n.includes('security')) return { bg: '#F5F3FF', color: '#7C3AED', border: '#DDD6FE' };
  return { bg: C.brassL, color: C.brass, border: C.brassB };
};

// ─── Status badge ─────────────────────────────────────────────────────────────
const CERT_STATUS: Record<string, { bg: string; color: string; label: string }> = {
  pending: { bg: C.amberL, color: C.amber, label: 'In review' },
  in_review: { bg: '#EEE8FF', color: '#5B3FA6', label: 'In review' },
  verified: { bg: C.sageL, color: C.sage, label: '✓ Verified' },
  rejected: { bg: C.roseL, color: C.rose, label: 'Rejected' },
  expired: { bg: C.roseL, color: C.rose, label: 'Expired' },
};
function StatusBadge({ status }: { status: string }) {
  const s = CERT_STATUS[status] || { bg: C.panel, color: C.ink3, label: status };
  return (
    <span style={{
      fontSize: 11, fontWeight: 700, padding: '4px 12px', borderRadius: 20,
      background: s.bg, color: s.color, whiteSpace: 'nowrap', border: `1px solid ${s.color}25`
    }}>
      {s.label}
    </span>
  );
}

export default function TradieDashboard() {
  return (
    <Suspense fallback={
      <div style={{ minHeight: '100vh', background: C.paper, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Loader2 size={22} color={C.brass} className="animate-spin" />
      </div>
    }>
      <TradieDashboardContent />
    </Suspense>
  );
}

const INSURANCE_LABELS: Record<string, string> = {
  public_liability: 'Public liability insurance',
  workers_compensation: "Workers' Compensation",
  professional_indemnity: 'Professional Indemnity',
};
const REJECTION_LABELS: Record<string, string> = {
  invalid_number: 'Licence number not found in registry',
  expired: 'Licence has lapsed / expired',
  name_mismatch: 'Holder name does not match registry',
  wrong_category: 'Licence is for a different trade',
  cannot_verify: 'Registry unavailable or photo unclear',
  insufficient_cover: 'Coverage below required minimum',
  other: 'See rejection note',
};

// ═══ QUOTE MODAL ══════════════════════════════════════════════════════════════
function QuoteModal({ lead, onClose, onSuccess }: { lead: LeadCard; onClose: () => void; onSuccess: () => void }) {
  const [amount, setAmount] = useState('');
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  const urg = URGENCY[lead.job_urgency || ''] || URGENCY.flexible;

  const submit = async () => {
    if (!amount || Number(amount) <= 0) { setErr('Enter a valid amount.'); return; }
    if (message.trim().length < 10) { setErr('Message too short — min 10 characters.'); return; }
    setSaving(true); setErr('');
    try {
      await api.post('/quotes', { lead_id: lead.id, amount: Number(amount), message: message.trim() });
      toast.success('Quote sent.'); onSuccess(); onClose();
    } catch (e: any) {
      const d = e?.response?.data?.detail;
      setErr(typeof d === 'string' ? d : 'Failed. Please try again.');
    } finally { setSaving(false); }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(26,26,26,0.42)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
      <motion.div initial={{ opacity: 0, y: 20, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.98 }} transition={{ type: 'spring', damping: 28, stiffness: 320 }}
        onClick={e => e.stopPropagation()} className="quote-modal"
        style={{ width: '100%', maxWidth: 500, background: C.card, borderRadius: 16, overflow: 'hidden', boxShadow: SHADOW_LG, border: `1px solid ${C.line}`, maxHeight: '92vh', overflowY: 'auto' }}>
        <div style={{ padding: '24px 28px 20px', borderBottom: `1px solid ${C.lineSoft}`, position: 'relative' }}>
          <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, width: 30, height: 30, borderRadius: 8, background: 'transparent', border: `1px solid ${C.line}`, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.ink3 }}>
            <X size={14} />
          </button>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', background: C.panel, border: `1px solid ${C.line}`, borderRadius: 20, marginBottom: 12 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: urg.dot }} />
            <span style={{ fontSize: 11, fontWeight: 600, color: C.ink2, letterSpacing: '0.02em' }}>{urg.label}</span>
          </div>
          <h2 style={{ fontFamily: DISPLAY, fontSize: 24, fontWeight: 500, color: C.ink, margin: '0 0 6px', lineHeight: 1.15, letterSpacing: '-0.02em', paddingRight: 32 }}>{lead.job_title}</h2>
          {lead.job_suburb && (
            <p style={{ fontSize: 13, color: C.ink3, margin: 0, display: 'flex', alignItems: 'center', gap: 5 }}>
              <MapPin size={12} />{lead.job_suburb}, {lead.job_state}
            </p>
          )}
        </div>
        {lead.job_description && (
          <div style={{ padding: '16px 28px', background: C.paper, borderBottom: `1px solid ${C.lineSoft}` }}>
            <p style={{ fontSize: 10, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.12em', margin: '0 0 8px' }}>Brief</p>
            <p style={{ fontSize: 14, color: C.ink2, lineHeight: 1.6, margin: 0 }}>{lead.job_description}</p>
          </div>
        )}
        <div style={{ padding: '22px 28px 26px', display: 'flex', flexDirection: 'column', gap: 18 }}>
          {err && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: C.roseL, border: `1px solid ${C.rose}30`, color: C.rose, padding: '10px 14px', borderRadius: 10, fontSize: 13 }}>
              <AlertCircle size={14} />{err}
            </div>
          )}
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: C.ink2, textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 8 }}>Your quote <span style={{ color: C.rose }}>*</span></label>
            <div style={{ position: 'relative' }}>
              <span style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', fontSize: 22, fontWeight: 500, color: C.ink3, fontFamily: DISPLAY }}>$</span>
              <input type="number" min="1" value={amount} onChange={e => setAmount(e.target.value)} placeholder="0" autoFocus
                style={{ width: '100%', padding: '16px 16px 16px 36px', borderRadius: 12, border: `1.5px solid ${C.line}`, fontSize: 30, fontWeight: 500, color: C.ink, outline: 'none', boxSizing: 'border-box', background: C.paper, fontFamily: DISPLAY, letterSpacing: '-0.02em' }}
                onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; }}
                onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; }} />
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: C.ink2, textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 8 }}>Message <span style={{ color: C.rose }}>*</span></label>
            <textarea rows={4} value={message} onChange={e => setMessage(e.target.value)}
              placeholder="Introduce yourself, explain your approach, when you can start…"
              style={{ width: '100%', padding: '12px 14px', borderRadius: 12, border: `1.5px solid ${C.line}`, background: C.paper, fontSize: 14, color: C.ink, lineHeight: 1.6, resize: 'vertical', fontFamily: UI, outline: 'none', boxSizing: 'border-box' }}
              onFocus={e => { e.currentTarget.style.borderColor = C.brass; e.currentTarget.style.background = C.card; }}
              onBlur={e => { e.currentTarget.style.borderColor = C.line; e.currentTarget.style.background = C.paper; }} />
            <p style={{ fontSize: 11, color: C.ink3, marginTop: 6, fontVariantNumeric: 'tabular-nums' }}>{message.length} characters</p>
          </div>
          <button onClick={submit} disabled={saving}
            style={{ width: '100%', padding: '14px', borderRadius: 12, border: 'none', background: saving ? C.ink3 : C.ink, color: C.card, fontSize: 14, fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, transition: 'all 0.2s' }}
            onMouseEnter={e => !saving && (e.currentTarget.style.background = '#000')}
            onMouseLeave={e => !saving && (e.currentTarget.style.background = C.ink)}>
            {saving ? <Loader2 size={15} className="animate-spin" /> : <Send size={14} />}
            {saving ? 'Sending…' : 'Send quote'}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ═══ JOB DETAIL MODAL ════════════════════════════════════════════════════════
function JobDetailModal({ lead, onClose, onQuote }: { lead: LeadCard; onClose: () => void; onQuote: (l: LeadCard) => void }) {
  const [photos, setPhotos] = useState<string[]>([]);
  const [loadingDetails, setLoadingDetails] = useState(true);
  const [existingQuote, setExistingQuote] = useState<{ amount: number; message: string } | null>(null);
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null);
  const urg = URGENCY[lead.job_urgency || ''] || URGENCY.flexible;
  const budget = fmtBudget(lead.job_budget_min, lead.job_budget_max);
  const newLead = isNew(lead.status);

  useEffect(() => {
    const go = async () => {
      setLoadingDetails(true);
      try {
        const [photoRes, quoteRes] = await Promise.allSettled([
          api.get(`/jobs/${lead.job_id}/photos`),
          api.get(`/quotes/my-quote/${lead.id}`),
        ]);
        if (photoRes.status === 'fulfilled') {
          const raw = photoRes.value.data || [];
          setPhotos(raw.map((p: any) => p.url || p.photo_url || p.public_url).filter(Boolean));
        }
        if (quoteRes.status === 'fulfilled') {
          const q = quoteRes.value.data;
          if (q && q.amount !== undefined) setExistingQuote({ amount: q.amount, message: q.message });
        }
      } finally { setLoadingDetails(false); }
    };
    go();
  }, [lead.job_id, lead.id]);

  const navLightbox = (dir: 1 | -1) => (e: React.MouseEvent) => {
    e.stopPropagation();
    setLightboxIdx(i => ((i ?? 0) + dir + photos.length) % photos.length);
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(26,26,26,0.50)', backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px' }}>
      <AnimatePresence>
        {lightboxIdx !== null && photos[lightboxIdx] && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={e => { e.stopPropagation(); setLightboxIdx(null); }}
            style={{ position: 'fixed', inset: 0, zIndex: 10001, background: 'rgba(10,10,10,0.96)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <motion.img key={lightboxIdx} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
              src={photos[lightboxIdx]} alt={`Photo ${lightboxIdx + 1}`} onClick={e => e.stopPropagation()}
              style={{ maxWidth: '90vw', maxHeight: '88vh', objectFit: 'contain', borderRadius: 10, boxShadow: '0 40px 100px rgba(0,0,0,0.6)' }} />
            {photos.length > 1 && <>
              <button onClick={navLightbox(-1)} style={{ position: 'absolute', left: 20, top: '50%', transform: 'translateY(-50%)', width: 48, height: 48, borderRadius: '50%', background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)', color: 'white', fontSize: 22, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>‹</button>
              <button onClick={navLightbox(1)} style={{ position: 'absolute', right: 20, top: '50%', transform: 'translateY(-50%)', width: 48, height: 48, borderRadius: '50%', background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)', color: 'white', fontSize: 22, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>›</button>
            </>}
            <button onClick={e => { e.stopPropagation(); setLightboxIdx(null); }} style={{ position: 'absolute', top: 18, right: 18, width: 38, height: 38, borderRadius: 10, background: 'rgba(255,255,255,0.12)', border: '1px solid rgba(255,255,255,0.15)', color: 'white', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <X size={16} />
            </button>
            <span style={{ position: 'absolute', bottom: 18, left: '50%', transform: 'translateX(-50%)', color: 'rgba(255,255,255,0.5)', fontSize: 12, fontWeight: 600 }}>{lightboxIdx + 1} / {photos.length}</span>
          </motion.div>
        )}
      </AnimatePresence>
      <motion.div initial={{ opacity: 0, y: 20, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 10, scale: 0.98 }} transition={{ type: 'spring', damping: 28, stiffness: 320 }}
        onClick={e => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 660, background: C.card, borderRadius: 18, overflow: 'hidden', boxShadow: SHADOW_LG, border: `1px solid ${C.line}`, maxHeight: '92vh', display: 'flex', flexDirection: 'column' }}>
        <div style={{ padding: '24px 28px 20px', borderBottom: `1px solid ${C.lineSoft}`, position: 'relative', flexShrink: 0 }}>
          <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, width: 30, height: 30, borderRadius: 8, background: 'transparent', border: `1px solid ${C.line}`, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.ink3 }}><X size={14} /></button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, flexWrap: 'wrap', paddingRight: 40 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', background: C.panel, border: `1px solid ${C.line}`, borderRadius: 20 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: urg.dot }} />
              <span style={{ fontSize: 11, fontWeight: 600, color: C.ink2 }}>{urg.label}</span>
            </div>
            {lead.is_urgent && <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 4, background: C.roseL, color: C.rose, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Urgent</span>}
            <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 20, background: newLead ? C.brassL : C.sageL, color: newLead ? C.brass : C.sage, border: `1px solid ${newLead ? C.brassB : C.sage + '30'}`, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              {newLead ? 'New' : lead.status === 'accepted' ? 'Won' : 'Quoted'}
            </span>
          </div>
          <h2 style={{ fontFamily: DISPLAY, fontSize: 26, fontWeight: 500, color: C.ink, margin: '0 0 10px', lineHeight: 1.15, letterSpacing: '-0.02em', paddingRight: 32 }}>{lead.job_title || 'Untitled job'}</h2>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            {lead.job_suburb && <span style={{ fontSize: 13, color: C.ink3, display: 'flex', alignItems: 'center', gap: 4 }}><MapPin size={12} />{lead.job_suburb}, {lead.job_state}</span>}
            {budget && <span style={{ fontSize: 13, fontWeight: 700, color: C.brass }}>{budget}</span>}
            <span style={{ fontSize: 13, color: C.ink3, display: 'flex', alignItems: 'center', gap: 4 }}><Clock size={12} />{timeAgo(lead.sent_at)}</span>
          </div>
        </div>
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {lead.job_description && (
            <div style={{ padding: '20px 28px', borderBottom: `1px solid ${C.lineSoft}` }}>
              <p style={{ fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.12em', margin: '0 0 10px' }}>Job brief</p>
              <p style={{ fontSize: 14.5, color: C.ink2, lineHeight: 1.75, margin: 0 }}>{lead.job_description}</p>
            </div>
          )}
          <div style={{ padding: '20px 28px', borderBottom: `1px solid ${C.lineSoft}` }}>
            <p style={{ fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.12em', margin: '0 0 14px' }}>Photos{photos.length > 0 ? ` · ${photos.length}` : ''}</p>
            {loadingDetails ? (
              <div style={{ display: 'flex', gap: 8 }}>{[1, 2, 3].map(i => <div key={i} style={{ width: 130, height: 98, borderRadius: 8, background: C.panel, flexShrink: 0 }} />)}</div>
            ) : photos.length === 0 ? (
              <div style={{ padding: '18px 0', display: 'flex', alignItems: 'center', gap: 10, color: C.ink4 }}>
                <ImageIcon size={16} /><span style={{ fontSize: 13 }}>No photos attached.</span>
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8 }}>
                {photos.map((url, idx) => (
                  <div key={idx} onClick={() => setLightboxIdx(idx)} style={{ aspectRatio: '4/3', borderRadius: 10, overflow: 'hidden', cursor: 'pointer', background: C.panel, border: `1px solid ${C.line}` }}>
                    <img src={url} alt={`Photo ${idx + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  </div>
                ))}
              </div>
            )}
          </div>
          {!newLead && (
            <div style={{ padding: '20px 28px' }}>
              <p style={{ fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.12em', margin: '0 0 14px' }}>Your submitted quote</p>
              {loadingDetails ? <div style={{ height: 80, borderRadius: 10, background: C.panel }} />
                : existingQuote ? (
                  <div style={{ padding: '18px 20px', background: C.brassL, border: `1px solid ${C.brassB}`, borderRadius: 12 }}>
                    <p style={{ fontFamily: DISPLAY, fontSize: 32, fontWeight: 500, color: C.ink, margin: '0 0 10px' }}>${existingQuote.amount.toLocaleString()}</p>
                    <p style={{ fontSize: 14, color: C.ink2, margin: 0, lineHeight: 1.65 }}>{existingQuote.message}</p>
                  </div>
                ) : <p style={{ fontSize: 13, color: C.ink4, fontStyle: 'italic', margin: 0 }}>Quote details unavailable.</p>}
            </div>
          )}
        </div>
        <div style={{ padding: '14px 28px', borderTop: `1px solid ${C.lineSoft}`, display: 'flex', gap: 10, justifyContent: 'flex-end', flexShrink: 0 }}>
          <button onClick={onClose} style={{ padding: '10px 18px', borderRadius: 10, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>Close</button>
          {newLead && (
            <button onClick={() => { onClose(); onQuote(lead); }}
              style={{ padding: '10px 22px', borderRadius: 10, border: 'none', background: C.ink, color: C.card, fontSize: 13, fontWeight: 600, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
              onMouseEnter={e => e.currentTarget.style.background = '#000'}
              onMouseLeave={e => e.currentTarget.style.background = C.ink}>
              <Send size={13} /> Send quote
            </button>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}

// ═══ LEAD ROW ════════════════════════════════════════════════════════════════
function LeadRow({ lead, onQuote, onView, onMarkComplete, selected, onClick }: {
  lead: LeadCard; onQuote: (l: LeadCard) => void; onView: (l: LeadCard) => void;
  onMarkComplete?: (l: LeadCard) => void;
  selected?: boolean; onClick?: () => void;
}) {
  const budget = fmtBudget(lead.job_budget_min, lead.job_budget_max);
  const urg = URGENCY[lead.job_urgency || ''] || URGENCY.flexible;
  const newLead = isNew(lead.status);
  return (
    <div onClick={onClick} className="lead-row"
      style={{ background: selected ? C.brassL : 'transparent', borderLeft: `2px solid ${selected ? C.brass : 'transparent'}`, borderBottom: `1px solid ${C.lineSoft}`, cursor: onClick ? 'pointer' : 'default', transition: 'background 0.15s ease' }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = C.paper; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = 'transparent'; }}>
      <div className="lead-row-inner" style={{ padding: '18px 24px' }}>
        <div className="lead-row-status"><div style={{ width: 8, height: 8, borderRadius: '50%', background: urg.dot, flexShrink: 0, boxShadow: newLead ? `0 0 0 3px ${urg.dot}25` : 'none' }} /></div>
        <div className="lead-row-content">
          <div className="lead-row-title-row">
            <h3 style={{ fontSize: 14.5, fontWeight: 600, color: C.ink, margin: 0, letterSpacing: '-0.005em', lineHeight: 1.35 }}>{lead.job_title || 'Untitled job'}</h3>
            {lead.is_urgent && <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: C.roseL, color: C.rose, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Urgent</span>}
          </div>
          {lead.job_description && <p className="lead-row-desc" style={{ fontSize: 13, color: C.ink3, margin: '4px 0 0', lineHeight: 1.5 }}>{lead.job_description}</p>}
          <div className="lead-row-meta" style={{ marginTop: 8 }}>
            {lead.job_suburb && <span style={{ fontSize: 12, color: C.ink3, display: 'inline-flex', alignItems: 'center', gap: 4 }}><MapPin size={11} />{lead.job_suburb}</span>}
            <span style={{ fontSize: 12, color: C.ink3, display: 'inline-flex', alignItems: 'center', gap: 4 }}><Clock size={11} />{timeAgo(lead.sent_at)}</span>
            <span style={{ fontSize: 12, color: C.ink3, display: 'inline-flex', alignItems: 'center', gap: 4 }}><CircleDot size={11} />{urg.label}</span>
          </div>
        </div>
        {budget && (
          <div className="lead-row-budget">
            <p style={{ fontSize: 10, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 2px' }}>Budget</p>
            <p style={{ fontSize: 14, fontWeight: 600, color: C.ink, margin: 0, fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{budget}</p>
          </div>
        )}
        <div className="lead-row-action">
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
            <button onClick={e => { e.stopPropagation(); onView(lead); }}
              style={{ padding: '7px 11px', borderRadius: 8, border: `1px solid ${C.line}`, background: C.paper, color: C.ink3, fontSize: 12, fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4, transition: 'all 0.15s', whiteSpace: 'nowrap' }}
              onMouseEnter={e => { e.currentTarget.style.background = C.card; e.currentTarget.style.color = C.ink; }}
              onMouseLeave={e => { e.currentTarget.style.background = C.paper; e.currentTarget.style.color = C.ink3; }}>
              <Eye size={11} /> View
            </button>
            {lead.job_status === 'confirmed' ? (
              /* Homeowner confirmed — job done, payment released */
              <span style={{ fontSize: 11, fontWeight: 700, padding: '5px 10px', borderRadius: 6, background: C.sageL, color: C.sage, border: `1px solid ${C.sage}30`, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <CheckCircle size={11} /> Confirmed
              </span>
            ) : lead.job_status === 'completed' ? (
              /* Tradie marked done — waiting for homeowner to confirm */
              <span style={{ fontSize: 11, fontWeight: 700, padding: '5px 10px', borderRadius: 6, background: C.amberL, color: C.amber, border: `1px solid ${C.amber}30`, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <Hourglass size={11} /> Awaiting confirmation
              </span>
            ) : lead.job_status === 'partial_stop' ? (
              <span style={{ fontSize: 11, fontWeight: 700, padding: '5px 10px', borderRadius: 6, background: C.roseL, color: C.rose, border: `1px solid ${C.rose}30`, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>
                Partial stop
              </span>
            ) : lead.job_status === 'awaiting_scope_approval' ? (
              <span style={{ fontSize: 11, fontWeight: 700, padding: '5px 10px', borderRadius: 6, background: C.brassL, color: C.brass, border: `1px solid ${C.brassB}`, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>
                Scope pending
              </span>
            ) : (lead.job_status === 'in_progress' || lead.job_status === 'hired') ? (
              <button
                onClick={e => { e.stopPropagation(); onMarkComplete?.(lead); }}
                style={{ padding: '7px 13px', borderRadius: 8, border: `1px solid ${C.sage}50`, background: C.sageL, color: C.sage, fontSize: 12, fontWeight: 700, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap', transition: 'all 0.15s' }}
                onMouseEnter={e => { e.currentTarget.style.background = C.sage; e.currentTarget.style.color = C.card; }}
                onMouseLeave={e => { e.currentTarget.style.background = C.sageL; e.currentTarget.style.color = C.sage; }}>
                <CheckCircle size={12} /> Mark complete
              </button>
            ) : newLead ? (
              <button onClick={e => { e.stopPropagation(); onQuote(lead); }}
                style={{ padding: '8px 14px', borderRadius: 8, border: `1px solid ${C.ink}`, background: C.ink, color: C.card, fontSize: 12.5, fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap', transition: 'all 0.15s' }}
                onMouseEnter={e => e.currentTarget.style.background = '#000'}
                onMouseLeave={e => e.currentTarget.style.background = C.ink}>
                Quote<ArrowUpRight size={12} />
              </button>
            ) : (
              <span style={{ fontSize: 11, fontWeight: 600, padding: '5px 10px', borderRadius: 6, background: lead.status === 'accepted' ? C.sageL : C.brassL, color: lead.status === 'accepted' ? C.sage : C.brass, border: `1px solid ${lead.status === 'accepted' ? C.sage + '30' : C.brassB}`, textTransform: 'uppercase', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>
                {lead.status === 'accepted' ? 'Won' : 'Quoted'}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══ MAP ══════════════════════════════════════════════════════════════════════
function LeadMap({ leads, selectedId, onSelect }: { leads: LeadCard[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const mkRef = useRef<Record<string, any>>({});

  useEffect(() => {
    if (typeof window === 'undefined' || !ref.current) return;
    if (!document.getElementById('lf-css')) {
      const l = document.createElement('link'); l.id = 'lf-css'; l.rel = 'stylesheet';
      l.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'; document.head.appendChild(l);
    }
    const init = () => {
      const L = (window as any).L; if (!L || mapRef.current) return;
      mapRef.current = L.map(ref.current, { center: [-33.868, 151.209], zoom: 12, zoomControl: false });
      L.control.zoom({ position: 'bottomright' }).addTo(mapRef.current);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: '© OpenStreetMap © CARTO', maxZoom: 19 }).addTo(mapRef.current);
    };
    if ((window as any).L) init();
    else if (!document.getElementById('lf-js')) {
      const s = document.createElement('script'); s.id = 'lf-js';
      s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'; s.onload = init; document.body.appendChild(s);
    } else { const t = setInterval(() => { if ((window as any).L) { clearInterval(t); init(); } }, 100); }
    return () => { if (mapRef.current) { mapRef.current.remove(); mapRef.current = null; mkRef.current = {}; } };
  }, []);

  useEffect(() => {
    const L = (window as any).L; if (!L || !mapRef.current) return;
    Object.values(mkRef.current).forEach((m: any) => m.remove()); mkRef.current = {};
    const bounds: [number, number][] = [];
    leads.forEach(lead => {
      const c = getCoords(lead.job_suburb); if (!c) return;
      const sel = selectedId === lead.id; const nw = isNew(lead.status); const size = sel ? 32 : 24;
      const icon = L.divIcon({ className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2], html: `<div style="width:${size}px;height:${size}px;border-radius:50%;background:${sel ? C.ink : nw ? C.brass : C.card};border:2px solid ${C.card};box-shadow:0 2px 8px rgba(26,26,26,0.18);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:${sel ? C.card : nw ? C.card : C.ink3}">${nw ? '!' : '✓'}</div>` });
      const budget = fmtBudget(lead.job_budget_min, lead.job_budget_max);
      const marker = L.marker(c, { icon }).addTo(mapRef.current)
        .bindPopup(`<div style="min-width:160px;font-family:${UI}"><p style="font-weight:600;font-size:13px;margin:0 0 4px;color:${C.ink}">${lead.job_title || 'Job'}</p><p style="font-size:12px;color:${C.ink3};margin:0">${lead.job_suburb}, ${lead.job_state}</p>${budget ? `<p style="font-size:13px;font-weight:700;margin:6px 0 0;color:${C.brass}">${budget}</p>` : ''}</div>`);
      marker.on('click', () => onSelect(lead.id));
      mkRef.current[lead.id] = marker;
      bounds.push(c);
    });
    if (bounds.length > 0) { try { mapRef.current.fitBounds(bounds, { padding: [48, 48], maxZoom: 13 }); } catch { } }
  }, [leads, selectedId]);

  useEffect(() => {
    if (!selectedId || !mapRef.current) return;
    const lead = leads.find(l => l.id === selectedId); if (!lead) return;
    const c = getCoords(lead.job_suburb);
    if (c) { mapRef.current.setView(c, 14, { animate: true }); mkRef.current[selectedId]?.openPopup(); }
  }, [selectedId]);

  const mappedCount = leads.filter(l => getCoords(l.job_suburb)).length;
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', borderRadius: 12, overflow: 'hidden', background: C.panel, border: `1px solid ${C.line}`, isolation: 'isolate', zIndex: 0 }}>
      <div ref={ref} style={{ width: '100%', height: '100%' }} />
      <div style={{ position: 'absolute', top: 14, left: 14, zIndex: 1000, background: C.card, border: `1px solid ${C.line}`, fontSize: 11, fontWeight: 600, color: C.ink2, padding: '6px 12px', borderRadius: 8, pointerEvents: 'none', boxShadow: SHADOW_SM, display: 'flex', alignItems: 'center', gap: 6 }}>
        <MapPin size={11} color={C.brass} />{mappedCount} on map
      </div>
    </div>
  );
}

// ═══ [Licence & Insurance modals removed] ════════════════════════════════════
// All document entry (licences, insurance, white card) is handled exclusively
// through the onboarding flow (/tradie/onboarding). The dashboard licences tab
// now redirects to /tradie/licences for read-only viewing and edit requests.

// ═══ MAIN COMPONENT ═══════════════════════════════════════════════════════════
type TabId = 'overview' | 'leads' | 'active' | 'licences' | 'preferences' | 'profile';

function TradieDashboardContent() {
  const { user, logout, isLoading: authLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  // Open specific tab when navigated here with ?tab=... etc.
  // Note: 'licences' is handled by the dedicated /tradie/licences page — redirect there.
  useEffect(() => {
    const t = searchParams.get('tab') as TabId | null;
    if (t === 'licences') { router.push('/tradie/licences'); return; }
    if (t && ['overview', 'leads', 'active', 'profile'].includes(t)) {
      setTab(t);
    } else if (!t) {
      // No ?tab= param means the user clicked "Overview" in the sidebar.
      // Without this branch the tab never switches back to overview after
      // visiting leads/active (the old if(t&&...) condition is always false
      // when t is null, so setTab was never called).
      setTab('overview');
    }
  }, [searchParams]);

  const [leads, setLeads] = useState<LeadCard[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [quoting, setQuoting] = useState<LeadCard | null>(null);
  const [viewing, setViewing] = useState<LeadCard | null>(null);
  const [markCompleteLead, setMarkCompleteLead] = useState<LeadCard | null>(null);
  const [tab, setTab] = useState<TabId>('overview');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [prof, setProf] = useState<ProfileForm>({ business_name: '', bio: '', phone: '', suburb: '', state: '', postcode: '', radius_km: 25, is_available: true, abn: '', avatar_url: '' });
  const [profSaving, setProfSaving] = useState(false);
  const [profLoaded, setProfLoaded] = useState(false);
  const [avatarUploading, setAvatarUploading] = useState(false);
  const avatarInputRef = useRef<HTMLInputElement>(null);

  const [onboardingStatus, setOnboardingStatus] = useState<OnboardingStatusData | null>(null);

  const [pref, setPref] = useState<PrefForm>({ accept_residential: true, accept_commercial: true, notifications_email: true, notifications_sms: false });
  const [prefSaving, setPrefSaving] = useState(false);
  const [prefLoaded, setPrefLoaded] = useState(false);
  const [serviceAreas, setServiceAreas] = useState<ServiceArea[]>([]);
  const [prefStateFilter, setPrefStateFilter] = useState('');
  const [suburbQuery, setSuburbQuery] = useState('');
  const [suburbResults, setSuburbResults] = useState<any[]>([]);
  const [suburbSearching, setSuburbSearching] = useState(false);
  const suburbTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [allCategories, setAllCategories] = useState<CategoryItem[]>([]);
  const [selectedCatIds, setSelectedCatIds] = useState<string[]>([]);
  const [originalCatIds, setOriginalCatIds] = useState<string[]>([]);
  const [catSearchQuery, setCatSearchQuery] = useState('');
  const [serviceLevelFilter, setServiceLevelFilter] = useState<'all' | 'strict' | 'standard' | 'basic'>('all');
  const [catLoaded, setCatLoaded] = useState(false);
  const [previewCatId, setPreviewCatId] = useState<string | null>(null);
  const [confirmAddCat, setConfirmAddCat] = useState<CategoryItem | null>(null);

  // ── Auth guard ───────────────────────────────────────────────────────────────
  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) { router.push('/login'); return; }
    if (user?.role === 'homeowner') { router.push('/dashboard'); return; }
    if (user?.role === 'tradie') {
      api.get('/tradies/profile/me').catch(err => {
        if (err?.response?.status === 404) { router.push('/tradie/onboarding'); }
      });
    }
  }, [authLoading, isAuthenticated, user, router]);

  // ── Load dashboard ───────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const { data } = await api.get('/tradies/dashboard/me');
      setStats(data.stats); setLeads(data.leads || []);
      if (data.stats?.is_available !== undefined) setProf(p => ({ ...p, is_available: data.stats.is_available }));
    } catch { } finally { setLoading(false); }
  }, [user]);
  useEffect(() => { load(); }, [load]);

  // isApproved, verificationStatus, isAvailable come from TradieStudioLayout ctx

  // ── Load profile ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (tab !== 'profile' || profLoaded) return;
    api.get('/tradies/profile/me').then(r => {
      const d = r.data;
      setProf({ business_name: d.business_name || '', bio: d.bio || '', phone: d.phone || '', suburb: d.suburb || '', state: d.state || '', postcode: d.postcode || '', radius_km: d.radius_km || 25, is_available: d.is_available ?? true, abn: d.abn || '', avatar_url: d.avatar_url || '' });
      setProfLoaded(true);
    }).catch(() => setProfLoaded(true));
  }, [tab, profLoaded]);

  // ── Load preferences ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (tab !== 'preferences' || prefLoaded) return;
    api.get('/tradies/preferences/me').then(r => {
      const d = r.data;
      setPref({ accept_residential: d.accept_residential ?? true, accept_commercial: d.accept_commercial ?? true, notifications_email: d.notify_email ?? true, notifications_sms: d.notify_sms ?? false });
      setServiceAreas(d.service_suburbs || []); setPrefLoaded(true);
    }).catch(() => setPrefLoaded(true));
  }, [tab, prefLoaded]);

  // ── Load categories (preferences only) ────────────────────────────────────────
  useEffect(() => {
    if (tab !== 'preferences' || catLoaded) return;
    Promise.allSettled([api.get('/tradies/categories/tree'), api.get('/categories/my-categories')]).then(([allRes, myRes]) => {
      const cats: CategoryItem[] = allRes.status === 'fulfilled' ? (allRes.value.data?.categories || []) : [];
      setAllCategories(cats);
      if (myRes.status === 'fulfilled') {
        const myIds = (myRes.value.data || []).map((c: any) => c.category_id || c.id);
        setSelectedCatIds(myIds); setOriginalCatIds(myIds);
      }
      setCatLoaded(true);
    });
  }, [tab, catLoaded]);

  // ── Load onboarding status (used by preferences tab for verified-licence checks) ────
  useEffect(() => {
    if (tab !== 'preferences') return;
    Promise.allSettled([
      api.get('/tradies/onboarding/status'),
      !profLoaded ? api.get('/tradies/profile/me') : Promise.resolve({ data: null }),
      api.get('/tradies/categories/tree'),
      api.get('/categories/my-categories'),
      api.get('/tradies/preferences/me').catch(() => ({ data: null })),
    ]).then(([statusRes, passRes, profileRes, catsRes, myCatsRes, prefRes]) => {
      if (statusRes.status === 'fulfilled') setOnboardingStatus(statusRes.value.data);
      else toast.error('Could not load verification status.');
      if (profileRes.status === 'fulfilled' && profileRes.value.data) {
        const d = profileRes.value.data;
        setProf(p => ({ ...p, abn: d.abn || p.abn, business_name: d.business_name || p.business_name, avatar_url: d.avatar_url || p.avatar_url }));
        setProfLoaded(true);
      }
      if (catsRes.status === 'fulfilled') setAllCategories(catsRes.value.data?.categories || []);
      if (myCatsRes.status === 'fulfilled') {
        const myIds = (myCatsRes.value.data || []).map((c: any) => c.category_id || c.id);
        setSelectedCatIds(myIds);
        if (!catLoaded) { setOriginalCatIds(myIds); setCatLoaded(true); }
      }
      // service_suburbs tells us which of the 8 AU states the tradie operates in
      if (prefRes.status === 'fulfilled' && prefRes.value.data?.service_suburbs) {
        setServiceAreas(prefRes.value.data.service_suburbs);
      }
    });
  }, [tab]);

  const saveProfile = async () => {
    setProfSaving(true);
    try { await api.patch('/tradies/profile/me', prof); toast.success('Profile saved.'); }
    catch { toast.error('Could not save profile.'); } finally { setProfSaving(false); }
  };

  const savePrefs = async () => {
    setPrefSaving(true);
    try {
      await api.patch('/tradies/preferences/me', { accept_residential: pref.accept_residential, accept_commercial: pref.accept_commercial, notify_email: pref.notifications_email, notify_sms: pref.notifications_sms, service_suburbs: serviceAreas });
      const toAdd = selectedCatIds.filter(id => !originalCatIds.includes(id));
      const toRemove = originalCatIds.filter(id => !selectedCatIds.includes(id));
      await Promise.all([...toAdd.map(id => api.post(`/categories/my-categories/${id}`).catch(() => { })), ...toRemove.map(id => api.delete(`/categories/my-categories/${id}`).catch(() => { }))]);
      setOriginalCatIds([...selectedCatIds]); toast.success('Preferences saved.');
    } catch { toast.error('Could not save preferences.'); } finally { setPrefSaving(false); }
  };

  const handleAvatarChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    if (file.size > 10_000_000) { toast.error('Image must be under 10 MB.'); return; }
    if (!file.type.startsWith('image/')) { toast.error('Only image files allowed.'); return; }
    setAvatarUploading(true);
    try {
      const fd = new FormData(); fd.append('file', file);
      const res = await fetch('/api/upload-photo', { method: 'POST', body: fd });
      if (!res.ok) throw new Error();
      const { public_url } = await res.json();
      setProf(p => ({ ...p, avatar_url: public_url })); toast.success('Profile photo updated.');
    } catch { toast.error('Could not upload photo.'); } finally { setAvatarUploading(false); e.target.value = ''; }
  };

  const formatAbn = (raw: string) => {
    const d = raw.replace(/\D/g, '').slice(0, 11);
    if (d.length <= 2) return d; if (d.length <= 5) return `${d.slice(0, 2)} ${d.slice(2)}`;
    if (d.length <= 8) return `${d.slice(0, 2)} ${d.slice(2, 5)} ${d.slice(5)}`;
    return `${d.slice(0, 2)} ${d.slice(2, 5)} ${d.slice(5, 8)} ${d.slice(8)}`;
  };
  const formatPhone = (raw: string) => {
    const d = raw.replace(/\D/g, '').slice(0, 10);
    if (d.length <= 4) return d; if (d.length <= 7) return `${d.slice(0, 4)} ${d.slice(4)}`;
    return `${d.slice(0, 4)} ${d.slice(4, 7)} ${d.slice(7)}`;
  };

  // ── Derived ───────────────────────────────────────────────────────────────────
  const newLeads = useMemo(() => leads.filter(l => isNew(l.status)), [leads]);
  // "Active" = any lead where the tradie is still engaged (working, awaiting something, or awaiting homeowner confirmation).
  // hired / in_progress / awaiting_scope_approval / partial_stop / completed all count — only confirmed/closed/cancelled/disputed are "done".
  const ACTIVE_JOB_STATUSES = new Set(['hired', 'in_progress', 'awaiting_scope_approval', 'partial_stop', 'completed']);
  const DONE_JOB_STATUSES = new Set(['confirmed', 'closed']);
  const activeLeads = useMemo(() => leads.filter(l =>
    l.job_status != null ? ACTIVE_JOB_STATUSES.has(l.job_status) : (l.status === 'quoted' || l.status === 'accepted')
  ), [leads]);
  const completedJobsCount = useMemo(() => leads.filter(l => l.job_status != null && DONE_JOB_STATUSES.has(l.job_status)).length, [leads]);
  const firstName = user?.name?.split(' ')[0] || user?.email?.split('@')[0] || 'there';
  const selectedCategories = useMemo(() => allCategories.filter(c => selectedCatIds.includes(c.id)), [allCategories, selectedCatIds]);
  const requiredDocuments = useMemo(() => getRequiredDocuments(selectedCategories), [selectedCategories]);

  // Services grouped by verification group — used in the preferences two-column picker
  const groupedAllCategories = useMemo(() => {
    const q = catSearchQuery.trim().toLowerCase();
    const filtered = allCategories.filter(c => {
      const rule = getServiceRule(c);
      return (!q || c.name.toLowerCase().includes(q)) && (serviceLevelFilter === 'all' || rule.level === serviceLevelFilter);
    }).sort((a, b) => {
      const rank = { strict: 0, standard: 1, basic: 2 } as const;
      return rank[getServiceRule(a).level] - rank[getServiceRule(b).level] || a.name.localeCompare(b.name);
    });
    return filtered.reduce<Record<string, CategoryItem[]>>((acc, cat) => {
      const group = getServiceRule(cat).group;
      (acc[group] = acc[group] || []).push(cat);
      return acc;
    }, {});
  }, [allCategories, catSearchQuery, serviceLevelFilter]);


  // Unique AU states the tradie operates in — sourced from service area selections.
  // Also absorbs any states already in submitted certs (edge case: cert in a state
  // they removed from service areas). Result is always sorted AU_STATES order.
  const tradieStates = useMemo(() => {
    const states = new Set<string>();
    serviceAreas.forEach(sa => { if (sa.state_code) states.add(sa.state_code); });
    if (onboardingStatus) {
      onboardingStatus.certifications.forEach(c => { if (c.issuing_state) states.add(c.issuing_state); });
    }
    // Keep AU_STATES order so display is consistent
    return ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT'].filter(s => states.has(s));
  }, [serviceAreas, onboardingStatus]);


  if (authLoading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: C.paper, fontFamily: UI }}>
        <Loader2 size={24} color={C.brass} className="animate-spin" />
      </div>
    );
  }

  // ─── Shared styles ─────────────────────────────────────────────────────────
  const panelStyle: React.CSSProperties = { background: C.card, borderRadius: 14, border: `1px solid ${C.line}`, boxShadow: SHADOW_SM, overflow: 'hidden' };
  const sectionTitle: React.CSSProperties = { fontSize: 10, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.14em', margin: 0 };
  const secLabel: React.CSSProperties = { fontSize: 9.5, fontWeight: 800, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.18em', margin: 0 };
  const inputStyle: React.CSSProperties = { width: '100%', padding: '11px 14px', borderRadius: 10, border: `1px solid ${C.line}`, background: C.paper, fontSize: 13.5, color: C.ink, outline: 'none', boxSizing: 'border-box', fontFamily: UI, transition: 'all 0.15s' };
  const labelStyle: React.CSSProperties = { fontSize: 11, fontWeight: 600, color: C.ink2, textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 7 };




  const TAB_META: Record<TabId, { title: string; sub: string }> = {
    overview: { title: 'Overview', sub: 'Today at a glance' },
    leads: { title: 'Leads', sub: 'Jobs matched to you' },
    active: { title: 'Active jobs', sub: 'Quotes in flight' },
    licences: { title: 'Licences & Insurance', sub: 'Licences & insurance' },
    preferences: { title: 'Preferences', sub: 'Tune your lead feed' },
    profile: { title: 'Profile', sub: 'Your business details' },
  };

  const Toggle = ({ on, onChange, disabled }: { on: boolean; onChange: (v: boolean) => void; disabled?: boolean }) => (
    <button onClick={() => !disabled && onChange(!on)} disabled={disabled}
      style={{ width: 40, height: 22, borderRadius: 11, background: on ? C.ink : C.line, border: 'none', cursor: disabled ? 'not-allowed' : 'pointer', position: 'relative', transition: 'background 0.2s', flexShrink: 0, opacity: disabled ? 0.5 : 1 }}>
      <div style={{ width: 16, height: 16, borderRadius: '50%', background: C.card, position: 'absolute', top: 3, left: on ? 21 : 3, transition: 'left 0.2s cubic-bezier(0.4,0,0.2,1)', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
    </button>
  );

  return (
    <TradieStudioLayout>
      {(ctx) => {
        const { isApproved, verificationStatus, isAvailable, refreshStatus } = ctx;
        return (
        <>
        <AnimatePresence>
          {quoting && <QuoteModal lead={quoting} onClose={() => setQuoting(null)} onSuccess={load} />}
          {viewing && <JobDetailModal lead={viewing} onClose={() => setViewing(null)} onQuote={l => { setViewing(null); setQuoting(l); }} />}
          {markCompleteLead && (
            <MarkCompleteModal
              jobId={markCompleteLead.job_id}
              jobTitle={markCompleteLead.job_title}
              onClose={() => setMarkCompleteLead(null)}
              onCompleted={() => { setMarkCompleteLead(null); load(); }}
            />
          )}
        </AnimatePresence>

        <div className="app-main" style={{position:"relative"}}>
        <AnimatePresence>
          {!isAvailable && isApproved && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              style={{ position: 'absolute', inset: 0, zIndex: 40, background: `${C.paper}D0`, backdropFilter: 'blur(5px)', WebkitBackdropFilter: 'blur(5px)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16, textAlign: 'center', padding: 32 }}>
              <div style={{ width: 64, height: 64, borderRadius: 18, background: C.card, border: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: SHADOW_MD }}>
                <ZapOff size={26} color={C.ink3} />
              </div>
              <div>
                <p style={{ fontFamily: DISPLAY, fontSize: 26, fontWeight: 500, color: C.ink, margin: '0 0 8px', letterSpacing: '-0.02em' }}>You are offline</p>
                <p style={{ fontSize: 14, color: C.ink3, margin: 0, maxWidth: 340, lineHeight: 1.65 }}>New leads are paused. Toggle your status in the sidebar to go back online.</p>
              </div>
              <button onClick={async () => {
                try { await api.patch('/tradies/availability/toggle'); refreshStatus(); }
                catch { /* ignore */ }
              }} style={{ marginTop: 4, padding: '12px 24px', borderRadius: 10, background: C.ink, color: C.card, border: 'none', fontWeight: 600, fontSize: 13.5, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Zap size={15} fill={C.card} /> Go online
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {verificationStatus && !isApproved && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            style={{ margin: '16px 32px 0', padding: '16px 20px', background: verificationStatus === 'rejected' ? C.roseL : C.brassL, border: `1px solid ${verificationStatus === 'rejected' ? C.rose + '40' : C.brassB}`, borderRadius: 12, display: 'flex', alignItems: 'flex-start', gap: 14 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: verificationStatus === 'rejected' ? C.rose : C.brass, color: C.card, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              {verificationStatus === 'rejected' ? <AlertCircle size={17} /> : <Hourglass size={16} />}
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ fontFamily: DISPLAY, fontSize: 17, fontWeight: 500, color: C.ink, margin: '0 0 4px', letterSpacing: '-0.01em' }}>
                {verificationStatus === 'pending_review' && 'Verification in review'}
                {verificationStatus === 'needs_documents' && 'Documents required'}
                {verificationStatus === 'rejected' && 'Application not approved'}
                {verificationStatus === 'suspended' && 'Account suspended'}
              </p>
              <p style={{ fontSize: 13, color: C.ink2, margin: 0, lineHeight: 1.6 }}>
                {verificationStatus === 'pending_review' && 'Your dashboard unlocks fully once approved — usually within 1 business day.'}
                {verificationStatus === 'needs_documents' && 'Upload the requested documents in the Licences & Docs tab to continue.'}
                {verificationStatus === 'rejected' && 'Contact support@proconnect.com.au to discuss your application.'}
                {verificationStatus === 'suspended' && 'Your account is suspended. Contact support to resolve.'}
              </p>
            </div>
          </motion.div>
        )}

        <header className="app-topbar">
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: 11, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.12em', margin: '0 0 2px' }}>{TAB_META[tab].sub}</p>
            <h1 style={{ fontFamily: DISPLAY, fontSize: 22, fontWeight: 500, color: C.ink, margin: 0, letterSpacing: '-0.02em', lineHeight: 1.1 }}>{TAB_META[tab].title}</h1>
          </div>
        </header>

        <div className="app-content">
          <AnimatePresence mode="wait">

            {/* ─── OVERVIEW ──────────────────────────────────────────────── */}
            {tab === 'overview' && (
              <motion.div key="ov" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                <div style={{ background: C.card, borderRadius: 16, border: `1px solid ${C.line}`, boxShadow: SHADOW_SM, padding: '28px 32px', position: 'relative', overflow: 'hidden' }}>
                  <div style={{ position: 'absolute', top: 0, right: 0, width: 180, height: 180, background: `radial-gradient(circle at 80% 20%, ${C.brassL} 0%, transparent 70%)`, pointerEvents: 'none' }} />
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 20 }}>
                    <div style={{ minWidth: 0, flex: '1 1 300px' }}>
                      <p style={{ fontSize: 12, fontWeight: 600, color: C.brass, margin: '0 0 6px', textTransform: 'uppercase', letterSpacing: '0.14em' }}>G&apos;day, {firstName}</p>
                      <h2 style={{ fontFamily: DISPLAY, fontSize: 32, fontWeight: 400, color: C.ink, margin: '0 0 10px', letterSpacing: '-0.03em', lineHeight: 1.1 }}>
                        {newLeads.length > 0 ? <>You have <em style={{ fontStyle: 'italic', color: C.brass }}>{newLeads.length} new {newLeads.length === 1 ? 'lead' : 'leads'}</em> waiting.</> : 'Your day is clear.'}
                      </h2>
                      <p style={{ fontSize: 14, color: C.ink2, margin: 0, lineHeight: 1.55, maxWidth: 480 }}>
                        {newLeads.length > 0 ? 'Quote fast — most homeowners pick a tradie within 24 hours.' : 'Check back soon. New jobs appear as they come in from your area.'}
                      </p>
                    </div>
                    {newLeads.length > 0 && (
                      <button onClick={() => setTab('leads')}
                        style={{ padding: '12px 20px', borderRadius: 10, background: C.ink, color: C.card, border: 'none', fontSize: 13.5, fontWeight: 600, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 6, transition: 'all 0.15s' }}
                        onMouseEnter={e => e.currentTarget.style.background = '#000'}
                        onMouseLeave={e => e.currentTarget.style.background = C.ink}>
                        Review leads <ArrowUpRight size={14} />
                      </button>
                    )}
                  </div>
                </div>
                <div className="stat-grid">
                  {[
                    { label: 'New leads', value: loading ? '—' : String(newLeads.length), sub: newLeads.length > 0 ? 'Quote to win' : 'Nothing pending', emphasis: newLeads.length > 0 },
                    { label: 'Active jobs', value: loading ? '—' : String(activeLeads.length), sub: activeLeads.length > 0 ? 'In progress or awaiting' : 'None in flight' },
                    { label: 'Total leads', value: loading ? '—' : String(leads.length), sub: 'All time' },
                    { label: 'Completed jobs', value: loading ? '—' : String(completedJobsCount), sub: completedJobsCount > 0 ? 'Confirmed by homeowners' : 'None confirmed yet' },
                  ].map((s, i) => (
                    <div key={i} className="stat-card" style={{ background: C.card, borderRadius: 12, border: `1px solid ${C.line}`, padding: '18px 20px', boxShadow: SHADOW_XS }}>
                      <p style={{ fontSize: 11, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 12px' }}>{s.label}</p>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 4 }}>
                        <p style={{ fontFamily: DISPLAY, fontSize: 36, fontWeight: 400, color: (s as any).emphasis ? C.brass : C.ink, margin: 0, letterSpacing: '-0.03em', lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>{s.value}</p>
                      </div>
                      <p style={{ fontSize: 12, color: C.ink3, margin: 0 }}>{s.sub}</p>
                    </div>
                  ))}
                </div>
                {newLeads.length > 0 && (
                  <div style={panelStyle}>
                    <div style={{ padding: '14px 24px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <p style={sectionTitle}>To quote</p>
                        <span style={{ fontSize: 11, fontWeight: 600, color: C.brass, background: C.brassL, border: `1px solid ${C.brassB}`, padding: '2px 8px', borderRadius: 20 }}>{newLeads.length} new</span>
                      </div>
                      <button onClick={() => setTab('leads')} style={{ fontSize: 12, fontWeight: 600, color: C.ink2, background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3, padding: 0 }}>All leads <ChevronRight size={13} /></button>
                    </div>
                    {newLeads.slice(0, 3).map(l => <LeadRow key={l.id} lead={l} onQuote={setQuoting} onView={setViewing} />)}
                  </div>
                )}
                {/* Active jobs in overview — in-progress and awaiting-confirmation jobs */}
                {!loading && activeLeads.length > 0 && (
                  <div style={panelStyle}>
                    <div style={{ padding: '14px 24px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <p style={sectionTitle}>Active jobs</p>
                        <span style={{ fontSize: 11, fontWeight: 600, color: C.sage, background: C.sageL, border: `1px solid ${C.sage}30`, padding: '2px 8px', borderRadius: 20 }}>{activeLeads.length} in flight</span>
                      </div>
                      <button onClick={() => setTab('active')} style={{ fontSize: 12, fontWeight: 600, color: C.ink2, background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 3, padding: 0 }}>See all <ChevronRight size={13} /></button>
                    </div>
                    {activeLeads.slice(0, 3).map(l => <LeadRow key={l.id} lead={l} onQuote={setQuoting} onView={setViewing} onMarkComplete={setMarkCompleteLead} />)}
                  </div>
                )}
                {!loading && leads.length === 0 && (
                  <div style={panelStyle}>
                    <div style={{ padding: '56px 28px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                      <div style={{ width: 56, height: 56, borderRadius: 14, background: C.paper, border: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.ink3 }}><Bell size={22} /></div>
                      <div>
                        <p style={{ fontFamily: DISPLAY, fontSize: 20, fontWeight: 500, color: C.ink, margin: '0 0 4px', letterSpacing: '-0.015em' }}>No leads yet</p>
                        <p style={{ fontSize: 13.5, color: C.ink3, margin: 0, maxWidth: 300, lineHeight: 1.6 }}>Complete your verification and upload documents to start receiving matched jobs.</p>
                      </div>
                      <button onClick={() => router.push('/tradie/licences')} style={{ marginTop: 6, padding: '10px 18px', borderRadius: 10, background: C.ink, color: C.card, border: 'none', fontWeight: 600, fontSize: 13, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 7 }}><ExternalLink size={14} /> Check licences & docs</button>
                    </div>
                  </div>
                )}
              </motion.div>
            )}

            {/* ─── LEADS ────────────────────────────────────────────────── */}
            {tab === 'leads' && isApproved && (
              <motion.div key="leads" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
                <div className="leads-layout">
                  <div className="leads-list-wrap" style={panelStyle}>
                    <div style={{ padding: '14px 20px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
                      <p style={sectionTitle}>All · {leads.length}</p>
                      {newLeads.length > 0 && <span style={{ fontSize: 11, fontWeight: 600, padding: '3px 9px', borderRadius: 20, background: C.brassL, color: C.brass, border: `1px solid ${C.brassB}` }}>{newLeads.length} new</span>}
                    </div>
                    <div className="leads-scroll">
                      {loading ? [1, 2, 3, 4].map(i => (
                        <div key={i} style={{ padding: '18px 24px', borderBottom: `1px solid ${C.lineSoft}` }}>
                          <div style={{ background: C.panel, borderRadius: 4, height: 10, width: '40%', marginBottom: 8 }} />
                          <div style={{ background: C.panel, borderRadius: 4, height: 14, width: '75%', marginBottom: 8 }} />
                          <div style={{ background: C.panel, borderRadius: 4, height: 10, width: '50%' }} />
                        </div>
                      )) : leads.length === 0 ? (
                        <div style={{ padding: '56px 24px', textAlign: 'center' }}>
                          <p style={{ fontFamily: DISPLAY, fontSize: 18, fontWeight: 500, color: C.ink, margin: '0 0 4px' }}>No leads yet</p>
                          <p style={{ fontSize: 13, color: C.ink3, margin: 0 }}>Jobs matching your area will appear here.</p>
                        </div>
                      ) : leads.map(l => (
                        <LeadRow key={l.id} lead={l} onQuote={setQuoting} onView={setViewing} onMarkComplete={setMarkCompleteLead}
                          selected={selectedId === l.id} onClick={() => setSelectedId(p => p === l.id ? null : l.id)} />
                      ))}
                    </div>
                  </div>
                  <div className="leads-map-wrap"><LeadMap leads={leads} selectedId={selectedId} onSelect={id => setSelectedId(p => p === id ? null : id)} /></div>
                </div>
              </motion.div>
            )}

            {/* ─── ACTIVE ───────────────────────────────────────────────── */}
            {tab === 'active' && isApproved && (
              <motion.div key="active" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }}>
                <div style={panelStyle}>
                  <div style={{ padding: '14px 24px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', gap: 10 }}>
                    <p style={sectionTitle}>Active jobs · {activeLeads.length}</p>
                    {activeLeads.some(l => l.job_status === 'completed') && (
                      <span style={{ fontSize: 11, fontWeight: 600, color: C.amber, background: C.amberL, border: `1px solid ${C.amber}30`, padding: '2px 8px', borderRadius: 20 }}>
                        {activeLeads.filter(l => l.job_status === 'completed').length} awaiting confirmation
                      </span>
                    )}
                  </div>
                  {loading ? <div style={{ padding: 48, textAlign: 'center' }}><Loader2 size={20} color={C.ink3} className="animate-spin" /></div>
                    : activeLeads.length === 0 ? (
                      <div style={{ padding: '56px 28px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 56, height: 56, borderRadius: 14, background: C.paper, border: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.ink3 }}><Briefcase size={22} /></div>
                        <div>
                          <p style={{ fontFamily: DISPLAY, fontSize: 20, fontWeight: 500, color: C.ink, margin: '0 0 4px', letterSpacing: '-0.015em' }}>No active jobs</p>
                          <p style={{ fontSize: 13.5, color: C.ink3, margin: 0 }}>Quote on leads to land your next job.</p>
                        </div>
                        <button onClick={() => setTab('leads')} style={{ marginTop: 6, padding: '10px 18px', borderRadius: 10, background: C.ink, color: C.card, border: 'none', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>View leads</button>
                      </div>
                    ) : activeLeads.map(l => <LeadRow key={l.id} lead={l} onQuote={setQuoting} onView={setViewing} onMarkComplete={setMarkCompleteLead} />)}
                </div>
              </motion.div>
            )}

            {/* ─── LICENCES & DOCS ──────────────────────────────────────── */}
            {/* Redirects to the dedicated licences page on activation */}
            {tab === 'licences' && (
              <motion.div key="licences" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }}
                style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '80px 24px', gap: 14 }}>
                <Loader2 size={22} color={C.brass} className="animate-spin" />
                <p style={{ fontSize: 14, color: C.ink3, margin: 0 }}>Redirecting to Licences &amp; Docs…</p>
                {/* Trigger redirect imperatively — avoids hook-in-callback issues */}
                {typeof window !== 'undefined' && (() => { setTimeout(() => router.push('/tradie/licences'), 0); return null; })()}
              </motion.div>
            )}
            {/* ─── PREFERENCES ──────────────────────────────────────────── */}
            {tab === 'preferences' && (
              <motion.div key="prefs" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

                {/* ── 1. Service areas & states — TOP, always visible ── */}
                <div style={panelStyle}>
                  <div style={{ padding: '14px 24px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', gap: 10 }}>
                    <MapPin size={14} color={C.brass} />
                    <p style={sectionTitle}>Service areas & states</p>
                    <span style={{ fontSize: 11, color: C.ink3 }}>— determines which state licences you need</span>
                  </div>
                  <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {AU_STATES.map(s => {
                        const active = prefStateFilter === s;
                        return (
                          <button key={s} onClick={() => { setPrefStateFilter(prev => prev === s ? '' : s); setSuburbQuery(''); setSuburbResults([]); }}
                            style={{ padding: '6px 16px', borderRadius: 8, border: `1.5px solid ${active ? C.brass : C.line}`, background: active ? C.brassL : C.paper, color: active ? C.brass : C.ink3, fontSize: 12.5, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s' }}>
                            {s}
                          </button>
                        );
                      })}
                    </div>
                    {prefStateFilter && (
                      <div style={{ position: 'relative' }}>
                        <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                        <input value={suburbQuery}
                          onChange={e => {
                            const val = e.target.value; setSuburbQuery(val);
                            if (suburbTimerRef.current) clearTimeout(suburbTimerRef.current);
                            if (val.length < 2) { setSuburbResults([]); return; }
                            setSuburbSearching(true);
                            suburbTimerRef.current = setTimeout(async () => {
                              try { const res = await fetch(`/api/suburbs?q=${encodeURIComponent(val)}&state=${prefStateFilter}&limit=12`); setSuburbResults(await res.json()); }
                              catch { setSuburbResults([]); } finally { setSuburbSearching(false); }
                            }, 300);
                          }}
                          placeholder={`Search suburbs in ${prefStateFilter}…`}
                          style={{ ...inputStyle, paddingLeft: 36 }}
                          onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; }}
                          onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; }} />
                        {suburbSearching && <Loader2 size={13} className="animate-spin" style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', color: C.ink3 }} />}
                      </div>
                    )}
                    {suburbResults.length > 0 && (
                      <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 10, overflow: 'hidden', maxHeight: 200, overflowY: 'auto', boxShadow: SHADOW_MD }}>
                        {suburbResults.map((r: any) => {
                          const added = serviceAreas.some(sa => sa.suburb === r.suburb && sa.postcode === r.postcode);
                          return (
                            <button key={r.id}
                              onClick={() => {
                                if (added) setServiceAreas(prev => prev.filter(sa => !(sa.suburb === r.suburb && sa.postcode === r.postcode)));
                                else {
                                  if (serviceAreas.length >= 20) { toast.error('Maximum 20 service areas.'); return; }
                                  setServiceAreas(prev => [...prev, { suburb: r.suburb, postcode: r.postcode, state_code: r.state_code }]);
                                }
                              }}
                              style={{ width: '100%', padding: '10px 16px', border: 'none', borderBottom: `1px solid ${C.lineSoft}`, background: added ? C.brassL : 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between', textAlign: 'left' }}>
                              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                                <span style={{ fontSize: 13.5, fontWeight: 600, color: C.ink }}>{r.suburb}</span>
                                <span style={{ fontSize: 12, color: C.ink3 }}>{r.postcode}</span>
                              </div>
                              {added ? <CheckCircle size={14} color={C.brass} /> : <Plus size={14} color={C.ink3} />}
                            </button>
                          );
                        })}
                      </div>
                    )}
                    {serviceAreas.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                        {serviceAreas.map(sa => (
                          <div key={`${sa.suburb}-${sa.postcode}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 8px 5px 12px', borderRadius: 20, background: C.brassL, border: `1px solid ${C.brassB}`, fontSize: 12, fontWeight: 600, color: C.ink2 }}>
                            <MapPin size={10} color={C.brass} style={{ flexShrink: 0 }} />
                            <span>{sa.suburb}</span><span style={{ color: C.ink4, fontSize: 11 }}>{sa.state_code}</span>
                            <button onClick={() => setServiceAreas(prev => prev.filter(s => !(s.suburb === sa.suburb && s.postcode === sa.postcode)))} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0 0 0 2px', display: 'flex', color: C.ink3 }}><X size={12} /></button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* ── 2. Services picker — two column ── */}
                <div style={panelStyle}>
                  <div style={{ padding: '14px 24px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <p style={sectionTitle}>Services you offer</p>
                    <span style={{ fontSize: 11, fontWeight: 600, color: C.ink3 }}>{selectedCatIds.length} selected · changes sync to Licences & Docs automatically</span>
                  </div>

                  <div className="services-picker-grid">
                    {/* ── LEFT: Requirements / Preview / Confirmation panel ── */}
                    <div style={{ padding: '20px 22px', borderRight: `1px solid ${C.lineSoft}`, display: 'flex', flexDirection: 'column', gap: 14, minHeight: 460 }}>

                      {/* CONFIRMATION: strict service waiting to be added */}
                      {confirmAddCat && (() => {
                        const rule = getServiceRule(confirmAddCat);
                        return (
                          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
                            <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20, background: C.amberL, color: C.amber, border: `1px solid ${C.amber}40`, alignSelf: 'flex-start', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                              {getLevelLabel(rule.level)}
                            </span>
                            <div>
                              <p style={{ fontFamily: DISPLAY, fontSize: 18, fontWeight: 500, color: C.ink, margin: '0 0 6px', letterSpacing: '-0.01em' }}>{confirmAddCat.name}</p>
                              <p style={{ fontSize: 13, color: C.ink3, margin: 0, lineHeight: 1.6 }}>{rule.reason}</p>
                            </div>
                            <div style={{ background: C.paper, border: `1px solid ${C.line}`, borderRadius: 10, padding: '12px 16px' }}>
                              <p style={{ fontSize: 10.5, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 10px' }}>Documents required</p>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                                {rule.documents.map(d => (
                                  <div key={d} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: C.amber, flexShrink: 0 }} />
                                    <span style={{ fontSize: 13, color: C.ink }}>{getDocumentLabel(d)}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                            <div style={{ padding: '10px 14px', background: C.sageL, borderRadius: 10, border: `1px solid ${C.sage}30`, display: 'flex', gap: 8 }}>
                              <Info size={13} color={C.sage} style={{ flexShrink: 0, marginTop: 1 }} />
                              <p style={{ fontSize: 12, color: C.ink2, margin: 0, lineHeight: 1.55 }}>Your existing verified services and leads <strong>will not be affected</strong> by adding this service.</p>
                            </div>
                            <div style={{ marginTop: 'auto' }}>
                              <p style={{ fontSize: 13, fontWeight: 600, color: C.ink, margin: '0 0 10px' }}>Add <em style={{ fontStyle: 'italic' }}>{confirmAddCat.name}</em> to your services?</p>
                              <div style={{ display: 'flex', gap: 8 }}>
                                <button onClick={() => setConfirmAddCat(null)}
                                  style={{ flex: 1, padding: '10px', borderRadius: 8, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>Cancel</button>
                                <button onClick={() => { setSelectedCatIds(prev => [...prev, confirmAddCat.id]); setPreviewCatId(confirmAddCat.id); setConfirmAddCat(null); }}
                                  style={{ flex: 1, padding: '10px', borderRadius: 8, border: 'none', background: C.ink, color: C.card, fontWeight: 600, fontSize: 13, cursor: 'pointer' }}>
                                  Yes, add service
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })()}

                      {/* PREVIEW: hovering a service from the right list */}
                      {!confirmAddCat && previewCatId && (() => {
                        const cat = allCategories.find(c => c.id === previewCatId);
                        if (!cat) return null;
                        const rule = getServiceRule(cat);
                        const isSelected = selectedCatIds.includes(previewCatId);
                        return (
                          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 14 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20, background: rule.level === 'strict' ? C.amberL : rule.level === 'standard' ? C.brassL : C.panel, color: rule.level === 'strict' ? C.amber : rule.level === 'standard' ? C.brass : C.ink3, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{getLevelLabel(rule.level)}</span>
                              {isSelected && <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20, background: C.sageL, color: C.sage }}>✓ Selected</span>}
                            </div>
                            <div>
                              <p style={{ fontFamily: DISPLAY, fontSize: 18, fontWeight: 500, color: C.ink, margin: '0 0 6px', letterSpacing: '-0.01em' }}>{cat.name}</p>
                              <p style={{ fontSize: 13, color: C.ink3, margin: 0, lineHeight: 1.6 }}>{rule.reason}</p>
                            </div>
                            <div style={{ background: C.paper, border: `1px solid ${C.line}`, borderRadius: 10, padding: '12px 16px' }}>
                              <p style={{ fontSize: 10.5, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 10px' }}>Documents required</p>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                                {rule.documents.map(d => (
                                  <div key={d} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: C.brass, flexShrink: 0 }} />
                                    <span style={{ fontSize: 13, color: C.ink2 }}>{getDocumentLabel(d)}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                            <p style={{ fontSize: 12, color: C.ink4, margin: 0 }}>Click to {isSelected ? 'remove from' : 'add to'} your services</p>
                          </div>
                        );
                      })()}

                      {/* DEFAULT: no hover, no confirm — show selected services list */}
                      {!confirmAddCat && !previewCatId && (
                        selectedCatIds.length === 0 ? (
                          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, textAlign: 'center', color: C.ink4, padding: '20px 0' }}>
                            <Search size={22} />
                            <p style={{ fontSize: 13, margin: 0, lineHeight: 1.65, maxWidth: 200 }}>Hover a service on the right to see what documents it needs</p>
                          </div>
                        ) : (
                          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10 }}>
                            <p style={{ fontSize: 10.5, fontWeight: 700, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.12em', margin: 0 }}>Selected services ({selectedCatIds.length})</p>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, overflowY: 'auto', maxHeight: 360 }}>
                              {selectedCategories.map(cat => {
                                const rule = getServiceRule(cat);
                                const hasVerified = onboardingStatus?.certifications.some(c => c.category_id === cat.id && c.status === 'verified') ?? false;
                                return (
                                  <div key={cat.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 12px', borderRadius: 8, background: C.paper, border: `1px solid ${C.line}` }}>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <p style={{ fontSize: 12.5, fontWeight: 600, color: C.ink, margin: '0 0 2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cat.name}</p>
                                      <p style={{ fontSize: 11, color: rule.level === 'strict' ? C.amber : C.ink3, margin: 0, fontWeight: 600 }}>{getLevelLabel(rule.level)}</p>
                                    </div>
                                    {hasVerified && <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 6, background: C.sageL, color: C.sage, flexShrink: 0 }}>Verified</span>}
                                    <button
                                      onClick={() => {
                                        if (hasVerified) toast('Removing won\'t delete your verified licence data', { icon: '⚠️' });
                                        setSelectedCatIds(prev => prev.filter(id => id !== cat.id));
                                      }}
                                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: C.ink4, padding: 2, display: 'flex', flexShrink: 0 }}
                                      onMouseEnter={e => e.currentTarget.style.color = C.rose}
                                      onMouseLeave={e => e.currentTarget.style.color = C.ink4}>
                                      <X size={13} />
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )
                      )}
                    </div>

                    {/* ── RIGHT: Searchable grouped services list ── */}
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      {/* Search + filter pills */}
                      <div style={{ padding: '14px 16px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', flexDirection: 'column', gap: 9 }}>
                        <div style={{ position: 'relative' }}>
                          <Search size={13} style={{ position: 'absolute', left: 11, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                          <input value={catSearchQuery} onChange={e => setCatSearchQuery(e.target.value)} placeholder="Search services…"
                            style={{ ...inputStyle, paddingLeft: 32, padding: '9px 10px 9px 32px', fontSize: 13 }}
                            onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; }}
                            onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; }} />
                          {catSearchQuery && <button onClick={() => setCatSearchQuery('')} style={{ position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: C.ink3, padding: 2, display: 'flex' }}><X size={12} /></button>}
                        </div>
                        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                          {[['all', 'All'], ['strict', 'Strict'], ['standard', 'Standard'], ['basic', 'Basic']].map(([value, label]) => {
                            const active = serviceLevelFilter === value;
                            return (
                              <button key={value} onClick={() => setServiceLevelFilter(value as any)}
                                style={{ padding: '5px 10px', borderRadius: 7, border: `1px solid ${active ? C.brass : C.line}`, background: active ? C.brassL : C.card, color: active ? C.brass : C.ink3, fontSize: 11, fontWeight: 700, cursor: 'pointer' }}>
                                {label}
                              </button>
                            );
                          })}
                        </div>
                      </div>

                      {/* Grouped services scroll list */}
                      {!catLoaded ? (
                        <div style={{ padding: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, color: C.ink3 }}>
                          <Loader2 size={16} className="animate-spin" />
                          <span style={{ fontSize: 13 }}>Loading services…</span>
                        </div>
                      ) : (
                        <div className="services-scroll" style={{ overflowY: 'auto', maxHeight: 380 }}>
                          {Object.keys(groupedAllCategories).length === 0 ? (
                            <div style={{ padding: '32px 16px', textAlign: 'center', color: C.ink4, fontSize: 13 }}>No services match your search.</div>
                          ) : Object.entries(groupedAllCategories).map(([group, items]) => (
                            <div key={group}>
                              <div style={{ padding: '7px 16px', background: C.lineSoft, borderBottom: `1px solid ${C.line}` }}>
                                <p style={{ fontSize: 9.5, fontWeight: 800, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.16em', margin: 0 }}>{group}</p>
                              </div>
                              {items.map(cat => {
                                const selected = selectedCatIds.includes(cat.id);
                                const rule = getServiceRule(cat);
                                const isPreviewing = previewCatId === cat.id;
                                const isConfirming = confirmAddCat?.id === cat.id;
                                return (
                                  <button key={cat.id}
                                    onMouseEnter={() => { if (!confirmAddCat) setPreviewCatId(cat.id); }}
                                    onMouseLeave={() => { if (!confirmAddCat) setPreviewCatId(null); }}
                                    onClick={() => {
                                      if (selected) {
                                        const hasVerified = onboardingStatus?.certifications.some(c => c.category_id === cat.id && c.status === 'verified') ?? false;
                                        if (hasVerified) toast('Removing won\'t delete your verified licence data', { icon: '⚠️' });
                                        setSelectedCatIds(prev => prev.filter(id => id !== cat.id));
                                        setConfirmAddCat(null);
                                      } else if (rule.level === 'strict') {
                                        setConfirmAddCat(cat);
                                        setPreviewCatId(null);
                                      } else {
                                        setSelectedCatIds(prev => [...prev, cat.id]);
                                      }
                                    }}
                                    style={{ width: '100%', padding: '11px 16px', border: 'none', borderBottom: `1px solid ${C.lineSoft}`, background: isConfirming ? C.amberL : selected ? C.brassL : isPreviewing ? C.panel : 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10, textAlign: 'left', transition: 'background 0.1s' }}>
                                    <div style={{ flex: 1, minWidth: 0 }}>
                                      <p style={{ fontSize: 13, fontWeight: selected ? 700 : 500, color: C.ink, margin: '0 0 2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cat.name}</p>
                                      <p style={{ fontSize: 10.5, color: rule.level === 'strict' ? C.amber : C.ink3, margin: 0, fontWeight: 600 }}>{getLevelLabel(rule.level)}</p>
                                    </div>
                                    {selected
                                      ? <CheckCircle size={14} color={C.brass} style={{ flexShrink: 0 }} />
                                      : isConfirming
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
                      )}
                    </div>
                  </div>
                </div>

                {/* ── 3. Job types ── */}
                <div style={panelStyle}>
                  <div style={{ padding: '14px 24px', borderBottom: `1px solid ${C.lineSoft}` }}><p style={sectionTitle}>Job types</p></div>
                  <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {[{ key: 'accept_residential', label: 'Residential', sub: 'Houses, apartments, townhouses' }, { key: 'accept_commercial', label: 'Commercial', sub: 'Offices, retail, industrial' }].map(({ key, label, sub }) => (
                      <div key={key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderRadius: 10, background: C.paper, border: `1px solid ${C.line}`, gap: 12 }}>
                        <div><p style={{ fontSize: 14, fontWeight: 600, color: C.ink, margin: '0 0 2px' }}>{label}</p><p style={{ fontSize: 12.5, color: C.ink3, margin: 0 }}>{sub}</p></div>
                        <Toggle on={(pref as any)[key]} onChange={v => setPref(p => ({ ...p, [key]: v }))} />
                      </div>
                    ))}
                  </div>
                </div>

                {/* ── 4. Notifications ── */}
                <div style={panelStyle}>
                  <div style={{ padding: '14px 24px', borderBottom: `1px solid ${C.lineSoft}` }}><p style={sectionTitle}>Notifications</p></div>
                  <div style={{ padding: '18px 24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {[{ key: 'notifications_email', label: 'Email', sub: 'New leads and quote updates', icon: Mail }, { key: 'notifications_sms', label: 'Text messages', sub: 'Urgent job alerts', icon: Phone }].map(({ key, label, sub, icon: Icon }) => (
                      <div key={key} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderRadius: 10, background: C.paper, border: `1px solid ${C.line}`, gap: 12 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{ width: 36, height: 36, borderRadius: 9, background: C.card, border: `1px solid ${C.line}`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Icon size={14} color={C.ink3} /></div>
                          <div><p style={{ fontSize: 14, fontWeight: 600, color: C.ink, margin: '0 0 2px' }}>{label}</p><p style={{ fontSize: 12.5, color: C.ink3, margin: 0 }}>{sub}</p></div>
                        </div>
                        <Toggle on={(pref as any)[key]} onChange={v => setPref(p => ({ ...p, [key]: v }))} />
                      </div>
                    ))}
                  </div>
                </div>

                {/* ── Save ── */}
                <button onClick={savePrefs} disabled={prefSaving}
                  style={{ alignSelf: 'flex-start', padding: '11px 22px', borderRadius: 10, background: prefSaving ? C.ink3 : C.ink, color: C.card, border: 'none', fontWeight: 600, fontSize: 13, cursor: prefSaving ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
                  onMouseEnter={e => { if (!prefSaving) e.currentTarget.style.background = '#000'; }}
                  onMouseLeave={e => { if (!prefSaving) e.currentTarget.style.background = C.ink; }}>
                  {prefSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  {prefSaving ? 'Saving…' : 'Save preferences'}
                </button>
              </motion.div>
            )}

            {/* ─── PROFILE ──────────────────────────────────────────────── */}
            {tab === 'profile' && (
              <motion.div key="profile" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.25 }} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={panelStyle}>
                  <div className="profile-header" style={{ padding: '28px 28px 24px' }}>
                    <div style={{ position: 'relative', flexShrink: 0 }}>
                      <div style={{ width: 76, height: 76, borderRadius: 16, background: C.paper, border: `1px solid ${C.line}`, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {avatarUploading ? <Loader2 size={22} color={C.brass} className="animate-spin" /> : prof.avatar_url ? <img src={prof.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} /> : <User size={30} color={C.ink3} />}
                      </div>
                      <label htmlFor="avatar-upload" style={{ position: 'absolute', bottom: -4, right: -4, width: 26, height: 26, borderRadius: '50%', background: C.ink, border: `2px solid ${C.card}`, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: avatarUploading ? 'not-allowed' : 'pointer' }}>
                        <Camera size={12} color={C.card} />
                      </label>
                      <input id="avatar-upload" ref={avatarInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleAvatarChange} />
                      {prof.avatar_url && !avatarUploading && (
                        <button onClick={async () => {
                          const prev = prof.avatar_url; setProf(p => ({ ...p, avatar_url: '' }));
                          try { await api.patch('/tradies/profile/me', { avatar_url: '' }); toast.success('Photo removed.'); }
                          catch { setProf(p => ({ ...p, avatar_url: prev })); toast.error('Could not remove photo.'); }
                        }} style={{ position: 'absolute', top: -6, right: -6, width: 20, height: 20, borderRadius: '50%', background: C.rose, border: `2px solid ${C.card}`, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', padding: 0 }}>
                          <X size={10} color={C.card} />
                        </button>
                      )}
                    </div>
                    <div style={{ flex: 1, minWidth: 180 }}>
                      <h2 style={{ fontFamily: DISPLAY, fontSize: 22, fontWeight: 500, color: C.ink, margin: '0 0 4px', letterSpacing: '-0.02em' }}>{prof.business_name || user?.name || 'Your business'}</h2>
                      <p style={{ fontSize: 13, color: C.ink3, margin: 0 }}>{user?.email}</p>
                    </div>
                  </div>
                </div>
                <div style={panelStyle}>
                  <div style={{ padding: '14px 24px', borderBottom: `1px solid ${C.lineSoft}` }}><p style={sectionTitle}>Business details</p></div>
                  <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                    <div className="profile-biz-grid">
                      <div>
                        <label style={labelStyle}>Business name <span style={{ color: C.rose }}>*</span></label>
                        <input value={prof.business_name} onChange={e => setProf(p => ({ ...p, business_name: e.target.value }))} placeholder="e.g. Smith's Plumbing" style={inputStyle}
                          onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; }}
                          onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; }} />
                      </div>
                      <div>
                        <label style={labelStyle}>ABN</label>
                        <input value={prof.abn} onChange={e => setProf(p => ({ ...p, abn: formatAbn(e.target.value) }))} placeholder="12 345 678 901" maxLength={14}
                          style={{ ...inputStyle, fontVariantNumeric: 'tabular-nums' }}
                          onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; }}
                          onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; }} />
                      </div>
                    </div>
                    <div>
                      <label style={labelStyle}>Phone</label>
                      <input value={prof.phone} onChange={e => setProf(p => ({ ...p, phone: formatPhone(e.target.value) }))} placeholder="04XX XXX XXX" maxLength={12}
                        style={{ ...inputStyle, maxWidth: 280, fontVariantNumeric: 'tabular-nums' }}
                        onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; }}
                        onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; }} />
                    </div>
                    <div>
                      <label style={labelStyle}>About your work</label>
                      <textarea rows={4} value={prof.bio} onChange={e => setProf(p => ({ ...p, bio: e.target.value.slice(0, 500) }))} placeholder="Describe your experience…"
                        style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.65 }}
                        onFocus={e => { e.currentTarget.style.borderColor = C.brass; e.currentTarget.style.background = C.card; }}
                        onBlur={e => { e.currentTarget.style.borderColor = C.line; e.currentTarget.style.background = C.paper; }} />
                      <p style={{ fontSize: 11, color: C.ink3, marginTop: 5, fontVariantNumeric: 'tabular-nums' }}>{prof.bio.length}/500</p>
                    </div>
                  </div>
                </div>
                <button onClick={saveProfile} disabled={profSaving}
                  style={{ alignSelf: 'flex-start', padding: '11px 24px', borderRadius: 10, background: profSaving ? C.ink3 : C.ink, color: C.card, border: 'none', fontWeight: 600, fontSize: 13, cursor: profSaving ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}
                  onMouseEnter={e => { if (!profSaving) e.currentTarget.style.background = '#000'; }}
                  onMouseLeave={e => { if (!profSaving) e.currentTarget.style.background = C.ink; }}>
                  {profSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  {profSaving ? 'Saving…' : 'Save profile'}
                </button>
              </motion.div>
            )}

          </AnimatePresence>
        </div>
        </div>{/* end app-main */}

        <style>{`
        * { box-sizing: border-box; }
        body { margin: 0; }
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;1,9..144,400;1,9..144,500&family=Inter:wght@400;500;600;700&display=swap');
        .leaflet-pane, .leaflet-control, .leaflet-top, .leaflet-bottom { z-index: 1 !important; }
        .app-main { min-height: 100vh; display: flex; flex-direction: column; background: ${C.paper}; }
        .app-topbar { position: sticky; top: 0; z-index: 50; display: flex; align-items: center; gap: 16px; padding: 16px 32px; background: ${C.paper}f7; backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-bottom: 1px solid ${C.line}; box-shadow: 0 1px 8px rgba(0,0,0,0.05); }
        .app-content { padding: 28px 32px 48px; max-width: 1280px; width: 100%; }
        .stat-grid { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; }
        .stat-card { transition: transform 0.15s, box-shadow 0.15s; }
        .stat-card:hover { transform: translateY(-1px); box-shadow: ${SHADOW_SM}; }
        .lead-row-inner { display: flex; align-items: flex-start; gap: 14px; }
        .lead-row-status { padding-top: 6px; flex-shrink: 0; }
        .lead-row-content { flex: 1; min-width: 0; }
        .lead-row-title-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
        .lead-row-desc { overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
        .lead-row-meta { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
        .lead-row-budget { text-align: right; flex-shrink: 0; min-width: 90px; }
        .lead-row-action { flex-shrink: 0; }
        .leads-layout { display: grid; grid-template-columns: 420px 1fr; gap: 16px; height: calc(100vh - 140px); min-height: 520px; }
        .leads-list-wrap { display: flex; flex-direction: column; height: 100%; }
        .leads-scroll { flex: 1; overflow-y: auto; }
        .leads-map-wrap { height: 100%; min-height: 520px; }
        .profile-header { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; }
        .profile-biz-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        .service-card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
        .services-picker-grid { display: grid; grid-template-columns: 1fr 1fr; }
        .services-scroll::-webkit-scrollbar { width: 6px; }
        .services-scroll::-webkit-scrollbar-track { background: transparent; }
        .services-scroll::-webkit-scrollbar-thumb { background: ${C.line}; border-radius: 3px; }
        .services-scroll::-webkit-scrollbar-thumb:hover { background: ${C.ink4}; }
        @media (max-width: 1024px) {
          .stat-grid { grid-template-columns: repeat(2,1fr); }
          .leads-layout { grid-template-columns: 1fr; height: auto; }
          .leads-list-wrap { min-height: 420px; max-height: 540px; }
          .leads-map-wrap { height: 360px; min-height: 0; }
          .app-content { padding: 24px 24px 48px; }
          .app-topbar { padding: 14px 24px; }
          .service-card-grid { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); }
        }
        @media (max-width: 640px) {
          .app-content { padding: 20px 16px 40px; }
          .app-topbar { padding: 12px 16px; gap: 10px; }
          .stat-grid { gap: 10px; }
          .stat-card { padding: 14px 16px !important; }
          .lead-row-inner { flex-wrap: wrap; padding: 14px 18px !important; }
          .lead-row-budget { text-align: left; flex: 1; min-width: 0; }
          .lead-row-action { margin-left: auto; }
          .profile-header { flex-direction: column; align-items: flex-start; gap: 16px; }
          .profile-biz-grid { grid-template-columns: 1fr; gap: 12px; }
        }
      `}</style>
        </>
        );
      }}
    </TradieStudioLayout>
  );
}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  