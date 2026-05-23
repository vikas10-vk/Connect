"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  Shield, Award, HardHat, CheckCircle2, Clock, AlertCircle,
  XCircle, ChevronRight, FileText, Edit3, X, Send, Loader2,
  AlertTriangle, Info, Lock,
} from "lucide-react";
import TradieStudioLayout from "@/src/components/tradie/TradieStudioLayout";
import api from "@/src/lib/api";

// ─── Design tokens (matches dashboard/profile exactly) ───────────────────────
const C = {
  paper: '#FFF8E7', panel: '#F5EDD0', card: '#FFFFFF',
  line: '#E8D9B0', lineSoft: '#F5EDD0',
  ink: '#071D36', ink2: '#173452', ink3: '#56677A', ink4: '#8A785A',
  brass: '#D4AA3A', brassL: '#F7EBC5', brassB: '#E8C766',
  sage: '#5B7560', sageL: '#EDF3EE',
  amber: '#9A6B1E', amberL: '#F7EED8',
  rose: '#A8423A', roseL: '#F7E6E4',
};
const SHADOW_SM = '0 1px 3px rgba(26,26,26,0.05), 0 1px 2px rgba(26,26,26,0.03)';
const SHADOW_MD = '0 4px 14px rgba(26,26,26,0.06), 0 1px 3px rgba(26,26,26,0.04)';
const SHADOW_LG = '0 20px 60px rgba(26,26,26,0.14), 0 4px 12px rgba(26,26,26,0.06)';
const DISPLAY = "'Fraunces', 'Playfair Display', Georgia, serif";
const UI = "'Inter', 'DM Sans', -apple-system, system-ui, sans-serif";

// ─── Status config ────────────────────────────────────────────────────────────
const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  pending:   { label: 'Pending Review',  color: C.amber,  bg: C.amberL, icon: <Clock size={13} /> },
  in_review: { label: 'In Review',       color: C.brass,  bg: C.brassL, icon: <Clock size={13} /> },
  verified:  { label: 'Verified',        color: C.sage,   bg: C.sageL,  icon: <CheckCircle2 size={13} /> },
  rejected:  { label: 'Rejected',        color: C.rose,   bg: C.roseL,  icon: <XCircle size={13} /> },
  expired:   { label: 'Expired',         color: C.ink3,   bg: C.panel,  icon: <AlertCircle size={13} /> },
};

interface Certification {
  id: string;
  category_name: string;
  licence_number: string;
  issuing_state: string;
  issuing_body: string | null;
  holder_name: string;
  issued_at: string | null;
  expires_at: string | null;
  status: string;
  rejection_reason: string | null;
  rejection_note: string | null;
  edit_request_note: string | null;
  created_at: string;
}

interface InsurancePolicy {
  id: string;
  insurance_type: string;
  insurer_name: string;
  policy_number: string;
  holder_name: string;
  coverage_amount_cents: number;
  issued_at: string | null;
  expires_at: string;
  status: string;
  rejection_reason: string | null;
  rejection_note: string | null;
  edit_request_note: string | null;
  created_at: string;
}

