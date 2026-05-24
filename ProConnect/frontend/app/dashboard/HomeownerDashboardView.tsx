"use client";

import React, { useEffect, useState, useMemo, useCallback, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  MapPin, Calendar, AlertCircle,
  Loader2, Plus, X, Eye,
  ThumbsUp, ThumbsDown, MessageSquare, Briefcase,
  FileText, RefreshCw, Bell, Star,
  Check, Edit3, ChevronRight, Activity,
  Phone, Ban, AlertTriangle, ShieldAlert,
  CheckCircle2, XCircle, DollarSign, Clock,
} from 'lucide-react';
import api from '@/src/lib/api';
import { useAuth } from '@/src/contexts/AuthContext';
import DraftBanner from './DraftBanner';
import ReviewSubmissionModal from '@/src/components/ReviewSubmissionModal';

// ── Types ─────────────────────────────────────────────────────────────────────
interface Job {
  id: string;
  title: string;
  description?: string;
  suburb: string;
  state: string;
  status: string;
  urgency: string;
  job_type?: string;
  service_type?: string;
  created: string;
  created_at?: string;
  match_intelligence?: string;
  category_name?: string;
  quote_count?: number;
  is_deleted?: boolean;
  deleted_at?: string;
  completed_at?: string;
  confirmed_by_user_at?: string;
  photos?: { id: string; url: string; file_key: string }[];
  has_review?: boolean;
  review_status?: 'pending' | 'approved' | 'rejected' | null;
  // Scope change fields
  pending_scope_amount_cents?: number;
  scope_change_reason?: string;
  scope_change_requested_at?: string;
  scope_change_expires_at?: string;
  // Job evidence
  photo_before_url?: string;
  photo_after_url?: string;
  completion_note?: string;
  // Redo flag  -  set when job returned to in_progress after a dispute redo_work resolution
  is_redo_job?: boolean;
  // Dispute window  -  null when no window is active
  dispute_window_hours?: number | null;
  dispute_window_expires_at?: string | null;
}

interface Quote {
  id: string;
  job_id?: string;
  job_title?: string;
  amount: number;
  message: string;
  status: string;
  tradie_name?: string;
  created_at?: string;
}

interface MatchIntel {
  matched: number;
  in_area: number;
  avg_response_hours: number;
  computed_at?: string;
}

// ── Constants ─────────────────────────────────────────────────────────────────
const CREAM = '#FFF8E7';
const CREAM2 = '#F5EDD0';
const TERRA = '#D4AA3A';
const TERRA_LIGHT = '#F6E9C9';
const TERRA_MID = '#EBCB66';
const TERRA_DARK = '#0D2544';
const INK = '#071D36';
const INK2 = '#173452';
const INK3 = '#56677A';
const INK4 = '#8A785A';
const BORDER = '#E8D9B0';
const GREEN = '#2E7D5A';
const GREEN_LIGHT = '#E8F5EE';
const AMBER = '#B85C00';
const AMBER_LIGHT = '#FFF3E0';
const PURPLE = '#5B3FA6';
const PURPLE_LIGHT = '#EEE8FF';
const ROSE = '#A33030';
const ROSE_LIGHT = '#FFEBEB';
const BLUE = '#0077AA';
const BLUE_LIGHT = '#E0F4FF';

const STATUS: Record<string, { label: string; color: string; bg: string }> = {
  open: { label: 'Open', color: TERRA, bg: TERRA_LIGHT },
  quoted: { label: 'Quoted', color: AMBER, bg: AMBER_LIGHT },
  hired: { label: 'Hired', color: PURPLE, bg: PURPLE_LIGHT },
  in_progress: { label: 'In Progress', color: BLUE, bg: BLUE_LIGHT },
  // ── NEW STATES ──────────────────────────────────────────────────────────────
  awaiting_scope_approval: { label: 'Scope Change', color: AMBER, bg: AMBER_LIGHT },
  partial_stop: { label: 'Work Stopped', color: ROSE, bg: ROSE_LIGHT },
  disputed: { label: 'Disputed', color: ROSE, bg: ROSE_LIGHT },
  // ── TERMINAL ────────────────────────────────────────────────────────────────
  completed: { label: 'Awaiting Confirmation', color: GREEN, bg: GREEN_LIGHT },
  confirmed: { label: 'Completed', color: GREEN, bg: GREEN_LIGHT },
  closed: { label: 'Closed', color: INK3, bg: CREAM2 },
  cancelled: { label: 'Cancelled', color: ROSE, bg: ROSE_LIGHT },
  deleted: { label: 'Deleted', color: INK3, bg: CREAM2 },
};

const URGENCY: Record<string, { label: string }> = {
  emergency: { label: 'Emergency' },
  asap: { label: 'ASAP' },
  today: { label: 'Today' },
  next_few_days: { label: 'This week' },
  next_few_weeks: { label: 'This month' },
  next_few_months: { label: 'Planning' },
  flexible: { label: 'Flexible' },
};

const AVATAR_GRADS = [
  `${TERRA},${TERRA_DARK}`,
  '#4F46E5,#3730A3',
  '#0EA5E9,#0284C7',
  `${GREEN},#1B5E3A`,
  `${AMBER},#7A3C00`,
];

