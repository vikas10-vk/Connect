"use client";

import React, { useEffect, useState } from 'react';
import {
    X, MapPin, Calendar, Clock, Zap, DollarSign,
    Loader2, CheckCircle2, AlertCircle, ImageIcon,
    Users, TrendingUp, Send, ChevronDown,
} from 'lucide-react';
import api from '@/src/lib/api';

// ── Palette (matches tradie dashboard) ───────────────────────────────────────
const CREAM = '#FDFAF5';
const CREAM2 = '#F5F0E8';
const TERRA = '#C5563A';
const TERRA_LIGHT = '#F5EDE9';
const INK = '#2C1A0E';
const INK2 = '#4A3728';
const INK3 = '#7A6558';
const INK4 = '#A89080';
const BORDER = '#E8E0D0';
const GREEN = '#2E7D5A';
const GREEN_LIGHT = '#E8F5EE';
const AMBER = '#B85C00';
const AMBER_LIGHT = '#FFF3E0';

// ── Types ────────────────────────────────────────────────────────────────────

interface Lead {
    id: string;
    job_id: string;
    job_title?: string;
    job_suburb?: string;
    job_state?: string;
    job_description?: string;
    job_budget_min?: number;
    job_budget_max?: number;
    job_urgency?: string;
    job_type?: string;
    service_type?: string;
    status: string;
    sent_at: string;
    is_urgent?: boolean;
    is_high_value?: boolean;
}

interface JobDetail {
    id: string;
    title: string;
    description?: string;
    suburb?: string;
    state?: string;
    urgency?: string;
    job_type?: string;
    service_type?: string;
    budget_min?: number;
    budget_max?: number;
    created_at: string;
    status: string;
}

interface Photo { id: string; url: string; file_key: string; }

interface Competition {
    quote_count: number;
    competition_level: 'none' | 'low' | 'medium' | 'high';
    message: string;
}

interface ExistingQuote {
    id: string;
    amount: number;
    message: string;
    status: string;
    created_at: string;
}

interface Props {
    lead: Lead;
    onClose: () => void;
    onQuoteSubmitted: () => void;
}

// ── Urgency labels ────────────────────────────────────────────────────────────
const URGENCY: Record<string, { label: string; color: string }> = {
    emergency: { label: 'Emergency', color: '#A33030' },
    asap: { label: 'ASAP', color: '#B85C00' },
    today: { label: 'Today', color: '#B85C00' },
    next_few_days: { label: 'This week', color: '#0077AA' },
    next_few_weeks: { label: 'Next few weeks', color: '#2E7D5A' },
    next_few_months: { label: 'Planning', color: '#7A6558' },
    flexible: { label: 'Flexible', color: '#2E7D5A' },
};

const COMPETITION_CONFIG = {
    none: { label: 'No quotes yet', color: GREEN, bg: GREEN_LIGHT, bar: 0 },
    low: { label: 'Low competition', color: GREEN, bg: GREEN_LIGHT, bar: 25 },
    medium: { label: 'Competitive', color: AMBER, bg: AMBER_LIGHT, bar: 60 },
    high: { label: 'High competition', color: '#A33030', bg: '#FFEBEB', bar: 90 },
};

const SERVICE_TYPE_LABELS: Record<string, string> = {
    new_installation: 'New Installation',
    repair: 'Repair',
    replace: 'Replace / Upgrade',
    other: 'Other',
};