// ─── Request Edit Modal ───────────────────────────────────────────────────────
function RequestEditModal({
  docType, docRef, docId, onClose, onSuccess,
}: {
  docType: 'certification' | 'insurance';
  docRef: string;
  docId: string;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    if (reason.trim().length < 10) { setErr('Please explain your reason in at least 10 characters.'); return; }
    setSaving(true); setErr('');
    try {
      const endpoint = docType === 'certification'
        ? `/tradies/certifications/${docId}/request-edit`
        : `/tradies/insurance/${docId}/request-edit`;
      await api.post(endpoint, { reason: reason.trim() });
      onSuccess();
      onClose();
    } catch (e: any) {
      const d = e?.response?.data?.detail;
      setErr(typeof d === 'string' ? d : 'Could not send request. Please try again.');
    } finally { setSaving(false); }
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(26,26,26,0.48)', backdropFilter: 'blur(6px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <motion.div initial={{ opacity: 0, y: 16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 8, scale: 0.98 }} transition={{ type: 'spring', damping: 28, stiffness: 340 }}
        onClick={e => e.stopPropagation()}
        style={{ width: '100%', maxWidth: 480, background: C.card, borderRadius: 16, overflow: 'hidden', boxShadow: SHADOW_LG, border: `1px solid ${C.line}` }}>

        {/* Header */}
        <div style={{ padding: '22px 24px 18px', borderBottom: `1px solid ${C.lineSoft}`, position: 'relative' }}>
          <button onClick={onClose} style={{ position: 'absolute', top: 14, right: 14, width: 28, height: 28, borderRadius: 7, border: `1px solid ${C.line}`, background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: C.ink3 }}><X size={13} /></button>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '2px 10px', background: C.amberL, border: `1px solid ${C.amber}30`, borderRadius: 20, marginBottom: 10 }}>
            <Edit3 size={11} color={C.amber} />
            <span style={{ fontSize: 11, fontWeight: 600, color: C.amber }}>Edit Request</span>
          </div>
          <h2 style={{ fontFamily: DISPLAY, fontSize: 20, fontWeight: 500, color: C.ink, margin: '0 0 4px', letterSpacing: '-0.01em' }}>Request to edit document</h2>
          <p style={{ fontSize: 13, color: C.ink3, margin: 0 }}>
            <strong style={{ color: C.ink2 }}>{docRef}</strong>  -  our admin team will review your request.
          </p>
        </div>

        {/* Form */}
        <div style={{ padding: '20px 24px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Info banner */}
          <div style={{ display: 'flex', gap: 10, padding: '10px 14px', background: C.amberL, border: `1px solid ${C.amber}30`, borderRadius: 10 }}>
            <Info size={14} color={C.amber} style={{ flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 12, color: C.ink2, margin: 0, lineHeight: 1.55 }}>
              Documents are locked after submission to maintain verification integrity. Once admin approves your request, you'll be able to resubmit.
            </p>
          </div>

          {err && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: C.roseL, border: `1px solid ${C.rose}30`, color: C.rose, padding: '10px 14px', borderRadius: 10, fontSize: 13 }}>
              <AlertCircle size={14} />{err}
            </div>
          )}

          <div>
            <label style={{ fontSize: 11, fontWeight: 600, color: C.ink2, textTransform: 'uppercase', letterSpacing: '0.08em', display: 'block', marginBottom: 7 }}>
              Reason for editing <span style={{ color: C.rose }}>*</span>
            </label>
            <textarea
              autoFocus
              value={reason}
              onChange={e => setReason(e.target.value)}
              placeholder="e.g. My licence was renewed with a new number, the previous one has expired..."
              rows={4}
              style={{ width: '100%', padding: '11px 14px', borderRadius: 10, border: `1px solid ${C.line}`, background: C.paper, fontSize: 13.5, color: C.ink, outline: 'none', boxSizing: 'border-box', fontFamily: UI, resize: 'vertical', lineHeight: 1.55 }}
              onFocus={e => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; }}
              onBlur={e => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; }}
            />
            <p style={{ fontSize: 11, color: C.ink4, margin: '5px 0 0' }}>{reason.length}/1000 characters</p>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={onClose} style={{ flex: 1, padding: '11px', borderRadius: 10, border: `1px solid ${C.line}`, background: C.paper, color: C.ink2, fontWeight: 600, fontSize: 13, cursor: 'pointer', fontFamily: UI }}>Cancel</button>
            <button onClick={submit} disabled={saving}
              style={{ flex: 2, padding: '11px', borderRadius: 10, border: 'none', background: saving ? C.ink3 : C.ink, color: C.card, fontWeight: 600, fontSize: 13, cursor: saving ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, fontFamily: UI }}>
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Send size={13} />}
              {saving ? 'Sending...' : 'Send Request'}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
}

// ─── Status Badge ─────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.pending;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', background: cfg.bg, color: cfg.color, borderRadius: 20, fontSize: 11.5, fontWeight: 600, letterSpacing: '0.01em' }}>
      {cfg.icon}{cfg.label}
    </span>
  );
}