// ── Helpers ───────────────────────────────────────────────────────────────────
const fmt = (d: string) => {
  try { return new Date(d).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }); }
  catch { return d; }
};
const fmtTime = (d: string) => {
  try { return new Date(d).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' }); }
  catch { return ''; }
};
const timeAgo = (d: string) => {
  try {
    const diff = Date.now() - new Date(d).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch { return ''; }
};
const timeUntil = (d: string) => {
  try {
    const diff = new Date(d).getTime() - Date.now();
    if (diff <= 0) return 'expired';
    const mins = Math.ceil(diff / 60000);
    if (mins < 60) return `${mins}m`;
    return `${Math.ceil(mins / 60)}h`;
  } catch { return ''; }
};
const initials = (name?: string) =>
  name ? name.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2) : 'T';
const avatarGrad = (id: string) =>
  AVATAR_GRADS[(id?.charCodeAt(0) || 0) % AVATAR_GRADS.length];
function parseMatchIntel(raw?: string): MatchIntel | null {
  if (!raw) return null;
  try { return JSON.parse(raw) as MatchIntel; }
  catch { return null; }
}
const fmtCents = (cents?: number) =>
  cents != null ? `$${(cents / 100).toLocaleString('en-AU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : ' - ';

// ── Shared styles ─────────────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: '#fff',
  borderRadius: 18,
  border: `1px solid ${BORDER}`,
};
const btn = (bg: string, color: string, extra?: React.CSSProperties): React.CSSProperties => ({
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
  padding: '9px 18px', borderRadius: 12, border: 'none', cursor: 'pointer',
  fontWeight: 700, fontSize: 13, background: bg, color,
  transition: 'all .15s', ...extra,
});

// ── Photo upload helper ───────────────────────────────────────────────────────
async function uploadPhotoToJob(file: File, jobId: string): Promise<void> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch('/api/upload-photo', { method: 'POST', body: formData });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `Upload failed (${res.status})`);
  }
  const { key, public_url } = await res.json();
  if (!key) throw new Error('Upload response missing file key');
  await api.post('/uploads/confirm', { key, url: public_url, job_id: jobId });
}

// ═══ SCOPE CHANGE BANNER ══════════════════════════════════════════════════════
// Shown when job.status === 'awaiting_scope_approval'
// Homeowner has a 10-minute window to approve or reject.
function ScopeChangeBanner({ job, onRespond }: {
  job: Job;
  onRespond: (approve: boolean) => Promise<void>;
}) {
  const [loading, setLoading] = useState<'approve' | 'reject' | null>(null);
  const [timeLeft, setTimeLeft] = useState(() =>
    job.scope_change_expires_at ? timeUntil(job.scope_change_expires_at) : ' - '
  );

  // Live countdown
  useEffect(() => {
    if (!job.scope_change_expires_at) return;
    const t = setInterval(() => {
      setTimeLeft(timeUntil(job.scope_change_expires_at!));
    }, 15000);
    return () => clearInterval(t);
  }, [job.scope_change_expires_at]);

  const handle = async (approve: boolean) => {
    setLoading(approve ? 'approve' : 'reject');
    try { await onRespond(approve); }
    finally { setLoading(null); }
  };

  return (
    <div style={{
      background: '#fff', border: `2px solid ${AMBER}50`,
      borderRadius: 20, overflow: 'hidden',
      boxShadow: `0 4px 20px rgba(184,92,0,.08)`,
    }}>
      {/* Header strip */}
      <div style={{
        background: `linear-gradient(135deg, ${AMBER_LIGHT}, #FFF8F0)`,
        borderBottom: `1px solid ${AMBER}30`,
        padding: '16px 22px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12, flexShrink: 0,
          background: AMBER_LIGHT, border: `1px solid ${AMBER}40`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <DollarSign size={20} color={AMBER} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontWeight: 800, fontSize: 15, color: INK, margin: 0 }}>
            Tradie requesting scope change
          </p>
          <p style={{ fontSize: 12, color: AMBER, margin: '2px 0 0', fontWeight: 600 }}>
            Respond within {timeLeft} - auto-rejected if no response
          </p>
        </div>
      </div>

      {/* Content */}
      <div style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* New amount */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 18px', background: AMBER_LIGHT,
          border: `1px solid ${AMBER}30`, borderRadius: 14,
        }}>
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, color: AMBER, textTransform: 'uppercase', letterSpacing: '.08em', margin: 0 }}>Proposed new total</p>
            <p style={{ fontSize: 30, fontWeight: 800, color: INK, margin: '4px 0 0', lineHeight: 1 }}>
              {fmtCents(job.pending_scope_amount_cents)}
            </p>
          </div>
          {job.scope_change_requested_at && (
            <div style={{ textAlign: 'right' }}>
              <p style={{ fontSize: 11, color: INK4, margin: 0 }}>Requested</p>
              <p style={{ fontSize: 12, fontWeight: 600, color: INK2, margin: '2px 0 0' }}>
                {timeAgo(job.scope_change_requested_at)}
              </p>
            </div>
          )}
        </div>

        {/* Reason */}
        {job.scope_change_reason && (
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, color: INK4, textTransform: 'uppercase', letterSpacing: '.08em', margin: '0 0 8px' }}>
              Tradie&apos;s reason
            </p>
            <div style={{ padding: '12px 14px', background: CREAM, borderRadius: 12, border: `1px solid ${BORDER}` }}>
              <p style={{ fontSize: 13.5, color: INK2, lineHeight: 1.7, margin: 0 }}>
                &ldquo;{job.scope_change_reason}&rdquo;
              </p>
            </div>
          </div>
        )}

        {/* Important notice */}
        <div style={{
          padding: '10px 14px', background: '#FFF8F0',
          border: `1px solid ${AMBER}25`, borderRadius: 10,
          display: 'flex', gap: 8,
        }}>
          <AlertTriangle size={14} color={AMBER} style={{ flexShrink: 0, marginTop: 1 }} />
          <p style={{ fontSize: 12, color: INK2, margin: 0, lineHeight: 1.6 }}>
            <strong>Verbal agreements don&apos;t count.</strong> Only in-app approval is recognised. If you reject, the tradie continues at the original price.
          </p>
        </div>

        {/* Buttons */}
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={() => handle(true)} disabled={!!loading}
            style={{
              ...btn(GREEN, '#fff'),
              flex: 1, padding: '13px', borderRadius: 14,
              opacity: loading ? .6 : 1,
              boxShadow: '0 4px 14px rgba(46,125,90,.2)',
            }}>
            {loading === 'approve'
              ? <Loader2 size={15} className="animate-spin" />
              : <CheckCircle2 size={15} />}
            Approve  -  {fmtCents(job.pending_scope_amount_cents)}
          </button>
          <button onClick={() => handle(false)} disabled={!!loading}
            style={{
              ...btn(ROSE_LIGHT, ROSE),
              flex: 1, padding: '13px', borderRadius: 14,
              border: `1px solid ${ROSE}30`,
              opacity: loading ? .6 : 1,
            }}>
            {loading === 'reject'
              ? <Loader2 size={15} className="animate-spin" />
              : <XCircle size={15} />}
            Reject  -  keep original
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══ PARTIAL STOP BANNER ══════════════════════════════════════════════════════
// Shown when job.status === 'partial_stop'
function PartialStopBanner({ job, onDispute, onConfirmComplete }: {
  job: Job;
  onDispute: () => void;
  onConfirmComplete: () => Promise<void>;
}) {
  const [confirmLoading, setConfirmLoading] = useState(false);

  const handleConfirm = async () => {
    setConfirmLoading(true);
    try { await onConfirmComplete(); }
    finally { setConfirmLoading(false); }
  };

  return (
    <div style={{
      background: '#fff', border: `2px solid ${ROSE}40`,
      borderRadius: 20, overflow: 'hidden',
      boxShadow: `0 4px 20px rgba(163,48,48,.08)`,
    }}>
      <div style={{
        background: `linear-gradient(135deg, ${ROSE_LIGHT}, #FFF5F5)`,
        borderBottom: `1px solid ${ROSE}20`,
        padding: '16px 22px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{ width: 40, height: 40, borderRadius: 12, flexShrink: 0, background: ROSE_LIGHT, border: `1px solid ${ROSE}30`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <ShieldAlert size={20} color={ROSE} />
        </div>
        <div>
          <p style={{ fontWeight: 800, fontSize: 15, color: INK, margin: 0 }}>Tradie has stopped work</p>
          <p style={{ fontSize: 12, color: ROSE, margin: '2px 0 0', fontWeight: 600 }}>Admin will adjudicate within 24 hours</p>
        </div>
      </div>

      <div style={{ padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Stop reason */}
        {job.completion_note && (
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, color: INK4, textTransform: 'uppercase', letterSpacing: '.08em', margin: '0 0 8px' }}>
              Tradie&apos;s reason for stopping
            </p>
            <div style={{ padding: '12px 14px', background: CREAM, borderRadius: 12, border: `1px solid ${BORDER}` }}>
              <p style={{ fontSize: 13.5, color: INK2, lineHeight: 1.7, margin: 0 }}>
                &ldquo;{job.completion_note}&rdquo;
              </p>
            </div>
          </div>
        )}

        {/* After photo if provided */}
        {job.photo_after_url && (
          <div>
            <p style={{ fontSize: 11, fontWeight: 700, color: INK4, textTransform: 'uppercase', letterSpacing: '.08em', margin: '0 0 8px' }}>
              Work state when stopped
            </p>
            <img src={job.photo_after_url} alt="Work state when stopped"
              style={{ width: '100%', maxHeight: 220, objectFit: 'cover', borderRadius: 12, border: `1px solid ${BORDER}` }} />
          </div>
        )}

        {/* What happens next */}
        <div style={{ padding: '12px 14px', background: AMBER_LIGHT, border: `1px solid ${AMBER}25`, borderRadius: 12 }}>
          <p style={{ fontSize: 12, color: INK2, margin: 0, lineHeight: 1.65 }}>
            <strong>What happens now:</strong> Our admin team reviews the situation within 24 hours and decides the partial charge. Payment is held until resolved. You can also raise a dispute if you disagree with the tradie&apos;s reason.
          </p>
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button onClick={handleConfirm} disabled={confirmLoading}
            style={{ ...btn(GREEN, '#fff'), flex: 1, minWidth: 140, padding: '12px', borderRadius: 13, opacity: confirmLoading ? .6 : 1, boxShadow: '0 4px 12px rgba(46,125,90,.18)' }}>
            {confirmLoading ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
            Accept partial completion
          </button>
          <button onClick={onDispute}
            style={{ ...btn(ROSE_LIGHT, ROSE), flex: 1, minWidth: 140, padding: '12px', borderRadius: 13, border: `1px solid ${ROSE}25` }}>
            <AlertTriangle size={14} />
            Raise a dispute
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══ REDO JOB BANNER ══════════════════════════════════════════════════════════
// Shown when job.is_redo_job === true AND job.status === 'in_progress' | 'completed'
// Gives the homeowner context: their dispute was resolved and the tradie is
// returning to redo the work. Disappears once the job is confirmed or closed.
function RedoJobBanner() {
  return (
    <div style={{
      background: '#FFF8EE',
      border: `1.5px solid ${AMBER}40`,
      borderRadius: 16,
      padding: '16px 20px',
      display: 'flex',
      gap: 14,
      alignItems: 'flex-start',
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: 10, flexShrink: 0,
        background: AMBER_LIGHT,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        {/* Wrench icon inline  -  no extra import needed */}
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={AMBER} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>
        </svg>
      </div>
      <div style={{ flex: 1 }}>
        <p style={{ fontWeight: 800, fontSize: 14, color: AMBER, margin: '0 0 4px' }}>
          Tradie returning to redo the work
        </p>
        <p style={{ fontSize: 13, color: INK, lineHeight: 1.6, margin: 0 }}>
          Your dispute was reviewed and the tradie has been instructed to return and fix the work.
          The job is active again. Once they mark it complete, you&apos;ll be asked to confirm  - 
          and you can raise another dispute if you&apos;re still not satisfied.
        </p>
      </div>
    </div>
  );
}

// ═══ DISPUTE BANNER ═══════════════════════════════════════════════════════════
// Shown when job.status === 'disputed'
function DisputeBanner({ jobId, onResolved }: { jobId: string; onResolved: () => void }) {
  const [info, setInfo] = React.useState<{
    dispute_reason: string | null;
    responses: Array<{ id: number; actor_role: string; response: string; evidence_url: string | null; created_at: string }>;
    resolution_claimed: boolean;
    resolution_claimed_at: string | null;
    resolution_rejection_count: number;
  } | null>(null);
  const [loading, setLoading]   = React.useState(true);
  const [reply, setReply]       = React.useState('');
  const [posting, setPosting]   = React.useState(false);
  const [posted, setPosted]     = React.useState(false);
  const [acting, setActing]     = React.useState(false);
  const [actErr, setActErr]     = React.useState('');
  const [rejected, setRejected] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get(`/jobs/${jobId}/dispute-info`);
      setInfo({
        dispute_reason: data?.dispute_reason || null,
        responses: data?.responses || [],
        resolution_claimed: data?.resolution_claimed || false,
        resolution_claimed_at: data?.resolution_claimed_at || null,
        resolution_rejection_count: data?.resolution_rejection_count || 0,
      });
    } catch { /* show static banner even on error */ }
    finally { setLoading(false); }
  }, [jobId]);

  React.useEffect(() => { load(); }, [load]);

  const submitReply = async () => {
    if (reply.trim().length < 5) return;
    setPosting(true);
    try {
      await api.post(`/jobs/${jobId}/dispute-response`, { response: reply.trim() });
      setReply(''); setPosted(true); await load();
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Could not send the message.');
    } finally { setPosting(false); }
  };

  const handleResolutionResponse = async (accept: boolean) => {
    setActing(true); setActErr('');
    try {
      await api.post(`/jobs/${jobId}/dispute-accept-resolution`, { accept });
      if (accept) {
        onResolved(); // triggers parent reload  -  job is now "completed"
      } else {
        setRejected(true);
        await load(); // refresh rejection count
      }
    } catch (e: any) {
      setActErr(e?.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally { setActing(false); }
  };

  // ── When tradie has claimed resolution: show the accept/reject prompt ──────
  if (info?.resolution_claimed) {
    return (
      <div style={{ background: '#fff', border: `2px solid ${GREEN}50`, borderRadius: 20, padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
          <div style={{ width: 44, height: 44, borderRadius: 12, flexShrink: 0, background: GREEN_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <CheckCircle2 size={22} color={GREEN} />
          </div>
          <div style={{ flex: 1 }}>
            <p style={{ fontWeight: 800, fontSize: 15, color: INK, margin: '0 0 5px' }}>Tradie says they&apos;ve fixed it</p>
            <p style={{ fontSize: 13, color: INK2, lineHeight: 1.65, margin: 0 }}>
              The tradie has marked this dispute as resolved from their side.
              {info.resolution_claimed_at ? ` They submitted this ${timeAgo(info.resolution_claimed_at)}.` : ''}
              {' '}Is the issue actually fixed?
            </p>
          </div>
        </div>

        {rejected && (
          <div style={{ background: AMBER_LIGHT, border: `1px solid ${AMBER}40`, borderRadius: 10, padding: '10px 14px' }}>
            <p style={{ fontSize: 13, color: AMBER, margin: 0, lineHeight: 1.55 }}>
              Your rejection has been sent to the tradie.
              {(info.resolution_rejection_count || 0) >= 2
                ? ' Our admin team has been notified and will step in to help resolve this.'
                : ' They can address your concerns and re-submit when they believe it is fixed.'}
            </p>
          </div>
        )}

        {actErr && <p style={{ fontSize: 12.5, color: ROSE, margin: 0 }}>{actErr}</p>}

        {!rejected && (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <button
              onClick={() => handleResolutionResponse(true)}
              disabled={acting}
              style={{ flex: 1, minWidth: 140, padding: '12px 16px', borderRadius: 12, background: GREEN, color: '#fff', border: 'none', fontSize: 13.5, fontWeight: 700, cursor: acting ? 'wait' : 'pointer', opacity: acting ? 0.6 : 1 }}>
              {acting ? 'Processing...' : 'Yes, it\'s resolved'}
            </button>
            <button
              onClick={() => handleResolutionResponse(false)}
              disabled={acting}
              style={{ flex: 1, minWidth: 140, padding: '12px 16px', borderRadius: 12, background: '#fff', color: ROSE, border: `1.5px solid ${ROSE}`, fontSize: 13.5, fontWeight: 700, cursor: acting ? 'wait' : 'pointer', opacity: acting ? 0.6 : 1 }}>
              {acting ? 'Processing...' : 'Still not right'}
            </button>
          </div>
        )}

        {/* Conversation history visible even on the resolution screen */}
        {info.dispute_reason && (
          <div style={{ background: ROSE_LIGHT, border: `1px solid ${ROSE}33`, borderRadius: 10, padding: '10px 14px' }}>
            <p style={{ fontSize: 10.5, fontWeight: 700, color: ROSE, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 4px' }}>Your original dispute reason</p>
            <p style={{ fontSize: 13, color: INK, margin: 0, lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{info.dispute_reason}</p>
          </div>
        )}
        {info.responses.length > 0 && (
          <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <p style={{ fontSize: 10.5, fontWeight: 700, color: INK4, textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>Conversation ({info.responses.length})</p>
            {info.responses.map(r => (
              <div key={r.id} style={{ background: r.actor_role === 'tradie' ? BLUE_LIGHT : CREAM2, border: `1px solid ${r.actor_role === 'tradie' ? BLUE + '33' : BORDER}`, borderRadius: 10, padding: '10px 14px' }}>
                <p style={{ fontSize: 10.5, fontWeight: 700, color: r.actor_role === 'tradie' ? BLUE : INK3, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 4px' }}>
                  {r.actor_role === 'tradie' ? 'Tradie' : 'You'} - {timeAgo(r.created_at)}
                </p>
                <p style={{ fontSize: 13, color: INK, margin: 0, lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{r.response}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── Default: dispute is open, waiting for tradie to claim resolution ────────
  return (
    <div style={{ background: '#fff', border: `2px solid ${ROSE}40`, borderRadius: 20, padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
        <div style={{ width: 44, height: 44, borderRadius: 12, flexShrink: 0, background: ROSE_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <ShieldAlert size={22} color={ROSE} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontWeight: 800, fontSize: 15, color: INK, margin: '0 0 6px' }}>Dispute under review</p>
          <p style={{ fontSize: 13, color: INK2, lineHeight: 1.65, margin: 0 }}>
            The tradie has been notified and will respond shortly. Once they mark it resolved, you&apos;ll be asked to confirm. Payment is held until this is sorted.
          </p>
        </div>
      </div>

      {info?.dispute_reason && (
        <div style={{ background: ROSE_LIGHT, border: `1px solid ${ROSE}33`, borderRadius: 10, padding: '10px 14px' }}>
          <p style={{ fontSize: 10.5, fontWeight: 700, color: ROSE, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 4px' }}>Your dispute reason</p>
          <p style={{ fontSize: 13.5, color: INK, margin: 0, lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{info.dispute_reason}</p>
        </div>
      )}

      {info && info.responses.length > 0 && (
        <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <p style={{ fontSize: 10.5, fontWeight: 700, color: INK4, textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0 }}>Conversation ({info.responses.length})</p>
          {info.responses.map(r => (
            <div key={r.id} style={{ background: r.actor_role === 'tradie' ? BLUE_LIGHT : CREAM2, border: `1px solid ${r.actor_role === 'tradie' ? BLUE + '33' : BORDER}`, borderRadius: 10, padding: '10px 14px' }}>
              <p style={{ fontSize: 10.5, fontWeight: 700, color: r.actor_role === 'tradie' ? BLUE : INK3, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 4px' }}>
                {r.actor_role === 'tradie' ? 'Tradie' : 'You'} - {timeAgo(r.created_at)}
              </p>
              <p style={{ fontSize: 13, color: INK, margin: 0, lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{r.response}</p>
              {r.evidence_url && (
                <a href={r.evidence_url} target="_blank" rel="noreferrer" style={{ display: 'inline-block', marginTop: 6, fontSize: 11.5, color: BLUE, textDecoration: 'underline' }}>View attached evidence</a>
              )}
            </div>
          ))}
        </div>
      )}

      <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 10 }}>
        {posted && <p style={{ fontSize: 12, color: GREEN, margin: '0 0 6px' }}>Your message was sent. The tradie will see it.</p>}
        <p style={{ fontSize: 10.5, fontWeight: 700, color: INK3, textTransform: 'uppercase', letterSpacing: '0.08em', margin: '0 0 6px' }}>Add to the conversation</p>
        <textarea value={reply} onChange={e => setReply(e.target.value)} rows={3}
          placeholder="Add more context or anything you forgot to mention."
          style={{ width: '100%', padding: '9px 12px', borderRadius: 10, border: `1px solid ${BORDER}`, fontSize: 13, fontFamily: 'inherit', resize: 'vertical', background: '#fff' }} />
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
          <button onClick={submitReply} disabled={posting || reply.trim().length < 5}
            style={{ padding: '8px 14px', borderRadius: 10, background: INK, color: '#fff', border: 'none', fontSize: 12.5, fontWeight: 700, cursor: 'pointer', opacity: (posting || reply.trim().length < 5) ? 0.5 : 1 }}>
            {posting ? 'Sending...' : 'Send message'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══ DISPUTE MODAL ════════════════════════════════════════════════════════════
function DisputeModal({ jobId, onClose, onSubmitted }: {
  jobId: string;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const submit = async () => {
    if (reason.trim().length < 10) { setErr('Please describe the issue in at least 10 characters.'); return; }
    setLoading(true); setErr('');
    try {
      await api.post(`/jobs/${jobId}/dispute`, { reason: reason.trim() });
      onSubmitted();
      onClose();
    } catch (e: any) {
      const d = e?.response?.data?.detail;
      setErr(typeof d === 'string' ? d : 'Could not raise dispute. Try again.');
    } finally { setLoading(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 200,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 16, background: 'rgba(7,29,54,0.55)', backdropFilter: 'blur(6px)',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', maxWidth: 440, background: '#fff',
        borderRadius: 24, border: `1px solid ${BORDER}`, overflow: 'hidden',
        boxShadow: '0 32px 80px rgba(44,26,14,.18)',
      }}>
        {/* Header */}
        <div style={{ background: `linear-gradient(135deg, ${ROSE} 0%, #7A1A1A 100%)`, padding: '22px 24px', position: 'relative' }}>
          <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, width: 32, height: 32, borderRadius: 10, background: 'rgba(255,255,255,.15)', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,.8)' }}>
            <X size={14} />
          </button>
          <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '.1em', textTransform: 'uppercase', color: 'rgba(255,255,255,.5)', marginBottom: 4 }}>Dispute</p>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: '#fff', margin: 0 }}>Raise a dispute</h2>
        </div>

        <div style={{ padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ padding: '12px 14px', background: AMBER_LIGHT, border: `1px solid ${AMBER}25`, borderRadius: 12 }}>
            <p style={{ fontSize: 12.5, color: INK2, margin: 0, lineHeight: 1.6 }}>
              Describe the issue clearly. Our team will review both sides within 2 business days. Payment is held until resolved.
            </p>
          </div>

          {err && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: ROSE_LIGHT, border: `1px solid ${ROSE}30`, color: ROSE, padding: '10px 14px', borderRadius: 10, fontSize: 13 }}>
              <AlertCircle size={14} />{err}
            </div>
          )}

          <div>
            <label style={{ fontSize: 11, fontWeight: 700, color: INK3, textTransform: 'uppercase', letterSpacing: '.08em', display: 'block', marginBottom: 8 }}>
              Describe the issue <span style={{ color: ROSE }}>*</span>
            </label>
            <textarea rows={5} value={reason} onChange={e => setReason(e.target.value)}
              placeholder="e.g. The tradie left the site incomplete without finishing the work that was agreed on..."
              style={{ width: '100%', padding: '12px 14px', borderRadius: 12, border: `1.5px solid ${BORDER}`, background: CREAM, color: INK, fontSize: 14, lineHeight: 1.65, resize: 'vertical', fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box' }}
              onFocus={e => { e.currentTarget.style.borderColor = TERRA; e.currentTarget.style.background = '#fff'; }}
              onBlur={e => { e.currentTarget.style.borderColor = BORDER; e.currentTarget.style.background = CREAM; }} />
            <p style={{ fontSize: 11, color: INK4, marginTop: 5, fontVariantNumeric: 'tabular-nums' }}>{reason.length} characters  |  minimum 10</p>
          </div>

          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={onClose} style={{ ...btn(CREAM2, INK2), flex: 0, padding: '12px 20px', borderRadius: 13, border: `1px solid ${BORDER}` }}>
              Cancel
            </button>
            <button onClick={submit} disabled={loading}
              style={{ ...btn(ROSE, '#fff'), flex: 1, padding: '12px', borderRadius: 13, opacity: loading ? .6 : 1 }}>
              {loading ? <Loader2 size={14} className="animate-spin" /> : <ShieldAlert size={14} />}
              {loading ? 'Submitting...' : 'Submit dispute'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══ QUOTE MODAL ══════════════════════════════════════════════════════════════
function QuoteModal({ quote, onClose, onAction }: {
  quote: Quote;
  onClose: () => void;
  onAction: (id: string, status: 'accepted' | 'rejected') => Promise<void>;
}) {
  const [loading, setLoading] = useState<'accept' | 'reject' | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const isPending = quote.status === 'pending';

  const handle = async (action: 'accepted' | 'rejected') => {
    setLoading(action === 'accepted' ? 'accept' : 'reject');
    setActionError(null);
    try {
      await onAction(quote.id, action);
      onClose(); // success  -  close modal (loadData already called inside onAction)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Something went wrong. Please try again.';
      setActionError(detail);
      setLoading(null);
    }
  };

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 200,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: 16, background: 'rgba(7,29,54,0.55)', backdropFilter: 'blur(6px)',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', maxWidth: 420, background: '#fff',
        borderRadius: 24, border: `1px solid ${BORDER}`, overflow: 'hidden',
        boxShadow: '0 32px 80px rgba(44,26,14,.18)',
      }}>
        <div style={{ background: `linear-gradient(145deg, ${INK} 0%, ${INK2} 100%)`, padding: '22px 24px', position: 'relative', overflow: 'hidden' }}>
          <div style={{ position: 'absolute', top: -60, right: -60, width: 180, height: 180, borderRadius: '50%', background: 'radial-gradient(circle, rgba(212,170,58,.28), transparent)', pointerEvents: 'none' }} />
          <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '.1em', textTransform: 'uppercase', color: 'rgba(255,255,255,.4)', marginBottom: 4 }}>Quote received</p>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: '#fff', margin: 0 }}>Review this offer</h2>
          <button onClick={onClose} style={{ position: 'absolute', top: 16, right: 16, width: 32, height: 32, borderRadius: 10, background: 'rgba(255,255,255,.12)', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,.65)' }}>
            <X size={14} />
          </button>
        </div>
        <div style={{ padding: '16px 22px', borderBottom: `1px solid ${CREAM2}`, display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 48, height: 48, borderRadius: 14, flexShrink: 0, background: `linear-gradient(135deg, ${avatarGrad(quote.id)})`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 800, fontSize: 16 }}>
            {initials(quote.tradie_name)}
          </div>
          <div>
            <p style={{ fontWeight: 700, fontSize: 15, color: INK }}>{quote.tradie_name || 'Tradie'}</p>
            <div style={{ display: 'flex', gap: 2, alignItems: 'center', margin: '3px 0' }}>
              {[...Array(5)].map((_, i) => <Star key={i} size={12} style={{ fill: '#F59E0B', color: '#F59E0B' }} />)}
              <span style={{ fontSize: 11, color: INK4, marginLeft: 4 }}>5.0  |  Verified</span>
            </div>
            {quote.created_at && <p style={{ fontSize: 11, color: INK4 }}>{timeAgo(quote.created_at)}</p>}
          </div>
        </div>
        <div style={{ margin: '16px 22px', background: TERRA_LIGHT, border: '1px solid rgba(212,170,58,.2)', borderRadius: 16, padding: 20, textAlign: 'center' }}>
          <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', color: TERRA, marginBottom: 6 }}>Total Quote</p>
          <p style={{ fontSize: 40, fontWeight: 800, color: INK, lineHeight: 1 }}>${(quote.amount || 0).toLocaleString()}</p>
          <p style={{ fontSize: 11, color: INK4, marginTop: 4 }}>Estimated all-in price</p>
        </div>
        {quote.message && (
          <div style={{ padding: '0 22px 14px' }}>
            <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', color: INK4, marginBottom: 8 }}>Their message</p>
            <div style={{ background: CREAM, borderRadius: 12, padding: 14 }}>
              <p style={{ fontSize: 12, lineHeight: 1.7, color: INK2 }}>&ldquo;{quote.message}&rdquo;</p>
            </div>
          </div>
        )}
        <div style={{ padding: '0 22px 14px' }}>
          <span style={{ fontSize: 11, fontWeight: 700, padding: '5px 12px', borderRadius: 20, background: quote.status === 'accepted' ? GREEN_LIGHT : quote.status === 'rejected' ? ROSE_LIGHT : AMBER_LIGHT, color: quote.status === 'accepted' ? GREEN : quote.status === 'rejected' ? ROSE : AMBER }}>
            {quote.status === 'accepted' ? 'Accepted' : quote.status === 'rejected' ? 'Declined' : 'Awaiting decision'}
          </span>
        </div>
        {actionError && (
          <div style={{ margin: '0 22px 12px', padding: '10px 14px', borderRadius: 10, background: ROSE_LIGHT, border: `1px solid ${ROSE}33` }}>
            <p style={{ fontSize: 12, color: ROSE, fontWeight: 600, margin: 0 }}>{actionError}</p>
          </div>
        )}
        {isPending && (
          <div style={{ padding: '0 22px 22px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button onClick={() => handle('accepted')} disabled={!!loading}
              style={{ ...btn(GREEN, '#fff'), padding: '13px', borderRadius: 14, opacity: loading ? .6 : 1, width: '100%' }}>
              {loading === 'accept' ? <Loader2 size={16} className="animate-spin" /> : <ThumbsUp size={16} />}
              Accept Quote
            </button>
            <button onClick={() => handle('rejected')} disabled={!!loading}
              style={{ ...btn(ROSE_LIGHT, ROSE), padding: '13px', borderRadius: 14, opacity: loading ? .6 : 1, width: '100%' }}>
              {loading === 'reject' ? <Loader2 size={16} className="animate-spin" /> : <ThumbsDown size={16} />}
              Decline
            </button>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {[{ icon: <Phone size={14} />, label: 'Call' }, { icon: <MessageSquare size={14} />, label: 'Message' }].map(({ icon, label }) => (
                <button key={label} style={{ ...btn(CREAM2, INK2), borderRadius: 12, border: `1px solid ${BORDER}` }}>{icon} {label}</button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══ JOB CARD (sidebar) ═══════════════════════════════════════════════════════
function JobCard({ job, selected, onClick, quoteCount }: {
  job: Job; selected: boolean; onClick: () => void; quoteCount: number;
}) {
  const s = STATUS[job.status] || STATUS.open;
  const u = URGENCY[job.urgency];
  const isNewState = ['awaiting_scope_approval', 'partial_stop', 'disputed'].includes(job.status);
  const needsReview = job.status === 'confirmed' && !job.has_review;
  return (
    <button onClick={onClick} style={{
      width: '100%', textAlign: 'left', borderRadius: 14, padding: '12px 14px',
      cursor: 'pointer',
      border: selected ? `1.5px solid ${TERRA}` : needsReview ? `1.5px solid ${TERRA}60` : isNewState ? `1.5px solid ${s.color}40` : '1.5px solid transparent',
      background: selected ? '#fff' : CREAM, transition: 'all .15s',
      boxShadow: selected ? `0 4px 12px rgba(212,170,58,.08)` : 'none',
    }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = CREAM2; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = CREAM; }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', marginBottom: 6 }}>
        <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 8px', borderRadius: 20, color: s.color, background: s.bg }}>
          {isNewState ? '' : ''}{s.label}
        </span>
        {u && <span style={{ fontSize: 10, color: INK4 }}>{u.label}</span>}
        {quoteCount > 0 && (
          <span style={{ marginLeft: 'auto', fontSize: 10, fontWeight: 800, background: TERRA, color: '#fff', padding: '3px 8px', borderRadius: 20 }}>
            {quoteCount} quote{quoteCount > 1 ? 's' : ''}
          </span>
        )}
        {needsReview && (
          <span style={{ marginLeft: 'auto', fontSize: 10, fontWeight: 800, background: TERRA_LIGHT, color: TERRA, padding: '3px 8px', borderRadius: 20, border: `1px solid ${TERRA}40` }}>
            Review needed
          </span>
        )}
        {isNewState && !needsReview && (
          <span style={{ marginLeft: 'auto', fontSize: 10, fontWeight: 800, background: s.color, color: '#fff', padding: '3px 8px', borderRadius: 20 }}>
            Action needed
          </span>
        )}
      </div>
      <p style={{ fontWeight: 600, fontSize: 13, color: INK, lineHeight: 1.3 }}>{job.title}</p>
      <p style={{ fontSize: 11, color: INK4, marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
        <MapPin size={11} /> {job.suburb}, {job.state}  |  {timeAgo(job.created_at || job.created)}
      </p>
    </button>
  );
}

// ═══ PROGRESS STEP ════════════════════════════════════════════════════════════
function ProgressStep({ done, label, sub, color, isLast }: {
  done: boolean; label: string; sub: string; color: string; isLast: boolean;
}) {
  return (
    <div style={{ display: 'flex', gap: 12, marginBottom: isLast ? 0 : 4 }}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <div style={{ width: 26, height: 26, borderRadius: 8, flexShrink: 0, background: done ? color : CREAM2, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {done ? <Check size={13} color="#fff" strokeWidth={2.5} /> : <div style={{ width: 8, height: 8, borderRadius: '50%', background: BORDER }} />}
        </div>
        {!isLast && <div style={{ width: 2, flex: 1, minHeight: 16, margin: '4px 0', borderRadius: 2, background: done ? color + '44' : CREAM2 }} />}
      </div>
      <div style={{ paddingBottom: isLast ? 0 : 12, paddingTop: 4 }}>
        <p style={{ fontSize: 13, fontWeight: 600, color: done ? INK : INK4 }}>{label}</p>
        <p style={{ fontSize: 11, marginTop: 2, color: done ? color : INK4 }}>{sub}</p>
      </div>
    </div>
  );
}

// ═══ MATCH INTELLIGENCE CARD ══════════════════════════════════════════════════
function MatchIntelCard({ raw }: { raw?: string }) {
  const intel = parseMatchIntel(raw);
  if (!intel || intel.matched === 0) return null;
  const stats = [
    { value: intel.in_area, label: 'tradies in your area', sub: 'match this category', color: TERRA, bg: TERRA_LIGHT },
    { value: intel.matched, label: 'have been notified', sub: 'and can quote now', color: GREEN, bg: GREEN_LIGHT },
    { value: `~${intel.avg_response_hours}h`, label: 'avg first quote', sub: 'based on your urgency', color: AMBER, bg: AMBER_LIGHT },
  ];
  return (
    <div style={{ ...card, display: 'flex', overflow: 'hidden' }}>
      {stats.map((stat, i) => (
        <div key={i} style={{ flex: 1, padding: '14px 10px', textAlign: 'center', borderRight: i < 2 ? `1px solid ${BORDER}` : 'none' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 38, height: 38, borderRadius: 10, background: stat.bg, marginBottom: 6 }}>
            <p style={{ fontSize: 15, fontWeight: 800, color: stat.color, lineHeight: 1 }}>{stat.value}</p>
          </div>
          <p style={{ fontSize: 11, fontWeight: 700, color: INK, lineHeight: 1.3 }}>{stat.label}</p>
          <p style={{ fontSize: 10, color: INK4, marginTop: 2 }}>{stat.sub}</p>
        </div>
      ))}
    </div>
  );
}

// ═══ MAIN DASHBOARD ═══════════════════════════════════════════════════════════
export default function HomeownerDashboardView() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const view = searchParams.get('view');

  const [jobs, setJobs] = useState<Job[]>([]);
  const [allQuotes, setAllQuotes] = useState<Quote[]>([]);
  const [quoteLoadFailedJobIds, setQuoteLoadFailedJobIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedQuote, setSelectedQuote] = useState<Quote | null>(null);
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const [editingJobId, setEditingJobId] = useState<string | null>(null);
  const [editDesc, setEditDesc] = useState('');
  const [editSaving, setEditSaving] = useState(false);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [historyJobs, setHistoryJobs] = useState<Job[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [reviewModalJobId, setReviewModalJobId] = useState<string | null>(null);
  // completingJobId removed  -  homeowner cannot directly mark in_progress→completed;
  // only the tradie can do that via POST /jobs/{id}/complete with photos.
  // ── NEW: dispute modal ────────────────────────────────────────────────────
  const [disputeModalJobId, setDisputeModalJobId] = useState<string | null>(null);
  const [confirmingCompleteJobId, setConfirmingCompleteJobId] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  // ── Ref keeps loadData's closure in sync with the current selectedJobId ───────
  // Without this, loadData (wrapped in useCallback([user])) captures
  // selectedJobId = null from mount time and always resets the selection.
  const selectedJobIdRef = useRef<string | null>(null);
  useEffect(() => { selectedJobIdRef.current = selectedJobId; }, [selectedJobId]);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 1024);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  const quotesByJob = useMemo(() => {
    const m: Record<string, Quote[]> = {};
    allQuotes.forEach(q => { if (q.job_id) { m[q.job_id] = m[q.job_id] || []; m[q.job_id].push(q); } });
    return m;
  }, [allQuotes]);

  const loadData = useCallback(async () => {
    if (!user) return;
    setIsLoading(true); setError(null);
    try {
      const { data } = await api.get('/jobs/my-jobs');
      const fetchedJobs: Job[] = data?.jobs || data || [];
      setJobs(fetchedJobs);
      const failedIds = new Set<string>();
      const quoteArrays = await Promise.all(
        fetchedJobs
          .filter(j => ['quoted', 'hired', 'in_progress', 'open', 'awaiting_scope_approval', 'partial_stop', 'disputed'].includes(j.status))
          .map(j =>
            api.get(`/quotes/job/${j.id}`)
              .then(r => (r.data?.quotes || r.data || []).map((q: Quote) => ({ ...q, job_id: q.job_id || j.id, job_title: q.job_title || j.title })))
              .catch(err => { console.error(`[quotes] failed to load for job ${j.id}:`, err?.response?.status, err?.response?.data?.detail || err?.message); failedIds.add(j.id); return []; })
          )
      );
      setAllQuotes(quoteArrays.flat());
      setQuoteLoadFailedJobIds(failedIds);
      const firstActive = fetchedJobs.find(j => !['completed', 'cancelled', 'closed'].includes(j.status));
      if (firstActive && !selectedJobIdRef.current) setSelectedJobId(firstActive.id);
    } catch {
      setError('Failed to load dashboard. Please refresh.');
    } finally { setIsLoading(false); }
  }, [user]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Real-time status push ─────────────────────────────────────────────────
  // The backend's JobStateMachine broadcasts a 'job:status_changed' event to
  // every party on the job (homeowner + each tradie that has a lead) whenever
  // a status transition is committed. Subscribe here so the dashboard refreshes
  // the instant the tradie marks complete, a dispute is raised, the system
  // auto-closes after 48h, etc.  -  no manual page reload needed.
  //
  // Falls back to silent no-op if WebSockets aren't reachable (e.g. behind a
  // proxy that strips the upgrade header); the existing manual reload path
  // still works.
  useEffect(() => {
    if (!user) return;
    // Lazy-import to avoid pulling auth helpers into the SSR bundle.
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = async () => {
      try {
        const { default: apiClient } = await import('@/src/lib/api');
        let ticket: string | undefined;
        try {
          ticket = (await apiClient.post('/auth/ws-ticket')).data?.ticket;
        } catch { return; }
        if (!ticket) return;
        // The /api/proxy route handles HTTP, but WebSockets need to talk
        // straight to the FastAPI host. NEXT_PUBLIC_API_URL is the public
        // base URL; flip http(s):// -> ws(s)://.
        const apiBase = process.env.NEXT_PUBLIC_API_URL || window.location.origin;
        const wsBase = apiBase.replace(/^http/, 'ws');
        ws = new WebSocket(`${wsBase}/ws?ticket=${encodeURIComponent(ticket)}`);

        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg?.type === 'job:status_changed') {
              // Pull the latest snapshot; cheap and avoids drift bugs that come
              // from trying to merge a delta into local state.
              loadData().catch(() => {});
            }
          } catch { /* ignore non-JSON heartbeats */ }
        };

        ws.onclose = () => {
          if (closed) return;
          // Auto-reconnect with a small backoff so dropped sockets recover
          // (e.g. laptop wakes from sleep, mobile network flap).
          reconnectTimer = setTimeout(connect, 5000);
        };

        ws.onerror = () => {
          try { ws?.close(); } catch { /* noop */ }
        };
      } catch {
        // Non-fatal: dashboard still works without real-time updates.
      }
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      try { ws?.close(); } catch { /* noop */ }
    };
  }, [user, loadData]);

  const loadHistory = useCallback(async () => {
    if (!user) return;
    setHistoryLoading(true);
    try { const { data } = await api.get('/jobs/history'); setHistoryJobs(data || []); }
    catch { setHistoryJobs([]); }
    finally { setHistoryLoading(false); }
  }, [user]);

  useEffect(() => { if (view === 'history') loadHistory(); }, [view, loadHistory]);

  const handleQuoteAction = async (quoteId: string, status: 'accepted' | 'rejected') => {
    try {
      await api.patch(`/quotes/${quoteId}/status?new_status=${status}`);
      await loadData();
    } catch (err: any) {
      // Always refresh even on failure  -  the backend may have committed the
      // change before the response errored, so the UI must stay in sync with DB.
      await loadData().catch(() => {});
      throw err; // re-throw so QuoteModal can display the error message
    }
  };

  const handleCancelJob = async (jobId: string) => {
    if (!confirm('Cancel this job? Tradies will be notified and it will move to your job history.')) return;
    setCancellingJobId(jobId);
    try {
      await api.patch(`/jobs/${jobId}/status?new_status=cancelled`);
      await api.delete(`/jobs/${jobId}`);
      setJobs(prev => prev.filter(j => j.id !== jobId));
      if (selectedJobId === jobId) setSelectedJobId(null);
    } catch { alert('Could not cancel job. Please try again.'); }
    finally { setCancellingJobId(null); }
  };

  const handleRepost = (job: Job) => {
    const draft = { description: job.description || '', category_name: job.category_name || '', suburb: job.suburb, state: job.state, step: 2 };
    localStorage.setItem('proconnect_job_draft', JSON.stringify(draft));
    router.push('/book');
  };

  const handleClearHistory = async (jobId: string) => {
    if (!confirm('Permanently remove this from history?')) return;
    try { await api.delete(`/jobs/history/clear?job_id=${jobId}`); setHistoryJobs(prev => prev.filter(j => j.id !== jobId)); }
    catch { alert('Could not clear history.'); }
  };

  const handleSaveEdit = async (jobId: string) => {
    setEditSaving(true);
    try { await api.patch(`/jobs/${jobId}`, { description: editDesc }); await loadData(); setEditingJobId(null); }
    catch { alert('Could not save changes.'); }
    finally { setEditSaving(false); }
  };

  // handleMarkComplete removed  -  homeowner cannot mark in_progress→completed directly.
  // The state machine enforces that only tradies can make this transition (with photos).
  // Homeowners confirm completion after the tradie has marked it done.

  // ── NEW: Scope change respond ────────────────────────────────────────────────
  const handleScopeChangeRespond = async (jobId: string, approve: boolean) => {
    await api.post(`/jobs/${jobId}/scope-change/respond`, { approve });
    await loadData();
  };

  // ── Confirm complete (after tradie marks done) ────────────────────────────────
  const handleConfirmComplete = async (jobId: string) => {
    setConfirmingCompleteJobId(jobId);
    setConfirmError(null);
    try {
      console.log('[confirm-complete] Sending POST for job:', jobId);
      const res = await api.post(`/jobs/${jobId}/confirm-complete`);
      console.log('[confirm-complete] Success:', res.data);
      // Optimistically update the job status in state so the UI flips immediately
      // even before loadData() completes its re-fetch.
      setJobs(prev => prev.map(j => j.id === jobId ? { ...j, status: 'confirmed' } : j));
      await loadData();
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      console.error('[confirm-complete] Error:', status, detail, err);
      setConfirmError(detail || `Could not confirm completion (HTTP ${status ?? 'network error'}). Please try again.`);
    } finally {
      setConfirmingCompleteJobId(null);
    }
  };

  const handlePhotoUpload = async (file: File, jobId: string) => {
    if (photoUploading) return;
    setPhotoUploading(true);
    try { await uploadPhotoToJob(file, jobId); await loadData(); }
    catch (err: any) { alert(`Photo upload failed: ${err.message || 'Unknown error'}`); }
    finally { setPhotoUploading(false); }
  };

  const handleRemovePhoto = async (jobId: string, photoId: string) => {
    try { await api.delete(`/jobs/${jobId}/photos/${photoId}`); await loadData(); }
    catch { alert('Could not remove photo.'); }
  };

  // 'completed' MUST be in this list. When the tradie marks the job done, the
  // homeowner has 48 hours to confirm or dispute. If we don't surface the job
  // in "Your Jobs", the homeowner can never reach the Confirm / Dispute buttons
  // and the dashboard looks empty even though there's pending action.
  // 'confirmed' without a review stays here too so the review CTA is reachable.
  const ACTIVE_STATUSES = ['open', 'quoted', 'hired', 'in_progress', 'awaiting_scope_approval', 'partial_stop', 'disputed', 'completed'];
  const activeJobs = [...jobs.filter(j => ACTIVE_STATUSES.includes(j.status) || (j.status === 'confirmed' && !j.has_review))].sort((a, b) => {
    // Surface action-needed states first: dispute > scope change > partial stop >
    // tradie-marked-complete (homeowner action required) > everything else.
    const URGENT_ORDER: Record<string, number> = {
      disputed: 4, awaiting_scope_approval: 3, partial_stop: 2, completed: 1,
    };
    const aUrgent = URGENT_ORDER[a.status] || 0;
    const bUrgent = URGENT_ORDER[b.status] || 0;
    if (bUrgent !== aUrgent) return bUrgent - aUrgent;
    const aPending = (quotesByJob[a.id] || []).filter(q => q.status === 'pending').length;
    const bPending = (quotesByJob[b.id] || []).filter(q => q.status === 'pending').length;
    if (bPending !== aPending) return bPending - aPending;
    return 0;
  });
  // A job is "completed" for archive purposes once the homeowner has confirmed it
  // OR the system auto-closed it after the 48-hour dispute window. Either way the
  // work is done and the user is no longer being asked to act. We deliberately do
  // NOT gate on has_review  -  leaving a review is optional and shouldn't determine
  // whether the homeowner can see their own finished jobs in the archive.
  const completedJobs = jobs.filter(j => j.status === 'confirmed' || j.status === 'closed');

  const pendingQuotes = allQuotes.filter(q => q.status === 'pending');
  const actionNeededJobs = activeJobs.filter(j => ['awaiting_scope_approval', 'partial_stop', 'disputed'].includes(j.status));

  const selectedJob = jobs.find(j => j.id === selectedJobId) || null;
  const jobQuotes = selectedJob ? (quotesByJob[selectedJob.id] || []) : [];
  const jobPending = jobQuotes.filter(q => q.status === 'pending');
  const firstName = user?.name?.split(' ')[0] || 'there';

  // ── History view ──────────────────────────────────────────────────────────
  if (view === 'history') {
    return (
      <div style={{ background: CREAM, minHeight: '100vh', padding: isMobile ? '20px 14px' : '32px 28px', overflowX: 'hidden' }}>
        <div style={{ maxWidth: 800, width: '100%', margin: '0 auto' }}>
          <h2 style={{ fontSize: isMobile ? 24 : 26, fontWeight: 800, color: INK, marginBottom: 6 }}>Job History</h2>
          <p style={{ fontSize: 13, color: INK4, marginBottom: 20 }}>Cancelled and deleted jobs  -  re-post anytime.</p>
          <div style={{ ...card, overflow: 'hidden' }}>
            {historyLoading ? (
              <div style={{ padding: 40, textAlign: 'center' }}><Loader2 size={20} color={TERRA} className="animate-spin" /></div>
            ) : historyJobs.length === 0 ? (
              <div style={{ padding: '60px 40px', textAlign: 'center', color: INK4, fontSize: 14 }}>No job history yet.</div>
            ) : historyJobs.map((job, i) => {
              const u = URGENCY[job.urgency];
              return (
                <div key={job.id} style={{ padding: isMobile ? '16px 18px' : '18px 22px', borderBottom: i < historyJobs.length - 1 ? `1px solid ${CREAM2}` : 'none', display: 'flex', flexDirection: isMobile ? 'column' : 'row', alignItems: isMobile ? 'stretch' : 'center', justifyContent: 'space-between', gap: 14 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 4, flexWrap: 'wrap' }}>
                      <p style={{ fontWeight: 700, color: INK, fontSize: 14, margin: 0, overflowWrap: 'anywhere' }}>{job.title}</p>
                      <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20, background: job.status === 'cancelled' ? ROSE_LIGHT : CREAM2, color: job.status === 'cancelled' ? ROSE : INK4 }}>
                        {job.status === 'cancelled' ? 'Cancelled' : 'Deleted'}
                      </span>
                    </div>
                    <p style={{ fontSize: 12, color: INK4 }}>{job.suburb}, {job.state}{u && ` | ${u.label}`}{job.deleted_at && ` | ${timeAgo(job.deleted_at)}`}</p>
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexShrink: 0, width: isMobile ? '100%' : 'auto' }}>
                    <button onClick={() => handleRepost(job)} style={{ flex: isMobile ? 1 : 'initial', padding: '8px 14px', borderRadius: 10, background: TERRA_LIGHT, border: '1px solid rgba(212,170,58,.25)', color: TERRA, fontWeight: 700, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}>
                      Re-post
                    </button>
                    <button onClick={() => handleClearHistory(job.id)} style={{ width: 34, height: 34, borderRadius: 10, background: ROSE_LIGHT, color: ROSE, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }} title="Remove permanently">
                      <X size={14} />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // ── Completed view ────────────────────────────────────────────────────────
  if (view === 'completed') {
    // Show every confirmed/closed job in the archive. We used to gate on
    // (has_review && >24h since completed_at) which made the archive empty for
    // homeowners who confirmed a job but hadn't left a review yet  -  and they
    // could never find their own completed jobs. Confirmation is what marks a
    // job as truly done; reviews are an optional next step, surfaced via the
    // review CTA on the main dashboard.
    const trueCompleted = [...completedJobs].sort((a, b) => {
      const at = a.confirmed_by_user_at || a.completed_at || a.created_at || a.created || '';
      const bt = b.confirmed_by_user_at || b.completed_at || b.created_at || b.created || '';
      return bt.localeCompare(at);
    });
    return (
      <div style={{ background: CREAM, minHeight: '100vh', padding: isMobile ? '20px 14px' : '32px 28px' }}>
        <div style={{ maxWidth: 800, margin: '0 auto' }}>
          <h2 style={{ fontSize: 26, fontWeight: 800, color: INK, marginBottom: 6 }}>Completed Jobs</h2>
          <p style={{ fontSize: 13, color: INK4, marginBottom: 20 }}>Finished jobs. Re-post the same issue anytime.</p>
          <div style={{ ...card, overflow: 'hidden' }}>
            {trueCompleted.length === 0 ? (
              <div style={{ padding: '60px 40px', textAlign: 'center', color: INK4, fontSize: 14 }}>No completed jobs yet.</div>
            ) : trueCompleted.map((job, i) => {
              const u = URGENCY[job.urgency];
              return (
                <div key={job.id} style={{ padding: '18px 22px', borderBottom: i < trueCompleted.length - 1 ? `1px solid ${CREAM2}` : 'none', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 5, alignItems: 'center' }}>
                      <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 20, color: GREEN, background: GREEN_LIGHT }}>Completed</span>
                      {u && <span style={{ fontSize: 11, color: INK4 }}>{u.label}</span>}
                    </div>
                    <p style={{ fontWeight: 700, color: INK, fontSize: 14 }}>{job.title}</p>
                    <p style={{ fontSize: 12, color: INK4, marginTop: 3 }}>{job.suburb}, {job.state}{job.completed_at && `  |  Completed ${fmt(job.completed_at)}`}</p>
                  </div>
                  <button onClick={() => handleRepost(job)} style={{ padding: '8px 14px', borderRadius: 10, background: GREEN_LIGHT, border: '1px solid rgba(46,125,90,.2)', color: GREEN, fontWeight: 700, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
                    Same issue
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  if (isLoading) return <DashboardSkeleton />;

  // ═══ MAIN DASHBOARD ════════════════════════════════════════════════════════
  return (
    <div style={{ background: CREAM, minHeight: '100vh', display: 'flex', flexDirection: 'column', overflowX: 'hidden', maxWidth: '100%' }}>

      {/* ── Modals ── */}
      {selectedQuote && <QuoteModal quote={selectedQuote} onClose={() => setSelectedQuote(null)} onAction={handleQuoteAction} />}
      {disputeModalJobId && (
        <DisputeModal
          jobId={disputeModalJobId}
          onClose={() => setDisputeModalJobId(null)}
          onSubmitted={() => { setDisputeModalJobId(null); loadData(); }}
        />
      )}
      {reviewModalJobId && (() => {
        const job = jobs.find(j => j.id === reviewModalJobId);
        const acceptedQuote = (quotesByJob[reviewModalJobId] || []).find(q => q.status === 'accepted');
        if (!job) return null;
        return (
          <ReviewSubmissionModal
            jobId={reviewModalJobId}
            jobTitle={job.title}
            tradieName={acceptedQuote?.tradie_name}
            onClose={() => setReviewModalJobId(null)}
            onSubmitted={() => loadData()}
          />
        );
      })()}

      {/* ── Top bar ── */}
      <div style={{
        background: '#fff', borderBottom: `1px solid ${BORDER}`,
        padding: isMobile ? '10px 14px' : '14px 28px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 8, position: 'sticky', top: 0, zIndex: 10, flexShrink: 0,
        width: '100%', maxWidth: '100%',
      }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 800, color: INK, lineHeight: 1.2 }}>Good day, {firstName}</h1>
          <p style={{ fontSize: 12, color: INK4, marginTop: 2 }}>Here's everything happening with your jobs</p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          {/* ── NEW: action-needed alert badge ── */}
          {actionNeededJobs.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 10, background: ROSE_LIGHT, border: `1px solid ${ROSE}30`, color: ROSE, fontWeight: 700, fontSize: 13 }}>
              <AlertTriangle size={14} />
              {actionNeededJobs.length} job{actionNeededJobs.length > 1 ? 's' : ''} need action
            </div>
          )}
          {pendingQuotes.length > 0 && actionNeededJobs.length === 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 10, background: TERRA_LIGHT, border: '1px solid rgba(212,170,58,.25)', color: TERRA, fontWeight: 700, fontSize: 13 }}>
              <Bell size={14} />
              {pendingQuotes.length} quote{pendingQuotes.length > 1 ? 's' : ''} waiting
            </div>
          )}
          <button onClick={() => router.push('/book')} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '10px 20px', borderRadius: 12, background: TERRA, color: '#fff', fontWeight: 700, fontSize: 13, border: 'none', cursor: 'pointer', boxShadow: '0 4px 16px rgba(212,170,58,.3)' }}>
            <Plus size={14} /> Post a Job
          </button>
        </div>
      </div>

      {error && (
        <div style={{ margin: '14px 28px 0', display: 'flex', alignItems: 'center', gap: 10, background: ROSE_LIGHT, border: `1px solid ${ROSE}30`, color: ROSE, padding: '12px 16px', borderRadius: 12, fontSize: 14 }}>
          <AlertCircle size={18} style={{ flexShrink: 0 }} /> {error}
        </div>
      )}

      {/* ── Content grid ── */}
      <div style={{
        flex: 1, padding: isMobile ? '12px 14px' : '20px 28px',
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : '300px 1fr',
        gap: isMobile ? 12 : 20, alignContent: 'start',
        width: '100%', maxWidth: '100%', overflowX: 'hidden',
      }}>
        <div style={{ gridColumn: '1 / -1' }}><DraftBanner /></div>

        {/* LEFT: Job list */}
        <div style={{ ...card, alignSelf: 'start' }}>
          <div style={{ padding: '14px 16px', borderBottom: `1px solid ${BORDER}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <p style={{ fontWeight: 700, fontSize: 14, color: INK }}>Your Jobs</p>
              <p style={{ fontSize: 11, color: INK4, marginTop: 1 }}>{activeJobs.length} active</p>
            </div>
          </div>
          <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 5 }}>
            {jobs.length === 0 ? (
              <div style={{ padding: '32px 16px', textAlign: 'center' }}>
                <div style={{ width: 44, height: 44, borderRadius: 14, background: TERRA_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
                  <Briefcase size={22} color={TERRA} />
                </div>
                <p style={{ fontWeight: 700, fontSize: 13, color: INK, marginBottom: 6 }}>No jobs yet</p>
                <p style={{ fontSize: 12, color: INK4, marginBottom: 14, lineHeight: 1.5 }}>Post your first job to get started.</p>
                <button onClick={() => router.push('/book')} style={{ padding: '8px 16px', borderRadius: 10, background: TERRA, color: '#fff', fontWeight: 700, fontSize: 12, border: 'none', cursor: 'pointer' }}>Post a Job</button>
              </div>
            ) : (
              <>
                {activeJobs.map(job => (
                  <JobCard key={job.id} job={job} selected={selectedJobId === job.id} onClick={() => setSelectedJobId(job.id)} quoteCount={(quotesByJob[job.id] || []).filter(q => q.status === 'pending').length} />
                ))}
                {completedJobs.length > 0 && (
                  <>
                    <div style={{ padding: '8px 8px 4px', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.08em', color: INK4 }}>Completed</div>
                    {completedJobs.slice(0, 3).map(job => (
                      <JobCard key={job.id} job={job} selected={selectedJobId === job.id} onClick={() => setSelectedJobId(job.id)} quoteCount={0} />
                    ))}
                  </>
                )}
              </>
            )}
          </div>
        </div>

        {/* RIGHT: Job detail */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {selectedJob ? (
            <>
              {/* ① Job hero */}
              <div style={{ background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 20, padding: 26, position: 'relative', overflow: 'hidden' }}>
                <div style={{ position: 'absolute', top: -60, right: -60, width: 200, height: 200, borderRadius: '50%', background: 'radial-gradient(circle, rgba(212,170,58,.08), transparent)', pointerEvents: 'none' }} />
                {(() => {
                  const s = STATUS[selectedJob.status] || STATUS.open;
                  const u = URGENCY[selectedJob.urgency];
                  return (
                    <>
                      <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 10, fontWeight: 700, padding: '4px 10px', borderRadius: 20, color: s.color, background: s.bg }}>{s.label}</span>
                        {u && <span style={{ fontSize: 10, fontWeight: 700, padding: '4px 10px', borderRadius: 20, color: INK4, background: CREAM2 }}>{u.label}</span>}
                      </div>
                      <h2 style={{ fontSize: 24, fontWeight: 800, color: INK, lineHeight: 1.2, marginBottom: 12 }}>{selectedJob.title}</h2>
                      <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap' }}>
                        <span style={{ fontSize: 12, color: INK4, display: 'flex', alignItems: 'center', gap: 5 }}><MapPin size={12} /> {selectedJob.suburb}, {selectedJob.state}</span>
                        <span style={{ fontSize: 12, color: INK4, display: 'flex', alignItems: 'center', gap: 5 }}><Calendar size={12} /> Posted {fmt(selectedJob.created_at || selectedJob.created)}</span>
                        {jobPending.length > 0 && <span style={{ fontSize: 12, color: TERRA, fontWeight: 700 }}> |  {jobPending.length} quote{jobPending.length > 1 ? 's' : ''} waiting</span>}
                      </div>
                      {jobPending.length > 0 && (
                        <button onClick={() => setSelectedQuote(jobPending[0])} style={{ marginTop: 18, display: 'inline-flex', alignItems: 'center', gap: 8, padding: '11px 22px', borderRadius: 12, background: TERRA, color: '#fff', fontWeight: 700, fontSize: 13, border: 'none', cursor: 'pointer', boxShadow: '0 4px 12px rgba(212,170,58,.15)' }}>
                          <Eye size={15} />Review {jobPending.length > 1 ? `${jobPending.length} Quotes` : 'Quote'}<ChevronRight size={14} />
                        </button>
                      )}
                    </>
                  );
                })()}
              </div>

              {/* ② Match intelligence */}
              <MatchIntelCard raw={selectedJob.match_intelligence} />

              {/* ③ Redo job banner  -  shown when tradie is returning after dispute */}
              {selectedJob.is_redo_job && ['in_progress', 'completed', 'awaiting_scope_approval'].includes(selectedJob.status) && (
                <RedoJobBanner />
              )}

              {/* ④ NEW: Scope change approval banner */}
              {selectedJob.status === 'awaiting_scope_approval' && (
                <ScopeChangeBanner
                  job={selectedJob}
                  onRespond={approve => handleScopeChangeRespond(selectedJob.id, approve)}
                />
              )}

              {/* ⑤ NEW: Partial stop banner */}
              {selectedJob.status === 'partial_stop' && (
                <PartialStopBanner
                  job={selectedJob}
                  onDispute={() => setDisputeModalJobId(selectedJob.id)}
                  onConfirmComplete={() => handleConfirmComplete(selectedJob.id)}
                />
              )}

              {/* ⑥ NEW: Dispute banner */}
              {selectedJob.status === 'disputed' && <DisputeBanner jobId={selectedJob.id} onResolved={loadData} />}

              {/* ⑦ NEW: Confirm complete (tradie marked done, homeowner hasn't confirmed) */}
              {selectedJob.status === 'completed' && (() => {
                const expiresAt   = selectedJob.dispute_window_expires_at ? new Date(selectedJob.dispute_window_expires_at).getTime() : 0;
                const windowHours = selectedJob.dispute_window_hours ?? 48;
                const canStillDispute = expiresAt > 0 && Date.now() < expiresAt;
                const hoursLeft   = canStillDispute ? Math.max(0, Math.ceil((expiresAt - Date.now()) / (60 * 60 * 1000))) : 0;
                return (
                <div style={{ background: '#fff', border: `1.5px solid ${GREEN}40`, borderRadius: 18, padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                    <div style={{ width: 48, height: 48, borderRadius: 12, flexShrink: 0, background: GREEN_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <CheckCircle2 size={22} color={GREEN} />
                    </div>
                    <div style={{ flex: 1, minWidth: 200 }}>
                      <p style={{ fontWeight: 700, fontSize: 14, color: INK, margin: '0 0 3px' }}>Tradie says the job is done</p>
                      <p style={{ fontSize: 12, color: INK4, lineHeight: 1.5 }}>
                        Confirm to release payment.{' '}
                        {canStillDispute
                          ? <>You have <strong>{hoursLeft}h left</strong> to raise an issue if anything isn't right ({windowHours}h window).</>
                          : <>The dispute window has closed.</>}
                      </p>
                    </div>
                    <div style={{ display: 'flex', gap: 10, flexShrink: 0, flexWrap: 'wrap' }}>
                      <button
                        onClick={() => handleConfirmComplete(selectedJob.id)}
                        disabled={confirmingCompleteJobId === selectedJob.id}
                        style={{ ...btn(GREEN, '#fff'), padding: '11px 18px', borderRadius: 12, opacity: confirmingCompleteJobId === selectedJob.id ? .6 : 1, boxShadow: '0 4px 12px rgba(46,125,90,.2)' }}>
                        {confirmingCompleteJobId === selectedJob.id ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                        {confirmingCompleteJobId === selectedJob.id ? 'Confirming...' : 'Confirm complete'}
                      </button>
                      {canStillDispute && (
                        <button onClick={() => setDisputeModalJobId(selectedJob.id)}
                          style={{ ...btn(ROSE_LIGHT, ROSE), padding: '11px 18px', borderRadius: 12, border: `1px solid ${ROSE}25` }}>
                          <AlertTriangle size={14} /> Something's wrong
                        </button>
                      )}
                    </div>
                  </div>
                  {/* Inline error  -  shows instead of a browser alert that can be blocked */}
                  {confirmError && (
                    <div style={{ background: '#FFF0F0', border: '1px solid #F5A0A0', borderRadius: 10, padding: '10px 14px', fontSize: 12, color: '#A33030', display: 'flex', alignItems: 'center', gap: 8 }}>
                      <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                      <span>{confirmError}</span>
                      <button onClick={() => setConfirmError(null)} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: '#A33030', fontSize: 16, lineHeight: 1 }}>×</button>
                    </div>
                  )}
                </div>
                );
              })()}

              {/* ⑥b: Job confirmed by homeowner  -  awaiting payment release.
                  Report Issue visible only within the dispute window:
                  48h (first dispute) or 10h (re-dispute after resolution). */}
              {selectedJob.status === 'confirmed' && (() => {
                const expiresAt   = selectedJob.dispute_window_expires_at ? new Date(selectedJob.dispute_window_expires_at).getTime() : 0;
                const windowHours = selectedJob.dispute_window_hours ?? 48;
                const canStillDispute = expiresAt > 0 && Date.now() < expiresAt;
                const hoursLeft   = canStillDispute ? Math.max(0, Math.ceil((expiresAt - Date.now()) / (60 * 60 * 1000))) : 0;
                return (
                  <div style={{ background: '#fff', border: `1.5px solid ${GREEN}40`, borderRadius: 18, padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                      <div style={{ width: 48, height: 48, borderRadius: 12, flexShrink: 0, background: GREEN_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <CheckCircle2 size={22} color={GREEN} />
                      </div>
                      <div style={{ flex: 1, minWidth: 200 }}>
                        <p style={{ fontWeight: 700, fontSize: 14, color: INK, margin: '0 0 3px' }}>Job completed  -  thank you!</p>
                        <p style={{ fontSize: 12, color: INK4, lineHeight: 1.5 }}>
                          Great work is done! Leave a review to help other homeowners find great tradies.
                          {canStillDispute && hoursLeft > 0 && (
                            <> If something isn{'’'}t right, you have <strong>{hoursLeft}h left</strong> to report an issue ({windowHours}h window).</>
                          )}
                        </p>
                      </div>
                      {canStillDispute && (
                        <button onClick={() => setDisputeModalJobId(selectedJob.id)}
                          style={{ ...btn(ROSE_LIGHT, ROSE), padding: '10px 16px', borderRadius: 12, border: `1px solid ${ROSE}25`, flexShrink: 0 }}>
                          <AlertTriangle size={14} /> Report an issue
                        </button>
                      )}
                    </div>
                  </div>
                );
              })()}

              {/* ⑦ Waiting for tradie  -  job is in_progress, tradie must mark complete first */}
              {selectedJob.status === 'in_progress' && (
                <div style={{ background: '#fff', border: `1.5px solid ${GREEN}30`, borderRadius: 18, padding: 20, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                  <div style={{ width: 48, height: 48, borderRadius: 12, flexShrink: 0, background: GREEN_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Loader2 size={22} color={GREEN} style={{ animation: 'spin 2s linear infinite' }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 200 }}>
                    <p style={{ fontWeight: 700, fontSize: 14, color: INK }}>Work in progress</p>
                    <p style={{ fontSize: 12, color: INK4, marginTop: 3, lineHeight: 1.5 }}>
                      Your tradie will mark the job complete once finished. You'll then be able to confirm and leave a review.
                    </p>
                  </div>
                </div>
              )}

              {/* ⑧ Review CTA */}
              {(selectedJob.status === 'completed' || selectedJob.status === 'confirmed') && (
                <div style={{ background: '#fff', border: `1.5px solid ${TERRA}40`, borderRadius: 18, padding: 20, display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                  <div style={{ width: 48, height: 48, borderRadius: 12, flexShrink: 0, background: TERRA_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <Star size={22} color={TERRA} fill={TERRA} />
                  </div>
                  {!selectedJob.has_review ? (
                    <>
                      <div style={{ flex: 1, minWidth: 200 }}>
                        <p style={{ fontWeight: 700, fontSize: 14, color: INK }}>Leave a review</p>
                        <p style={{ fontSize: 12, color: INK4, marginTop: 3, lineHeight: 1.5 }}>Help other homeowners  -  share your experience with this tradie.</p>
                      </div>
                      <button onClick={() => setReviewModalJobId(selectedJob.id)} style={{ ...btn(TERRA, '#fff'), padding: '11px 20px', borderRadius: 12, boxShadow: '0 4px 14px rgba(212,170,58,.25)' }}>
                        <Star size={14} /> Write review
                      </button>
                    </>
                  ) : (
                    <div style={{ flex: 1, minWidth: 200 }}>
                      <p style={{ fontWeight: 700, fontSize: 14, color: INK }}>
                        Thank you for your review
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* ⑨ Details + Progress grid */}
              <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 14, width: '100%', minWidth: 0 }}>
                {/* Job details */}
                <div style={{ ...card, padding: isMobile ? 16 : 20, minWidth: 0, overflow: 'hidden' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                    <p style={{ fontWeight: 700, fontSize: 14, color: INK }}>Job Details</p>
                    <FileText size={16} color={INK4} />
                  </div>
                  {editingJobId === selectedJob.id ? (
                    <div style={{ marginBottom: 16 }}>
                      <p style={{ fontSize: 11, fontWeight: 700, color: INK4, marginBottom: 6, textTransform: 'uppercase', letterSpacing: '.06em' }}>Description</p>
                      <textarea value={editDesc} onChange={e => setEditDesc(e.target.value)} rows={4}
                        style={{ width: '100%', padding: '10px 12px', borderRadius: 10, border: `1px solid ${BORDER}`, background: '#fff', color: INK, fontSize: 14, lineHeight: 1.7, resize: 'vertical', fontFamily: 'inherit', outline: 'none', boxSizing: 'border-box' }}
                        placeholder="Describe the job in detail..." />
                    </div>
                  ) : selectedJob.description ? (
                    <p style={{ fontSize: 14, color: INK2, lineHeight: 1.75, marginBottom: 16 }}>{selectedJob.description}</p>
                  ) : (
                    <p style={{ fontSize: 14, color: INK4, marginBottom: 16 }}>No description added</p>
                  )}
                  {/* Photos */}
                  <div style={{ marginBottom: 16 }}>
                    <p style={{ fontSize: 11, fontWeight: 700, color: INK4, marginBottom: 10, textTransform: 'uppercase', letterSpacing: '.06em' }}>
                      Photos {editingJobId === selectedJob.id && <span style={{ color: TERRA, fontWeight: 600 }}> -  tap + to add</span>}
                    </p>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      {(selectedJob.photos || []).map(photo => (
                        <div key={photo.id} style={{ position: 'relative' }}>
                          <img src={photo.url} alt="job photo" style={{ width: 70, height: 70, borderRadius: 10, objectFit: 'cover', border: `1px solid ${BORDER}`, display: 'block' }} />
                          {editingJobId === selectedJob.id && (
                            <button onClick={() => handleRemovePhoto(selectedJob.id, photo.id)} style={{ position: 'absolute', top: -7, right: -7, width: 22, height: 22, borderRadius: '50%', background: ROSE, border: '2px solid #fff', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 800, zIndex: 2 }}>×</button>
                          )}
                        </div>
                      ))}
                      {editingJobId === selectedJob.id && (selectedJob.photos || []).length < 5 && (
                        <label style={{ width: 70, height: 70, borderRadius: 10, border: `2px dashed ${photoUploading ? TERRA : BORDER}`, background: photoUploading ? TERRA_LIGHT : CREAM2, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', cursor: photoUploading ? 'not-allowed' : 'pointer', flexShrink: 0, gap: 3 }}>
                          {photoUploading ? <Loader2 size={20} color={TERRA} className="animate-spin" /> : <><Plus size={20} color={INK3} /><span style={{ fontSize: 9, color: INK4, fontWeight: 600 }}>Add</span></>}
                          <input type="file" accept="image/jpeg,image/png,image/webp,image/heic" disabled={photoUploading} style={{ display: 'none' }} onChange={async e => { const file = e.target.files?.[0]; if (!file) return; await handlePhotoUpload(file, selectedJob.id); e.target.value = ''; }} />
                        </label>
                      )}
                      {(selectedJob.photos || []).length === 0 && editingJobId !== selectedJob.id && (
                        <p style={{ fontSize: 12, color: INK4 }}>No photos added yet</p>
                      )}
                    </div>
                  </div>
                  {/* Before/after photos (from tradie) */}
                  {(selectedJob.photo_before_url || selectedJob.photo_after_url) && (
                    <div style={{ marginBottom: 16 }}>
                      <p style={{ fontSize: 11, fontWeight: 700, color: INK4, marginBottom: 10, textTransform: 'uppercase', letterSpacing: '.06em' }}>Tradie evidence photos</p>
                      <div style={{ display: 'flex', gap: 8 }}>
                        {selectedJob.photo_before_url && (
                          <div style={{ flex: 1 }}>
                            <p style={{ fontSize: 10, color: INK4, marginBottom: 4 }}>Before</p>
                            <img src={selectedJob.photo_before_url} alt="Before" style={{ width: '100%', height: 80, objectFit: 'cover', borderRadius: 8, border: `1px solid ${BORDER}` }} />
                          </div>
                        )}
                        {selectedJob.photo_after_url && (
                          <div style={{ flex: 1 }}>
                            <p style={{ fontSize: 10, color: INK4, marginBottom: 4 }}>After</p>
                            <img src={selectedJob.photo_after_url} alt="After" style={{ width: '100%', height: 80, objectFit: 'cover', borderRadius: 8, border: `1px solid ${BORDER}` }} />
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                  {selectedJob.status === 'open' && (
                    <div style={{ display: 'flex', gap: 8, flexDirection: isMobile ? 'column' : 'row' }}>
                      <button onClick={() => { if (editingJobId === selectedJob.id) { setEditingJobId(null); } else { setEditingJobId(selectedJob.id); setEditDesc(selectedJob.description || ''); } }} style={{ flex: 1, padding: '8px 10px', borderRadius: 10, background: CREAM2, border: `1px solid ${BORDER}`, color: INK2, fontWeight: 600, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}>
                        <Edit3 size={12} />{editingJobId === selectedJob.id ? 'Cancel edit' : 'Edit details'}
                      </button>
                      {editingJobId === selectedJob.id && (
                        <button onClick={() => handleSaveEdit(selectedJob.id)} disabled={editSaving} style={{ flex: 1, padding: '8px 10px', borderRadius: 10, background: TERRA, color: '#fff', border: 'none', fontWeight: 700, fontSize: 12, cursor: 'pointer', opacity: editSaving ? .6 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5 }}>
                          {editSaving ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                          {editSaving ? 'Saving...' : 'Save'}
                        </button>
                      )}
                    </div>
                  )}
                </div>

                {/* Progress card  -  updated with new states */}
                <div style={{ ...card, padding: isMobile ? 16 : 20, minWidth: 0, overflow: 'hidden' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
                    <p style={{ fontWeight: 700, fontSize: 14, color: INK }}>Progress</p>
                    <Activity size={16} color={INK4} />
                  </div>
                  {[
                    {
                      done: true,
                      label: 'Job posted',
                      sub: (() => { const intel = parseMatchIntel(selectedJob.match_intelligence); if (!intel) return 'Tradies notified'; return `${intel.matched} tradie${intel.matched !== 1 ? 's' : ''} notified`; })(),
                      color: TERRA,
                    },
                    {
                      done: jobQuotes.length > 0 || ['hired', 'in_progress', 'awaiting_scope_approval', 'partial_stop', 'disputed', 'completed', 'confirmed'].includes(selectedJob.status),
                      label: 'Quotes received',
                      sub: jobPending.length > 0 ? `${jobPending.length} quote${jobPending.length > 1 ? 's' : ''} ready` : jobQuotes.length > 0 ? 'All quotes reviewed' : 'Waiting for offers',
                      color: AMBER,
                    },
                    {
                      done: ['hired', 'in_progress', 'awaiting_scope_approval', 'partial_stop', 'disputed', 'completed'].includes(selectedJob.status),
                      label: 'Tradie hired',
                      sub: 'Job underway',
                      color: PURPLE,
                    },
                    // ── NEW: scope change step (only shown when relevant) ──
                    ...(selectedJob.status === 'awaiting_scope_approval' ? [{
                      done: false,
                      label: 'Scope change pending',
                      sub: `Respond within ${selectedJob.scope_change_expires_at ? timeUntil(selectedJob.scope_change_expires_at) : ' - '}`,
                      color: AMBER,
                    }] : []),
                    ...(selectedJob.status === 'partial_stop' ? [{
                      done: false,
                      label: 'Work stopped mid-job',
                      sub: 'Admin adjudicating payment',
                      color: ROSE,
                    }] : []),
                    ...(selectedJob.status === 'disputed' ? [{
                      done: false,
                      label: 'Dispute under review',
                      sub: 'Resolution within 2 business days',
                      color: ROSE,
                    }] : []),
                    { done: selectedJob.status === 'completed' || selectedJob.status === 'confirmed', label: 'Job complete', sub: 'Rate your tradie', color: GREEN },
                  ].map((step, i, arr) => (
                    <ProgressStep key={i} {...step} isLast={i === arr.length - 1} />
                  ))}
                </div>
              </div>

              {/* ⑩ Quotes failed to load  -  show retry banner */}
              {jobQuotes.length === 0 && quoteLoadFailedJobIds.has(selectedJob.id) && (
                <div style={{ background: '#fff', border: `1px solid ${ROSE}44`, borderRadius: 16, padding: '18px 22px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                  <div>
                    <p style={{ fontWeight: 700, fontSize: 14, color: ROSE, margin: 0 }}>Could not load quotes</p>
                    <p style={{ fontSize: 12, color: INK4, marginTop: 4 }}>There was a problem fetching quotes for this job.</p>
                  </div>
                  <div>
                    <p style={{ fontWeight: 700, fontSize: 14, color: ROSE, margin: 0 }}>Could not load quotes</p>
                    <p style={{ fontSize: 12, color: INK4, marginTop: 4 }}>There was a problem fetching quotes for this job.</p>
                  </div>
                  <button onClick={loadData} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '9px 16px', borderRadius: 10, background: ROSE_LIGHT, border: `1px solid ${ROSE}44`, color: ROSE, fontWeight: 700, fontSize: 12, cursor: 'pointer' }}>
                    <RefreshCw size={13} /> Retry
                  </button>
                </div>
              )}

              {/* ⑩ Quotes list */}
              {jobQuotes.length > 0 && (
                <div style={{ ...card, overflow: 'hidden', minWidth: 0 }}>
                  <div style={{ padding: isMobile ? '14px 16px' : '14px 20px', borderBottom: `1px solid ${BORDER}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' }}>
                    <div>
                      <p style={{ fontWeight: 700, fontSize: 14, color: INK }}>Quotes for this job</p>
                      <p style={{ fontSize: 11, color: INK4, marginTop: 1 }}>{jobQuotes.length} offer{jobQuotes.length > 1 ? 's' : ''} received</p>
                    </div>
                    {jobPending.length > 0 && <span style={{ fontSize: 11, fontWeight: 700, padding: '4px 12px', borderRadius: 20, background: TERRA_LIGHT, color: TERRA }}>Review needed</span>}
                  </div>
                  {jobQuotes.map((q, i) => {
                    const statusColor = q.status === 'accepted' ? GREEN : q.status === 'rejected' ? ROSE : AMBER;
                    const statusBg = q.status === 'accepted' ? GREEN_LIGHT : q.status === 'rejected' ? ROSE_LIGHT : AMBER_LIGHT;
                    const statusLabel = q.status === 'accepted' ? 'Accepted' : q.status === 'rejected' ? 'Declined' : 'Pending';
                    return (
                      <button key={q.id} onClick={() => setSelectedQuote(q)} style={{ width: '100%', textAlign: 'left', padding: isMobile ? '14px 16px' : '16px 20px', borderBottom: i < jobQuotes.length - 1 ? `1px solid ${CREAM2}` : 'none', background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: isMobile ? 'flex-start' : 'center', gap: 12, flexWrap: isMobile ? 'wrap' : 'nowrap' }}
                        onMouseEnter={e => e.currentTarget.style.background = CREAM2}
                        onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                        <div style={{ width: 44, height: 44, borderRadius: 12, flexShrink: 0, background: `linear-gradient(135deg, ${avatarGrad(q.id)})`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 800, fontSize: 14 }}>
                          {initials(q.tradie_name)}
                        </div>
                        <div style={{ flex: '1 1 150px', minWidth: 0 }}>
                          <p style={{ fontWeight: 600, fontSize: 14, color: INK }}>{q.tradie_name || 'Tradie'}</p>
                          <p style={{ fontSize: 12, color: INK4, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{q.message?.slice(0, 60)}...</p>
                        </div>
                        <div style={{ textAlign: isMobile ? 'left' : 'right', flexShrink: 0, marginLeft: isMobile ? 56 : 0 }}>
                          <p style={{ fontWeight: 800, fontSize: 20, color: INK }}>${(q.amount || 0).toLocaleString()}</p>
                          <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 20, background: statusBg, color: statusColor, display: 'inline-block', marginTop: 4 }}>{statusLabel}</span>
                        </div>
                        {!isMobile && <ChevronRight size={16} color={INK4} style={{ flexShrink: 0 }} />}
                      </button>
                    );
                  })}
                </div>
              )}

              {/* ⑪ Cancel job  -  last */}
              {['open', 'quoted'].includes(selectedJob.status) && (
                <div style={{ background: '#fff', border: `1px solid #F5C0C0`, borderRadius: 16, padding: isMobile ? '16px' : '16px 20px', display: 'flex', flexDirection: isMobile ? 'column' : 'row', alignItems: isMobile ? 'stretch' : 'center', justifyContent: 'space-between', gap: 12, minWidth: 0, overflow: 'hidden' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontWeight: 700, fontSize: 13, color: INK2, marginBottom: 2 }}>Need to cancel this job?</p>
                    <p style={{ fontSize: 12, color: INK4, lineHeight: 1.5 }}>All tradies will be notified immediately. The job moves to your history.</p>
                  </div>
                  <button onClick={() => handleCancelJob(selectedJob.id)} disabled={cancellingJobId === selectedJob.id}
                    style={{ flexShrink: 0, width: isMobile ? '100%' : 'auto', justifyContent: 'center', padding: '9px 16px', borderRadius: 10, background: ROSE_LIGHT, border: `1px solid ${ROSE}30`, color: ROSE, fontWeight: 700, fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, opacity: cancellingJobId === selectedJob.id ? .5 : 1 }}>
                    <Ban size={13} />
                    {cancellingJobId === selectedJob.id ? 'Cancelling...' : 'Cancel job'}
                  </button>
                </div>
              )}
            </>
          ) : (
            <div style={{ ...card, padding: '60px 40px', textAlign: 'center', border: `2px dashed ${BORDER}`, background: 'transparent' }}>
              <div style={{ width: 56, height: 56, borderRadius: 18, background: TERRA_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px' }}>
                <Briefcase size={28} color={TERRA} />
              </div>
              <h3 style={{ fontSize: 20, fontWeight: 800, color: INK, marginBottom: 8 }}>Post a job</h3>
              <p style={{ fontSize: 13, color: INK4, maxWidth: 280, margin: '0 auto 24px', lineHeight: 1.6 }}>Describe what you need and get matched with verified local tradies in minutes.</p>
              <button onClick={() => router.push('/book')} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '12px 28px', borderRadius: 14, background: TERRA, color: '#fff', fontWeight: 700, fontSize: 14, border: 'none', cursor: 'pointer', boxShadow: '0 6px 20px rgba(212,170,58,.3)' }}>
                <Plus size={16} /> Post a Job
              </button>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
function DashboardSkeleton() {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 1024);
    check(); window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);
  return (
    <div style={{ background: CREAM, minHeight: '100vh', padding: isMobile ? '12px 14px' : '20px 28px' }}>
      <div style={{ height: 60, background: '#fff', borderRadius: 16, marginBottom: 20, opacity: .6 }} />
      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '300px 1fr', gap: 20 }}>
        <div style={{ height: isMobile ? 200 : 500, background: '#fff', borderRadius: 18, opacity: .6 }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ height: 200, background: '#fff', borderRadius: 20, opacity: .4 }} />
          <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr', gap: 14 }}>
            <div style={{ height: 220, background: '#fff', borderRadius: 18, opacity: .6 }} />
            {!isMobile && <div style={{ height: 220, background: '#fff', borderRadius: 18, opacity: .6 }} />}
          </div>
        </div>
      </div>
    </div>
  );
}