const fmt = (d: string) => {
    try { return new Date(d).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' }); }
    catch { return d; }
};

// ── Main component ────────────────────────────────────────────────────────────

export default function LeadDetailModal({ lead, onClose, onQuoteSubmitted }: Props) {
    const [job, setJob] = useState<JobDetail | null>(null);
    const [photos, setPhotos] = useState<Photo[]>([]);
    const [competition, setCompetition] = useState<Competition | null>(null);
    const [existing, setExisting] = useState<ExistingQuote | null>(null);
    const [loading, setLoading] = useState(true);

    // Quote form
    const [amount, setAmount] = useState('');
    const [message, setMessage] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [submitted, setSubmitted] = useState(false);

    // Photo lightbox
    const [lightbox, setLightbox] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const load = async () => {
            setLoading(true);
            try {
                const [jobRes, photosRes, compRes, quoteRes] = await Promise.allSettled([
                    api.get(`/jobs/${lead.job_id}`),
                    api.get(`/jobs/${lead.job_id}/photos`),
                    api.get(`/jobs/${lead.job_id}/competition`),
                    api.get(`/quotes/my-quote/${lead.id}`),
                ]);

                if (cancelled) return;

                if (jobRes.status === 'fulfilled') setJob(jobRes.value.data);
                if (photosRes.status === 'fulfilled') setPhotos(photosRes.value.data || []);
                if (compRes.status === 'fulfilled') setCompetition(compRes.value.data);
                if (quoteRes.status === 'fulfilled') setExisting(quoteRes.value.data);
            } catch { /* silent */ }
            finally { if (!cancelled) setLoading(false); }
        };

        load();
        return () => { cancelled = true; };
    }, [lead.job_id, lead.id]);

    const handleSubmit = async () => {
        const parsed = parseFloat(amount);
        if (!parsed || parsed <= 0) { setSubmitError('Please enter a valid quote amount.'); return; }
        if (message.trim().length < 20) { setSubmitError('Please write at least 20 characters in your message.'); return; }

        setSubmitting(true);
        setSubmitError(null);
        try {
            await api.post('/quotes/', {
                lead_id: lead.id,
                amount: parsed,
                message: message.trim(),
            });
            setSubmitted(true);
            setTimeout(() => {
                onQuoteSubmitted();
                onClose();
            }, 1600);
        } catch (err: any) {
            const msg = err?.response?.data?.error?.message || err?.response?.data?.detail;
            setSubmitError(typeof msg === 'string' ? msg : 'Could not send quote. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    const urgency = URGENCY[job?.urgency || lead.job_urgency || 'flexible'];
    const comp = competition ? COMPETITION_CONFIG[competition.competition_level] : null;
    const alreadyQuoted = !!existing || lead.status === 'quoted';

    // ── Lightbox ───────────────────────────────────────────────────
    if (lightbox) {
        return (
            <div onClick={() => setLightbox(null)}
                style={{
                    position: 'fixed', inset: 0, zIndex: 300, background: 'rgba(0,0,0,0.9)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                <img src={lightbox} alt="Job photo" style={{ maxWidth: '90vw', maxHeight: '90vh', borderRadius: 8 }} />
                <button onClick={() => setLightbox(null)} style={{
                    position: 'absolute', top: 16, right: 16, width: 36, height: 36,
                    borderRadius: '50%', background: 'rgba(255,255,255,0.15)', border: 'none',
                    cursor: 'pointer', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                    <X size={18} />
                </button>
            </div>
        );
    }

    // ── Success state ──────────────────────────────────────────────
    if (submitted) {
        return (
            <div onClick={onClose} style={{
                position: 'fixed', inset: 0, zIndex: 200, display: 'flex', alignItems: 'center',
                justifyContent: 'center', padding: 16, background: 'rgba(30,16,6,0.55)', backdropFilter: 'blur(6px)',
            }}>
                <div onClick={e => e.stopPropagation()} style={{
                    width: '100%', maxWidth: 380, background: '#fff', borderRadius: 24,
                    padding: '40px 28px', textAlign: 'center', border: `1px solid ${BORDER}`,
                }}>
                    <div style={{
                        width: 64, height: 64, borderRadius: 20, margin: '0 auto 16px',
                        background: GREEN_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <CheckCircle2 size={34} color={GREEN} strokeWidth={2} />
                    </div>
                    <h3 style={{ fontSize: 20, fontWeight: 800, color: INK, marginBottom: 8 }}>Quote sent!</h3>
                    <p style={{ fontSize: 14, color: INK4, lineHeight: 1.6 }}>
                        The homeowner has been notified. You'll hear back if they accept.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <>
            {/* Backdrop */}
            <div onClick={onClose} style={{
                position: 'fixed', inset: 0, zIndex: 200,
                background: 'rgba(30,16,6,0.55)', backdropFilter: 'blur(6px)',
            }} />

            {/* Sheet */}
            <div style={{
                position: 'fixed', zIndex: 201,
                // Mobile: full-screen bottom sheet. Desktop: centred modal.
                bottom: 0, left: 0, right: 0,
                maxHeight: '92vh',
                background: '#fff',
                borderTopLeftRadius: 24, borderTopRightRadius: 24,
                overflowY: 'auto',
                boxShadow: '0 -16px 60px rgba(44,26,14,.18)',
                display: 'flex', flexDirection: 'column',
            }}>
                <style>{`
          @media (min-width: 768px) {
            .ldm-shell {
              top: 50% !important; left: 50% !important; bottom: auto !important;
              right: auto !important; transform: translate(-50%,-50%) !important;
              width: 580px !important; border-radius: 24px !important;
              max-height: 88vh !important;
            }
          }
        `}</style>

                {/* ── Header ──────────────────────────────────────────── */}
                <div style={{
                    padding: '18px 20px 14px', position: 'sticky', top: 0, zIndex: 5,
                    background: '#fff', borderBottom: `1px solid ${CREAM2}`,
                    display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12,
                }}>
                    <div style={{ minWidth: 0 }}>
                        <p style={{
                            fontSize: 10, fontWeight: 700, letterSpacing: '.1em',
                            textTransform: 'uppercase', color: INK4, marginBottom: 4,
                        }}>
                            Job Lead
                        </p>
                        <h2 style={{
                            fontSize: 19, fontWeight: 800, color: INK, lineHeight: 1.25,
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                            maxWidth: 'calc(100% - 10px)',
                        }}>
                            {lead.job_title || job?.title || 'Job Details'}
                        </h2>
                    </div>
                    <button onClick={onClose} style={{
                        flexShrink: 0, width: 32, height: 32, borderRadius: 10,
                        background: CREAM2, border: 'none', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', color: INK4,
                    }}>
                        <X size={15} />
                    </button>
                </div>

                {/* ── Body ────────────────────────────────────────────── */}
                <div style={{ padding: '20px 20px 100px', flex: 1 }}>
                    {loading ? (
                        <div style={{ padding: '60px 0', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <Loader2 size={28} color={TERRA} className="animate-spin" />
                        </div>
                    ) : (
                        <>
                            {/* Location + Date + Urgency badges */}
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
                                {(lead.job_suburb || job?.suburb) && (
                                    <span style={{
                                        display: 'inline-flex', alignItems: 'center', gap: 5,
                                        padding: '5px 10px', borderRadius: 20, background: CREAM2,
                                        fontSize: 12, fontWeight: 600, color: INK2,
                                    }}>
                                        <MapPin size={12} color={TERRA} />
                                        {lead.job_suburb || job?.suburb}, {lead.job_state || job?.state}
                                    </span>
                                )}
                                {urgency && (
                                    <span style={{
                                        display: 'inline-flex', alignItems: 'center', gap: 5,
                                        padding: '5px 10px', borderRadius: 20,
                                        background: `${urgency.color}15`,
                                        fontSize: 12, fontWeight: 700, color: urgency.color,
                                    }}>
                                        {urgency.label}
                                    </span>
                                )}
                                {job?.created_at && (
                                    <span style={{
                                        display: 'inline-flex', alignItems: 'center', gap: 5,
                                        padding: '5px 10px', borderRadius: 20, background: CREAM2,
                                        fontSize: 12, color: INK4,
                                    }}>
                                        <Calendar size={12} /> Posted {fmt(job.created_at)}
                                    </span>
                                )}
                            </div>

                            {/* Description */}
                            {(lead.job_description || job?.description) && (
                                <div style={{ marginBottom: 20 }}>
                                    <p style={{
                                        fontSize: 11, fontWeight: 700, letterSpacing: '.08em',
                                        textTransform: 'uppercase', color: INK4, marginBottom: 8,
                                    }}>What the homeowner needs</p>
                                    <p style={{ fontSize: 14, color: INK2, lineHeight: 1.75 }}>
                                        {lead.job_description || job?.description}
                                    </p>
                                </div>
                            )}

                            {/* Job meta chips */}
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
                                {(lead.job_type || job?.job_type) && (
                                    <span style={{
                                        padding: '4px 10px', borderRadius: 20, background: CREAM2,
                                        fontSize: 12, color: INK3, fontWeight: 600,
                                    }}>
                                        {(lead.job_type || job?.job_type) === 'residential' ? 'Residential' : 'Commercial'}
                                    </span>
                                )}
                                {(lead.service_type || job?.service_type) && (
                                    <span style={{
                                        padding: '4px 10px', borderRadius: 20, background: CREAM2,
                                        fontSize: 12, color: INK3, fontWeight: 600,
                                    }}>
                                        {SERVICE_TYPE_LABELS[lead.service_type || job?.service_type || ''] || 'Other'}
                                    </span>
                                )}
                            </div>

                            {/* Budget */}
                            {(lead.job_budget_min || lead.job_budget_max || job?.budget_min || job?.budget_max) && (
                                <div style={{
                                    background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 14,
                                    padding: '14px 16px', marginBottom: 20,
                                    display: 'flex', alignItems: 'center', gap: 10,
                                }}>
                                    <div style={{
                                        width: 36, height: 36, borderRadius: 10, background: TERRA_LIGHT,
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                                    }}>
                                        <DollarSign size={18} color={TERRA} />
                                    </div>
                                    <div>
                                        <p style={{ fontSize: 11, fontWeight: 700, color: INK4, marginBottom: 2 }}>Homeowner budget</p>
                                        <p style={{ fontSize: 15, fontWeight: 800, color: INK }}>
                                            {(() => {
                                                const lo = lead.job_budget_min ?? job?.budget_min;
                                                const hi = lead.job_budget_max ?? job?.budget_max;
                                                if (lo && hi) return `$${lo.toLocaleString()} - $${hi.toLocaleString()}`;
                                                if (hi) return `Up to $${hi.toLocaleString()}`;
                                                if (lo) return `From $${lo.toLocaleString()}`;
                                                return 'Not specified';
                                            })()}
                                        </p>
                                    </div>
                                </div>
                            )}

                            {/* Competition */}
                            {comp && competition && (
                                <div style={{
                                    background: comp.bg, border: `1px solid ${comp.color}33`, borderRadius: 14,
                                    padding: '14px 16px', marginBottom: 20,
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <TrendingUp size={15} color={comp.color} />
                                            <span style={{ fontSize: 12, fontWeight: 700, color: comp.color }}>{comp.label}</span>
                                        </div>
                                        <span style={{ fontSize: 12, color: INK3 }}>{competition.quote_count} quote{competition.quote_count !== 1 ? 's' : ''} sent</span>
                                    </div>
                                    {/* Competition bar */}
                                    <div style={{ height: 5, background: `${comp.color}20`, borderRadius: 4, overflow: 'hidden' }}>
                                        <div style={{
                                            height: '100%', borderRadius: 4, background: comp.color,
                                            width: `${comp.bar}%`, transition: 'width .4s ease',
                                        }} />
                                    </div>
                                    <p style={{ fontSize: 11, color: INK3, marginTop: 6 }}>{competition.message}</p>
                                </div>
                            )}

                            {/* Photos */}
                            {photos.length > 0 && (
                                <div style={{ marginBottom: 20 }}>
                                    <p style={{
                                        fontSize: 11, fontWeight: 700, letterSpacing: '.08em',
                                        textTransform: 'uppercase', color: INK4, marginBottom: 10,
                                        display: 'flex', alignItems: 'center', gap: 6,
                                    }}>
                                        <ImageIcon size={12} /> Photos ({photos.length})
                                    </p>
                                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                        {photos.map(p => (
                                            <button key={p.id} onClick={() => setLightbox(p.url)} style={{
                                                width: 80, height: 80, borderRadius: 10, padding: 0, border: `1px solid ${BORDER}`,
                                                cursor: 'pointer', overflow: 'hidden', flexShrink: 0,
                                            }}>
                                                <img src={p.url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Already quoted */}
                            {alreadyQuoted && existing && (
                                <div style={{
                                    background: GREEN_LIGHT, border: `1px solid ${GREEN}33`, borderRadius: 14,
                                    padding: '16px 18px', marginBottom: 8,
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                                        <CheckCircle2 size={16} color={GREEN} />
                                        <p style={{ fontSize: 13, fontWeight: 700, color: GREEN }}>Quote already sent</p>
                                    </div>
                                    <div style={{ display: 'flex', gap: 16 }}>
                                        <div>
                                            <p style={{ fontSize: 10, fontWeight: 700, color: INK4, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 2 }}>Amount</p>
                                            <p style={{ fontSize: 20, fontWeight: 800, color: INK }}>${existing.amount.toLocaleString()}</p>
                                        </div>
                                        <div style={{ flex: 1 }}>
                                            <p style={{ fontSize: 10, fontWeight: 700, color: INK4, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 2 }}>Status</p>
                                            <span style={{
                                                fontSize: 12, fontWeight: 700, padding: '3px 8px', borderRadius: 20,
                                                background: existing.status === 'accepted' ? GREEN_LIGHT : existing.status === 'rejected' ? '#FFEBEB' : AMBER_LIGHT,
                                                color: existing.status === 'accepted' ? GREEN : existing.status === 'rejected' ? '#A33030' : AMBER,
                                            }}>
                                                {existing.status === 'accepted' ? 'Accepted' : existing.status === 'rejected' ? 'Declined' : 'Pending'}
                                            </span>
                                        </div>
                                    </div>
                                    {existing.message && (
                                        <p style={{ fontSize: 12, color: INK3, marginTop: 10, lineHeight: 1.6, borderTop: `1px solid ${BORDER}`, paddingTop: 10 }}>
                                            "{existing.message}"
                                        </p>
                                    )}
                                </div>
                            )}

                            {/* Quote form  -  only show if not yet quoted */}
                            {!alreadyQuoted && (
                                <div style={{
                                    background: CREAM, border: `1px solid ${BORDER}`, borderRadius: 16,
                                    padding: '18px 18px', marginTop: 4,
                                }}>
                                    <p style={{ fontSize: 13, fontWeight: 800, color: INK, marginBottom: 16 }}>
                                        Send your quote
                                    </p>

                                    {/* Amount */}
                                    <div style={{ marginBottom: 14 }}>
                                        <label style={{ fontSize: 11, fontWeight: 700, color: INK4, textTransform: 'uppercase', letterSpacing: '.06em', display: 'block', marginBottom: 6 }}>
                                            Your quote amount (AUD) *
                                        </label>
                                        <div style={{ position: 'relative' }}>
                                            <span style={{
                                                position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)',
                                                fontSize: 16, fontWeight: 700, color: INK3, pointerEvents: 'none',
                                            }}>$</span>
                                            <input
                                                type="number"
                                                min="1"
                                                step="1"
                                                placeholder="e.g. 850"
                                                value={amount}
                                                onChange={e => setAmount(e.target.value)}
                                                style={{
                                                    width: '100%', padding: '12px 14px 12px 28px', borderRadius: 10,
                                                    border: `1px solid ${BORDER}`, background: '#fff', color: INK,
                                                    fontSize: 18, fontWeight: 700, outline: 'none', boxSizing: 'border-box',
                                                }}
                                            />
                                        </div>
                                    </div>

                                    {/* Message */}
                                    <div style={{ marginBottom: 14 }}>
                                        <label style={{ fontSize: 11, fontWeight: 700, color: INK4, textTransform: 'uppercase', letterSpacing: '.06em', display: 'block', marginBottom: 6 }}>
                                            Your message to the homeowner *
                                        </label>
                                        <textarea
                                            rows={5}
                                            placeholder="Introduce yourself, explain your approach, mention relevant experience, and note what's included in your price..."
                                            value={message}
                                            onChange={e => setMessage(e.target.value)}
                                            maxLength={1000}
                                            style={{
                                                width: '100%', padding: '12px 14px', borderRadius: 10,
                                                border: `1px solid ${BORDER}`, background: '#fff', color: INK,
                                                fontSize: 14, lineHeight: 1.6, fontFamily: 'inherit',
                                                resize: 'vertical', outline: 'none', boxSizing: 'border-box',
                                            }}
                                        />
                                        <p style={{ fontSize: 11, color: INK4, marginTop: 4, textAlign: 'right' }}>
                                            {message.length}/1000  -  min 20 characters
                                        </p>
                                    </div>

                                    {/* Tips */}
                                    <div style={{
                                        background: '#fff', border: `1px solid ${BORDER}`, borderRadius: 10,
                                        padding: '10px 12px', marginBottom: 14,
                                    }}>
                                        <p style={{ fontSize: 11, fontWeight: 700, color: INK3, marginBottom: 4 }}>Tips for winning quotes</p>
                                        <ul style={{ margin: 0, paddingLeft: 16, fontSize: 11, color: INK4, lineHeight: 1.8 }}>
                                            <li>Mention similar jobs you've completed</li>
                                            <li>Be specific about what's included in your price</li>
                                            <li>State your availability and expected timeframe</li>
                                        </ul>
                                    </div>

                                    {/* Error */}
                                    {submitError && (
                                        <div style={{
                                            display: 'flex', alignItems: 'center', gap: 8,
                                            background: '#FFEBEB', border: '1px solid #F5C0C0',
                                            color: '#A33030', padding: '10px 12px', borderRadius: 10,
                                            fontSize: 12, marginBottom: 12,
                                        }}>
                                            <AlertCircle size={14} style={{ flexShrink: 0 }} />
                                            {submitError}
                                        </div>
                                    )}
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* ── Sticky footer ────────────────────────────────────── */}
                {!loading && !alreadyQuoted && (
                    <div style={{
                        position: 'sticky', bottom: 0, background: '#fff',
                        borderTop: `1px solid ${CREAM2}`, padding: '12px 20px 20px',
                        display: 'flex', gap: 10,
                    }}>
                        <button onClick={onClose} style={{
                            flex: '0 0 auto', padding: '13px 18px', borderRadius: 12,
                            background: CREAM2, border: 'none', color: INK2,
                            fontWeight: 700, fontSize: 14, cursor: 'pointer',
                        }}>
                            Cancel
                        </button>
                        <button
                            onClick={handleSubmit}
                            disabled={submitting || !amount || !message || message.length < 20}
                            style={{
                                flex: 1, padding: '13px 18px', borderRadius: 12,
                                background: (!amount || message.length < 20) ? CREAM2 : TERRA,
                                color: (!amount || message.length < 20) ? INK4 : '#fff',
                                border: 'none', fontWeight: 800, fontSize: 14,
                                cursor: (submitting || !amount || message.length < 20) ? 'not-allowed' : 'pointer',
                                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                                opacity: submitting ? 0.7 : 1, transition: 'all .15s',
                            }}
                        >
                            {submitting
                                ? <><Loader2 size={16} className="animate-spin" /> Sending...</>
                                : <><Send size={15} /> Send Quote{amount ? `  -  $${parseFloat(amount || '0').toLocaleString()}` : ''}</>
                            }
                        </button>
                    </div>
                )}

                {/* Footer for already-quoted or loading states */}
                {!loading && alreadyQuoted && (
                    <div style={{
                        position: 'sticky', bottom: 0, background: '#fff',
                        borderTop: `1px solid ${CREAM2}`, padding: '12px 20px 20px',
                    }}>
                        <button onClick={onClose} style={{
                            width: '100%', padding: '13px', borderRadius: 12,
                            background: CREAM2, border: 'none', color: INK2,
                            fontWeight: 700, fontSize: 14, cursor: 'pointer',
                        }}>
                            Close
                        </button>
                    </div>
                )}
            </div>
        </>
    );
}