// ─── Certification Card ───────────────────────────────────────────────────────
function CertCard({ cert, onRequestEdit }: { cert: Certification; onRequestEdit: () => void }) {
  const canEdit = cert.status !== 'pending' && cert.status !== 'in_review';
  const isVerified = cert.status === 'verified';
  const hasEditRequest = !!cert.edit_request_note;

  return (
    <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden', boxShadow: SHADOW_SM }}>
      {/* Card header */}
      <div style={{ padding: '16px 20px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: isVerified ? C.sageL : C.panel, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Award size={18} color={isVerified ? C.sage : C.ink3} />
          </div>
          <div>
            <div style={{ fontSize: 14.5, fontWeight: 600, color: C.ink, lineHeight: 1.3 }}>{cert.category_name}</div>
            <div style={{ fontSize: 12, color: C.ink3 }}>{cert.issuing_state}{cert.issuing_body ? `  |  ${cert.issuing_body}` : ''}</div>
          </div>
        </div>
        <StatusBadge status={cert.status} />
      </div>

      {/* Card body */}
      <div style={{ padding: '16px 20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Licence Number</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.ink, fontVariantNumeric: 'tabular-nums', display: 'flex', alignItems: 'center', gap: 6 }}>
            {cert.licence_number}
            {isVerified && <CheckCircle2 size={14} color={C.sage} />}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Holder Name</div>
          <div style={{ fontSize: 14, color: C.ink }}>{cert.holder_name}</div>
        </div>
        {cert.issued_at && (
          <div>
            <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Issued</div>
            <div style={{ fontSize: 13.5, color: C.ink2 }}>{new Date(cert.issued_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}</div>
          </div>
        )}
        {cert.expires_at && (
          <div>
            <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Expires</div>
            <div style={{ fontSize: 13.5, color: new Date(cert.expires_at) < new Date() ? C.rose : C.ink2 }}>
              {new Date(cert.expires_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}
            </div>
          </div>
        )}
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Submitted</div>
          <div style={{ fontSize: 13.5, color: C.ink3 }}>{new Date(cert.created_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}</div>
        </div>
      </div>

      {/* Rejection info */}
      {cert.status === 'rejected' && cert.rejection_note && (
        <div style={{ margin: '0 20px 16px', padding: '10px 14px', background: C.roseL, border: `1px solid ${C.rose}25`, borderRadius: 10, display: 'flex', gap: 8 }}>
          <AlertTriangle size={14} color={C.rose} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.rose, marginBottom: 2 }}>Rejection reason</div>
            <div style={{ fontSize: 12.5, color: C.ink2, lineHeight: 1.5 }}>{cert.rejection_note}</div>
          </div>
        </div>
      )}

      {/* Edit request pending */}
      {hasEditRequest && (
        <div style={{ margin: '0 20px 16px', padding: '10px 14px', background: C.amberL, border: `1px solid ${C.amber}25`, borderRadius: 10, display: 'flex', gap: 8 }}>
          <Clock size={14} color={C.amber} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.amber, marginBottom: 2 }}>Edit request pending</div>
            <div style={{ fontSize: 12.5, color: C.ink2, lineHeight: 1.5 }}>Your request is being reviewed by our team.</div>
          </div>
        </div>
      )}

      {/* Footer actions */}
      <div style={{ padding: '12px 20px', borderTop: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: C.ink4, fontSize: 12 }}>
          <Lock size={11} />
          <span>Read-only after submission</span>
        </div>
        {canEdit && !hasEditRequest && (
          <button onClick={onRequestEdit}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 14px', borderRadius: 8, border: `1px solid ${C.line}`, background: 'transparent', color: C.ink2, fontSize: 12.5, fontWeight: 500, cursor: 'pointer', fontFamily: UI, transition: 'all 0.15s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = C.panel; (e.currentTarget as HTMLButtonElement).style.borderColor = C.brass; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; (e.currentTarget as HTMLButtonElement).style.borderColor = C.line; }}>
            <Edit3 size={12} />Request Edit
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Insurance Card ───────────────────────────────────────────────────────────
function InsuranceCard({ policy, onRequestEdit }: { policy: InsurancePolicy; onRequestEdit: () => void }) {
  const canEdit = policy.status !== 'pending' && policy.status !== 'in_review';
  const isVerified = policy.status === 'verified';
  const hasEditRequest = !!policy.edit_request_note;
  const coverageAud = (policy.coverage_amount_cents / 100).toLocaleString('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 });
  const isExpired = new Date(policy.expires_at) < new Date();

  return (
    <div style={{ background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, overflow: 'hidden', boxShadow: SHADOW_SM }}>
      {/* Card header */}
      <div style={{ padding: '16px 20px', borderBottom: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: isVerified ? C.sageL : C.panel, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Shield size={18} color={isVerified ? C.sage : C.ink3} />
          </div>
          <div>
            <div style={{ fontSize: 14.5, fontWeight: 600, color: C.ink, lineHeight: 1.3 }}>
              {policy.insurance_type === 'public_liability' ? 'Public Liability Insurance' : policy.insurance_type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
            </div>
            <div style={{ fontSize: 12, color: C.ink3 }}>{policy.insurer_name}</div>
          </div>
        </div>
        <StatusBadge status={isExpired ? 'expired' : policy.status} />
      </div>

      {/* Card body */}
      <div style={{ padding: '16px 20px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Policy Number</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.ink, fontVariantNumeric: 'tabular-nums', display: 'flex', alignItems: 'center', gap: 6 }}>
            {policy.policy_number}
            {isVerified && <CheckCircle2 size={14} color={C.sage} />}
          </div>
        </div>
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Holder Name</div>
          <div style={{ fontSize: 14, color: C.ink }}>{policy.holder_name}</div>
        </div>
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Coverage</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: C.ink }}>{coverageAud}</div>
        </div>
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Expires</div>
          <div style={{ fontSize: 13.5, color: isExpired ? C.rose : C.ink2 }}>
            {new Date(policy.expires_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}
          </div>
        </div>
        {policy.issued_at && (
          <div>
            <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Start Date</div>
            <div style={{ fontSize: 13.5, color: C.ink2 }}>{new Date(policy.issued_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 600, color: C.ink3, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>Submitted</div>
          <div style={{ fontSize: 13.5, color: C.ink3 }}>{new Date(policy.created_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}</div>
        </div>
      </div>

      {/* Rejection info */}
      {policy.status === 'rejected' && policy.rejection_note && (
        <div style={{ margin: '0 20px 16px', padding: '10px 14px', background: C.roseL, border: `1px solid ${C.rose}25`, borderRadius: 10, display: 'flex', gap: 8 }}>
          <AlertTriangle size={14} color={C.rose} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.rose, marginBottom: 2 }}>Rejection reason</div>
            <div style={{ fontSize: 12.5, color: C.ink2, lineHeight: 1.5 }}>{policy.rejection_note}</div>
          </div>
        </div>
      )}

      {/* Edit request pending */}
      {hasEditRequest && (
        <div style={{ margin: '0 20px 16px', padding: '10px 14px', background: C.amberL, border: `1px solid ${C.amber}25`, borderRadius: 10, display: 'flex', gap: 8 }}>
          <Clock size={14} color={C.amber} style={{ flexShrink: 0, marginTop: 1 }} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 600, color: C.amber, marginBottom: 2 }}>Edit request pending</div>
            <div style={{ fontSize: 12.5, color: C.ink2, lineHeight: 1.5 }}>Your request is being reviewed by our team.</div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div style={{ padding: '12px 20px', borderTop: `1px solid ${C.lineSoft}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: C.ink4, fontSize: 12 }}>
          <Lock size={11} />
          <span>Read-only after submission</span>
        </div>
        {canEdit && !hasEditRequest && (
          <button onClick={onRequestEdit}
            style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '6px 14px', borderRadius: 8, border: `1px solid ${C.line}`, background: 'transparent', color: C.ink2, fontSize: 12.5, fontWeight: 500, cursor: 'pointer', fontFamily: UI, transition: 'all 0.15s' }}
            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = C.panel; (e.currentTarget as HTMLButtonElement).style.borderColor = C.brass; }}
            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; (e.currentTarget as HTMLButtonElement).style.borderColor = C.line; }}>
            <Edit3 size={12} />Request Edit
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Empty Section ────────────────────────────────────────────────────────────
function EmptySection({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div style={{ padding: '32px 20px', textAlign: 'center', background: C.card, border: `1px dashed ${C.line}`, borderRadius: 14, color: C.ink4 }}>
      <div style={{ marginBottom: 8, opacity: 0.4 }}>{icon}</div>
      <div style={{ fontSize: 13.5, fontWeight: 500, color: C.ink3 }}>No {label} submitted yet</div>
      <div style={{ fontSize: 12, color: C.ink4, marginTop: 4 }}>Documents are submitted during onboarding.</div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function LicencesPage() {
  const [certs, setCerts] = useState<Certification[]>([]);
  const [insurance, setInsurance] = useState<InsurancePolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [editModal, setEditModal] = useState<{
    type: 'certification' | 'insurance'; id: string; ref: string;
  } | null>(null);
  const [successMsg, setSuccessMsg] = useState('');

  const load = async () => {
    try {
      const [certRes, insRes] = await Promise.all([
        api.get('/tradies/certifications/me'),
        api.get('/tradies/insurance/me'),
      ]);
      setCerts(certRes.data.certifications ?? []);
      setInsurance(insRes.data.insurance_policies ?? []);
    } catch {
      // silent fail  -  layout shows the error state
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleEditSuccess = () => {
    setSuccessMsg('Edit request sent! Our team will review and notify you.');
    load(); // refresh to show pending state
    setTimeout(() => setSuccessMsg(''), 5000);
  };

  // Count verified docs for the summary bar
  const verifiedCerts = certs.filter(c => c.status === 'verified').length;
  const verifiedInsurance = insurance.filter(p => p.status === 'verified').length;
  const totalDocs = certs.length + insurance.length;
  const verifiedDocs = verifiedCerts + verifiedInsurance;

  return (
    <TradieStudioLayout>
      {(ctx) => {
        if (loading) {
          return (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', flexDirection: 'column', gap: 12 }}>
              <Loader2 size={24} color={C.ink3} className="animate-spin" />
              <span style={{ fontSize: 13, color: C.ink3, fontFamily: UI }}>Loading your documents...</span>
            </div>
          );
        }

        return (
          <>
            {/* Top bar */}
            <div style={{ position: 'sticky', top: 0, zIndex: 50, background: `${C.paper}f0`, backdropFilter: 'blur(12px)', borderBottom: `1px solid ${C.lineSoft}`, padding: '14px 28px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <h1 style={{ fontFamily: DISPLAY, fontSize: 22, fontWeight: 500, color: C.ink, margin: 0, letterSpacing: '-0.01em' }}>Licences &amp; Documents</h1>
                <p style={{ fontSize: 13, color: C.ink3, margin: '2px 0 0', fontFamily: UI }}>
                  {totalDocs === 0
                    ? 'No documents submitted yet  -  complete onboarding to add your documents.'
                    : `${verifiedDocs} of ${totalDocs} document${totalDocs !== 1 ? 's' : ''} verified`}
                </p>
              </div>
              {/* Verification summary pills */}
              {totalDocs > 0 && (
                <div style={{ display: 'flex', gap: 8 }}>
                  {verifiedCerts > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px', background: C.sageL, borderRadius: 20, border: `1px solid ${C.sage}30` }}>
                      <CheckCircle2 size={12} color={C.sage} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: C.sage }}>{verifiedCerts} licence{verifiedCerts !== 1 ? 's' : ''} verified</span>
                    </div>
                  )}
                  {verifiedInsurance > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 12px', background: C.sageL, borderRadius: 20, border: `1px solid ${C.sage}30` }}>
                      <Shield size={12} color={C.sage} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: C.sage }}>Insurance verified</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Success toast */}
            <AnimatePresence>
              {successMsg && (
                <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
                  style={{ margin: '16px 28px 0', padding: '12px 16px', background: C.sageL, border: `1px solid ${C.sage}30`, borderRadius: 10, display: 'flex', alignItems: 'center', gap: 8, fontFamily: UI }}>
                  <CheckCircle2 size={15} color={C.sage} />
                  <span style={{ fontSize: 13, color: C.sage, fontWeight: 500 }}>{successMsg}</span>
                </motion.div>
              )}
            </AnimatePresence>

            <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 28px 48px' }}>

              {/* Info banner about read-only */}
              <div style={{ padding: '12px 16px', background: C.brassL, border: `1px solid ${C.brassB}`, borderRadius: 12, display: 'flex', gap: 10, marginBottom: 28 }}>
                <Info size={15} color={C.brass} style={{ flexShrink: 0, marginTop: 1 }} />
                <p style={{ fontSize: 13, color: C.ink2, margin: 0, lineHeight: 1.55, fontFamily: UI }}>
                  <strong style={{ color: C.ink }}>Documents are locked after submission</strong> to maintain verification integrity. If you need to correct a document, use the <em>Request Edit</em> button  -  our team will review and unlock it for you.
                </p>
              </div>

              {/* ── Licences section ── */}
              <section style={{ marginBottom: 36 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                  <div style={{ width: 30, height: 30, borderRadius: 8, background: C.brassL, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Award size={16} color={C.brass} />
                  </div>
                  <div>
                    <h2 style={{ fontFamily: DISPLAY, fontSize: 17, fontWeight: 500, color: C.ink, margin: 0 }}>Trade Licences</h2>
                    <p style={{ fontSize: 12, color: C.ink3, margin: 0, fontFamily: UI }}>{certs.length} submitted</p>
                  </div>
                </div>

                {certs.length === 0 ? (
                  <EmptySection icon={<Award size={32} />} label="licences" />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {certs.map(cert => (
                      <CertCard
                        key={cert.id}
                        cert={cert}
                        onRequestEdit={() => setEditModal({ type: 'certification', id: cert.id, ref: cert.licence_number })}
                      />
                    ))}
                  </div>
                )}
              </section>

              {/* ── Insurance section ── */}
              <section style={{ marginBottom: 36 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                  <div style={{ width: 30, height: 30, borderRadius: 8, background: C.sageL, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Shield size={16} color={C.sage} />
                  </div>
                  <div>
                    <h2 style={{ fontFamily: DISPLAY, fontSize: 17, fontWeight: 500, color: C.ink, margin: 0 }}>Insurance Policies</h2>
                    <p style={{ fontSize: 12, color: C.ink3, margin: 0, fontFamily: UI }}>{insurance.length} submitted</p>
                  </div>
                </div>

                {insurance.length === 0 ? (
                  <EmptySection icon={<Shield size={32} />} label="insurance policies" />
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {insurance.map(policy => (
                      <InsuranceCard
                        key={policy.id}
                        policy={policy}
                        onRequestEdit={() => setEditModal({ type: 'insurance', id: policy.id, ref: policy.policy_number })}
                      />
                    ))}
                  </div>
                )}
              </section>

              {/* ── White Card / Safety section ── */}
              <section>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                  <div style={{ width: 30, height: 30, borderRadius: 8, background: C.panel, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <HardHat size={16} color={C.ink2} />
                  </div>
                  <div>
                    <h2 style={{ fontFamily: DISPLAY, fontSize: 17, fontWeight: 500, color: C.ink, margin: 0 }}>Safety Cards</h2>
                    <p style={{ fontSize: 12, color: C.ink3, margin: 0, fontFamily: UI }}>White Card &amp; other safety certifications</p>
                  </div>
                </div>
                {ctx.isApproved ? (
                  <div style={{ padding: '20px', background: C.card, border: `1px solid ${C.line}`, borderRadius: 14, boxShadow: SHADOW_SM, display: 'flex', alignItems: 'center', gap: 12 }}>
                    <CheckCircle2 size={20} color={C.sage} />
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: C.ink, fontFamily: UI }}>White Card on file</div>
                      <div style={{ fontSize: 12.5, color: C.ink3, fontFamily: UI }}>Verified by admin during account approval</div>
                    </div>
                  </div>
                ) : (
                  <EmptySection icon={<HardHat size={32} />} label="safety cards" />
                )}
              </section>
            </div>

            {/* Edit Request Modal */}
            <AnimatePresence>
              {editModal && (
                <RequestEditModal
                  docType={editModal.type}
                  docRef={editModal.ref}
                  docId={editModal.id}
                  onClose={() => setEditModal(null)}
                  onSuccess={handleEditSuccess}
                />
              )}
            </AnimatePresence>
          </>
        );
      }}
    </TradieStudioLayout>
  );
}
