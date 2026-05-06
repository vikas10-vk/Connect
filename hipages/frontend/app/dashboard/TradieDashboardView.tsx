"use client";

import React, { useEffect, useState } from 'react';
import {
  Briefcase, Clock, MapPin, Calendar, MessageSquare,
  ChevronRight, Zap, Loader2, AlertCircle, DollarSign,
  ShieldCheck, FileText, XCircle, Lock, CheckCircle2,
  Award, Shield, AlertTriangle, ExternalLink,
} from 'lucide-react';
import api from '@/src/lib/api';
import { useAuth } from '@/src/contexts/AuthContext';
import LeadDetailModal from '@/src/components/LeadDetailModal';

// ── Interfaces ────────────────────────────────────────────────────────────────
interface Lead {
  id: string; job_id: string; job_title: string;
  job_suburb: string; job_state: string; job_description: string;
  job_budget_min?: number; job_budget_max?: number;
  job_urgency?: string; job_type?: string; service_type?: string;
  status: string; sent_at: string; is_urgent: boolean; is_high_value: boolean;
}

interface OnboardingGates {
  profile_approved: boolean; has_verified_cert: boolean;
  has_verified_insurance: boolean; ready_to_receive_jobs: boolean;
}
interface CertSummary {
  id: string; category_name?: string; status: string;
  licence_number: string; issuing_state: string;
  rejection_reason?: string;
}
interface InsuranceSummary {
  id: string; insurance_type: string; insurer_name: string;
  status: string; expires_at: string; coverage_amount_cents: number;
  rejection_reason?: string;
}
interface OnboardingStatusData {
  gates: OnboardingGates;
  certifications: CertSummary[];
  insurance_policies: InsuranceSummary[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────
const INSURANCE_LABELS: Record<string, string> = {
  public_liability: 'Public Liability',
  workers_compensation: "Workers' Compensation",
  professional_indemnity: 'Professional Indemnity',
};
const REJECTION_LABELS: Record<string, string> = {
  invalid_number: 'Number not found in registry',
  expired: 'Licence has lapsed',
  name_mismatch: 'Holder name mismatch',
  cannot_verify: 'Could not verify — resubmit with clearer details',
  insufficient_cover: 'Coverage below required minimum',
  other: 'See rejection note',
};
const fmtCoverage = (cents: number) =>
  `$${(cents / 100).toLocaleString('en-AU', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;

// ── Status configs ────────────────────────────────────────────────────────────
const CERT_BADGE: Record<string, { className: string; label: string }> = {
  pending: { className: 'bg-amber-50 text-amber-700', label: 'Pending review' },
  in_review: { className: 'bg-purple-50 text-purple-700', label: 'In review' },
  verified: { className: 'bg-green-50 text-green-700', label: 'Verified ✓' },
  rejected: { className: 'bg-red-50 text-red-600', label: 'Rejected' },
  expired: { className: 'bg-red-50 text-red-600', label: 'Expired' },
};

const VERIF_CONFIG: Record<string, {
  icon: React.ElementType; title: string; desc: string;
  cardBg: string; cardBorder: string; iconBg: string; iconColor: string;
  textColor: string; subColor: string; badge: string; badgeBg: string; badgeColor: string;
}> = {
  pending_review: {
    icon: Clock, title: 'Application Under Review',
    desc: "We're reviewing your profile. Usually takes 1 business day. You'll get an email when done.",
    cardBg: '#FFFBF2', cardBorder: '#F5D9A0', iconBg: '#FFF3DC', iconColor: '#B85C00',
    textColor: '#7A3C00', subColor: '#9A5C00', badge: 'Pending', badgeBg: '#FFF3DC', badgeColor: '#B85C00',
  },
  needs_documents: {
    icon: FileText, title: 'Documents Required',
    desc: 'We need more information. Check your email for details on what to provide.',
    cardBg: '#F0F8FF', cardBorder: '#B0D4F5', iconBg: '#E0F0FF', iconColor: '#0077AA',
    textColor: '#004D7A', subColor: '#0077AA', badge: 'Action Needed', badgeBg: '#E0F0FF', badgeColor: '#0077AA',
  },
  approved: {
    icon: ShieldCheck, title: 'Verified & Active',
    desc: "Your profile is live. You're set up to receive leads. Keep your availability current.",
    cardBg: '#F2FBF6', cardBorder: '#A0D9BC', iconBg: '#E0F5EC', iconColor: '#2E7D5A',
    textColor: '#1B5E3A', subColor: '#2E7D5A', badge: 'Verified', badgeBg: '#E0F5EC', badgeColor: '#2E7D5A',
  },
  rejected: {
    icon: XCircle, title: 'Application Not Approved',
    desc: "We couldn't approve your application. Check your email or contact support.",
    cardBg: '#FFF8F8', cardBorder: '#F5C0C0', iconBg: '#FFE8E8', iconColor: '#A33030',
    textColor: '#7A1A1A', subColor: '#A33030', badge: 'Not Approved', badgeBg: '#FFE8E8', badgeColor: '#A33030',
  },
  suspended: {
    icon: Lock, title: 'Account Suspended',
    desc: 'Your account is suspended. Check your email and reply to appeal.',
    cardBg: '#FFF8F8', cardBorder: '#F5C0C0', iconBg: '#FFE8E8', iconColor: '#A33030',
    textColor: '#7A1A1A', subColor: '#A33030', badge: 'Suspended', badgeBg: '#FFE8E8', badgeColor: '#A33030',
  },
};

// ─── Enhanced Verification Card ───────────────────────────────────────────────
function VerificationCard({ status }: { status: string }) {
  const cfg = VERIF_CONFIG[status] || VERIF_CONFIG['pending_review'];
  const Icon = cfg.icon;
  const [data, setData] = useState<OnboardingStatusData | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.get('/tradies/onboarding/status')
      .then(r => setData(r.data))
      .catch(() => { })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{ background: cfg.cardBg, border: `1.5px solid ${cfg.cardBorder}`, borderRadius: '1.75rem', padding: '1.75rem', position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: -40, right: -40, width: 140, height: 140, borderRadius: '50%', background: `${cfg.iconColor}18`, pointerEvents: 'none' }} />

      {/* ── Header ── */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.875rem', position: 'relative', zIndex: 1 }}>
        <div style={{ width: 44, height: 44, borderRadius: '0.875rem', flexShrink: 0, background: cfg.iconBg, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon style={{ width: 22, height: 22, color: cfg.iconColor }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
            <h3 style={{ margin: 0, fontSize: 15, fontWeight: 700, color: cfg.textColor }}>{cfg.title}</h3>
            <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 20, background: cfg.badgeBg, color: cfg.badgeColor }}>{cfg.badge}</span>
          </div>
          <p style={{ margin: 0, fontSize: 13, lineHeight: 1.6, color: cfg.subColor }}>{cfg.desc}</p>
        </div>
      </div>

      {/* ── Gates progress ── */}
      {data && (
        <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: `1px solid ${cfg.cardBorder}`, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {/* Ready banner */}
          {data.gates.ready_to_receive_jobs ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: '#E0F5EC', borderRadius: 10, border: '1px solid #A0D9BC' }}>
              <CheckCircle2 style={{ width: 16, height: 16, color: '#2E7D5A', flexShrink: 0 }} />
              <span style={{ fontSize: 13, fontWeight: 700, color: '#1B5E3A' }}>You&apos;re live — receiving job leads</span>
            </div>
          ) : (
            /* Individual gate checks */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { label: 'Profile approved', done: data.gates.profile_approved },
                { label: 'Trade licence verified', done: data.gates.has_verified_cert },
                { label: 'Insurance verified', done: data.gates.has_verified_insurance },
              ].map(gate => (
                <div key={gate.label} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0, background: gate.done ? '#2E7D5A' : '#E8E2D4', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {gate.done
                      ? <CheckCircle2 style={{ width: 11, height: 11, color: 'white' }} />
                      : <span style={{ fontSize: 9, color: '#8A8882' }}>○</span>}
                  </div>
                  <span style={{ fontSize: 12.5, color: gate.done ? '#1B5E3A' : '#7A6558', fontWeight: gate.done ? 600 : 400 }}>{gate.label}</span>
                </div>
              ))}
            </div>
          )}

          {/* Cert status summary */}
          {data.certifications.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <p style={{ fontSize: 10, fontWeight: 700, color: cfg.textColor, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 8px', opacity: 0.7 }}>Licences</p>
              {data.certifications.slice(0, 3).map(cert => {
                const badge = CERT_BADGE[cert.status] || { className: 'bg-gray-50 text-gray-500', label: cert.status };
                return (
                  <div key={cert.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0', borderBottom: `1px solid ${cfg.cardBorder}` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Award style={{ width: 12, height: 12, color: cfg.iconColor, flexShrink: 0 }} />
                      <span style={{ fontSize: 12.5, color: cfg.textColor, fontWeight: 500 }}>
                        {cert.category_name || 'Trade'} · <span style={{ fontFamily: 'monospace', fontSize: 11.5 }}>{cert.licence_number}</span> · {cert.issuing_state}
                      </span>
                    </div>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badge.className}`}>{badge.label}</span>
                  </div>
                );
              })}
              {data.certifications.length > 3 && (
                <p style={{ fontSize: 11.5, color: cfg.subColor, margin: '6px 0 0', opacity: 0.7 }}>+{data.certifications.length - 3} more licence{data.certifications.length - 3 > 1 ? 's' : ''}</p>
              )}
            </div>
          )}

          {/* Insurance summary */}
          {data.insurance_policies.length > 0 && (
            <div style={{ marginTop: 4 }}>
              <p style={{ fontSize: 10, fontWeight: 700, color: cfg.textColor, textTransform: 'uppercase', letterSpacing: '0.1em', margin: '0 0 8px', opacity: 0.7 }}>Insurance</p>
              {data.insurance_policies.filter(p => p.insurance_type === 'public_liability').slice(0, 1).map(policy => {
                const badge = CERT_BADGE[policy.status] || { className: 'bg-gray-50 text-gray-500', label: policy.status };
                return (
                  <div key={policy.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Shield style={{ width: 12, height: 12, color: cfg.iconColor, flexShrink: 0 }} />
                      <span style={{ fontSize: 12.5, color: cfg.textColor, fontWeight: 500 }}>
                        {INSURANCE_LABELS[policy.insurance_type]} · {policy.insurer_name} · {fmtCoverage(policy.coverage_amount_cents)}
                      </span>
                    </div>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${badge.className}`}>{badge.label}</span>
                  </div>
                );
              })}
            </div>
          )}

          {/* No certs/insurance warnings */}
          {data.certifications.length === 0 && !data.gates.has_verified_cert && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#FFF3DC', borderRadius: 8, border: '1px solid #F5D9A0' }}>
              <Award style={{ width: 14, height: 14, color: '#B85C00', flexShrink: 0 }} />
              <span style={{ fontSize: 12.5, color: '#7A3C00' }}>No trade licences submitted. Submit via the Verification tab.</span>
            </div>
          )}
          {data.insurance_policies.length === 0 && !data.gates.has_verified_insurance && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', background: '#FFF3DC', borderRadius: 8, border: '1px solid #F5D9A0' }}>
              <Shield style={{ width: 14, height: 14, color: '#B85C00', flexShrink: 0 }} />
              <span style={{ fontSize: 12.5, color: '#7A3C00' }}>No insurance submitted. Submit via the Verification tab.</span>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div style={{ marginTop: '1rem', paddingTop: '0.875rem', borderTop: `1px solid ${cfg.cardBorder}`, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Loader2 style={{ width: 13, height: 13, color: cfg.iconColor }} className="animate-spin" />
          <span style={{ fontSize: 12.5, color: cfg.subColor }}>Loading licence & insurance status…</span>
        </div>
      )}

      {/* ── CTA for non-approved ── */}
      {status !== 'approved' && (
        <div style={{ marginTop: '1rem', paddingTop: '0.875rem', borderTop: `1px solid ${cfg.cardBorder}` }}>
          <a href="mailto:support@proconnect.com.au" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 700, color: cfg.iconColor, textDecoration: 'none' }}>
            <MessageSquare style={{ width: 14, height: 14 }} />
            {status === 'needs_documents' ? 'Reply to our email with your documents' : 'Contact support'}
            <ChevronRight style={{ width: 13, height: 13, opacity: 0.6 }} />
          </a>
        </div>
      )}
    </div>
  );
}

// ─── Main dashboard view ──────────────────────────────────────────────────────
export default function TradieDashboardView() {
  const { user, tradieProfile } = useAuth();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);

  const verificationStatus: string =
    (tradieProfile as any)?.verification_status ||
    (tradieProfile as any)?.verificationStatus ||
    'pending_review';

  const loadLeads = async () => {
    if (!user) return;
    setIsLoading(true); setError(null);
    try {
      const res = await api.get('/leads/my-leads');
      setLeads(res.data || []);
    } catch {
      setError('Failed to load leads. Please refresh.');
    } finally { setIsLoading(false); }
  };

  useEffect(() => { loadLeads(); }, []);

  const newLeads = leads.filter(l => l.status === 'new' || l.status === 'sent');
  const quotedLeads = leads.filter(l => l.status === 'quoted');

  return (
    <div className="space-y-10">
      {selectedLead && (
        <LeadDetailModal
          lead={selectedLead}
          onClose={() => setSelectedLead(null)}
          onQuoteSubmitted={() => { setSelectedLead(null); loadLeads(); }}
        />
      )}

      <header className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
        <div className="space-y-1">
          <h1 className="text-4xl font-black tracking-tight text-gray-900">Tradie Dashboard</h1>
          <p className="text-gray-500 font-medium text-lg">Welcome back, {user?.name?.split(' ')[0] || 'Tradie'}.</p>
        </div>
        {verificationStatus === 'approved' && (
          <div className="flex items-center gap-3 bg-white px-4 py-2 rounded-2xl border border-gray-100 shadow-sm">
            <div className="relative">
              <div className="w-2.5 h-2.5 rounded-full bg-green-500 animate-ping absolute inset-0" />
              <div className="w-2.5 h-2.5 rounded-full bg-green-500 relative z-10" />
            </div>
            <span className="text-xs font-bold text-gray-700 uppercase tracking-widest">Accepting New Jobs</span>
          </div>
        )}
      </header>

      {error && (
        <div className="flex items-center gap-3 bg-red-50 border border-red-100 text-red-700 px-5 py-4 rounded-2xl text-sm">
          <AlertCircle className="w-5 h-5 shrink-0" /> {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left column */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-[2.5rem] p-8 shadow-sm border border-gray-100 space-y-6">
            <h3 className="text-xl font-bold text-gray-900">Business Stats</h3>
            {isLoading ? (
              <div className="flex items-center justify-center py-8"><Loader2 className="w-6 h-6 text-brand-terracotta animate-spin" /></div>
            ) : (
              <div className="grid grid-cols-2 gap-4">
                {[
                  { label: 'New Leads', value: newLeads.length, color: 'text-brand-terracotta' },
                  { label: 'Quotes Sent', value: quotedLeads.length, color: 'text-brand-terracotta' },
                  { label: 'Active Jobs', value: 0, color: 'text-gray-700' },
                  { label: 'Rating', value: (tradieProfile as any)?.rating || '—', color: 'text-yellow-500' },
                ].map(s => (
                  <div key={s.label} className="bg-brand-cream/50 p-5 rounded-3xl space-y-1">
                    <p className="text-xs font-bold text-gray-400 uppercase tracking-widest">{s.label}</p>
                    <p className={`text-3xl font-black ${s.color}`}>{s.value}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
          <VerificationCard status={verificationStatus} />
        </div>

        {/* Right column */}
        <div className="lg:col-span-2 space-y-8">
          {verificationStatus !== 'approved' && !isLoading && (
            <div className="bg-white rounded-[2rem] border border-gray-100 shadow-sm p-8 text-center">
              <div className="w-14 h-14 rounded-2xl bg-brand-cream flex items-center justify-center mx-auto mb-4">
                <Zap className="w-7 h-7 text-brand-terracotta" />
              </div>
              <h4 className="font-bold text-gray-900 mb-2">Leads will appear here once you&apos;re verified</h4>
              <p className="text-gray-500 text-sm max-w-xs mx-auto leading-relaxed">
                Our team is reviewing your application. Once approved, job leads matching your skills and location will show up right here.
              </p>
            </div>
          )}

          {verificationStatus === 'approved' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center px-1">
                <h3 className="text-2xl font-bold text-gray-900">Available Leads</h3>
              </div>
              {isLoading ? (
                <div className="bg-white rounded-[2.5rem] p-12 flex items-center justify-center border border-gray-100">
                  <Loader2 className="w-6 h-6 text-brand-terracotta animate-spin" />
                </div>
              ) : leads.length === 0 ? (
                <div className="bg-white rounded-[2.5rem] p-12 text-center border border-gray-100 shadow-sm">
                  <div className="w-14 h-14 bg-brand-cream rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <Zap className="w-7 h-7 text-brand-terracotta" />
                  </div>
                  <h4 className="font-bold text-gray-900 mb-2">No leads available</h4>
                  <p className="text-gray-500 text-sm max-w-xs mx-auto">We&apos;ll notify you as soon as new jobs matching your skills are posted.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {leads.map(lead => {
                    const isQuoted = lead.status === 'quoted';
                    return (
                      <div key={lead.id} className="bg-white p-6 rounded-[2rem] shadow-sm border border-gray-100 hover:shadow-md hover:border-brand-terracotta/10 transition-all">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap mb-2">
                              <span className={`text-xs font-bold px-3 py-1 rounded-full ${isQuoted ? 'bg-green-50 text-green-700' : 'bg-blue-50 text-blue-600'}`}>
                                {isQuoted ? 'Quoted' : 'New Lead'}
                              </span>
                              {lead.is_urgent && <span className="text-xs font-bold px-3 py-1 rounded-full bg-red-50 text-red-600">🚨 Urgent</span>}
                              {lead.is_high_value && <span className="text-xs font-bold px-3 py-1 rounded-full bg-yellow-50 text-yellow-700">💰 High Value</span>}
                            </div>
                            <h4 className="font-bold text-gray-900 text-base truncate">{lead.job_title}</h4>
                            <div className="flex items-center gap-4 mt-1.5 flex-wrap">
                              <span className="flex items-center gap-1 text-xs text-gray-500"><MapPin className="w-3 h-3" />{lead.job_suburb}, {lead.job_state}</span>
                              <span className="flex items-center gap-1 text-xs text-gray-500">
                                <Calendar className="w-3 h-3" />{new Date(lead.sent_at).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })}
                              </span>
                              {(lead.job_budget_min || lead.job_budget_max) && (
                                <span className="flex items-center gap-1 text-xs text-gray-500">
                                  <DollarSign className="w-3 h-3" />
                                  {lead.job_budget_max ? `Up to $${lead.job_budget_max.toLocaleString()}` : `From $${lead.job_budget_min?.toLocaleString()}`}
                                </span>
                              )}
                            </div>
                            {lead.job_description && (
                              <p className="text-xs text-gray-400 mt-2 leading-relaxed" style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                {lead.job_description}
                              </p>
                            )}
                          </div>
                          <div className="shrink-0">
                            {isQuoted ? (
                              <button onClick={() => setSelectedLead(lead)}
                                className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl font-bold text-sm border border-green-200 bg-green-50 text-green-700 hover:bg-green-100 transition-all">
                                <CheckCircle2 className="w-4 h-4" /> Quoted
                              </button>
                            ) : (
                              <button onClick={() => setSelectedLead(lead)}
                                className="bg-brand-terracotta text-white px-5 py-2.5 rounded-xl font-bold text-sm hover:shadow-lg hover:shadow-brand-terracotta/20 transition-all">
                                View & Quote
                              </button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
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
