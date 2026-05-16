"use client";

import React, { useState } from 'react';
import { X, Star, Loader2, Check, AlertCircle } from 'lucide-react';
import api from '@/src/lib/api';

// ── Palette (matches homeowner dashboard) ────────────────────────────────────
const CREAM = '#FBF8EF';
const CREAM2 = '#F1EBDD';
const TERRA = '#D4AA3A';
const INK = '#071D36';
const INK2 = '#173452';
const INK3 = '#56677A';
const INK4 = '#8A785A';
const BORDER = '#E9DDBF';
const GREEN = '#2E7D5A';
const GREEN_LIGHT = '#E8F5EE';

interface Props {
    jobId: string;
    jobTitle: string;
    tradieName?: string;
    onClose: () => void;
    onSubmitted: () => void;
}

const RATING_LABELS = ['Poor', 'Fair', 'Good', 'Great', 'Excellent'];

export default function ReviewSubmissionModal({
    jobId, jobTitle, tradieName, onClose, onSubmitted,
}: Props) {
    const [rating, setRating] = useState(0);
    const [hoverRating, setHoverRating] = useState(0);
    const [comment, setComment] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    const submit = async () => {
        if (rating < 1) {
            setError('Please choose a rating from 1 to 5 stars.');
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            await api.post(`/jobs/${jobId}/review`, {
                rating,
                comment: comment.trim() || null,
            });
            setSuccess(true);
            setTimeout(() => {
                onSubmitted();
                onClose();
            }, 1400);
        } catch (err: any) {
            const msg = err?.response?.data?.detail;
            setError(typeof msg === 'string' ? msg : 'Could not submit review. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    // ── Success state ───────────────────────────────────────────────────────
    if (success) {
        return (
            <div onClick={onClose} style={{
                position: 'fixed', inset: 0, zIndex: 200,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: 16, background: 'rgba(7,29,54,0.55)', backdropFilter: 'blur(6px)',
            }}>
                <div onClick={e => e.stopPropagation()} style={{
                    width: '100%', maxWidth: 400, background: '#fff',
                    borderRadius: 24, padding: '36px 28px', textAlign: 'center',
                    border: `1px solid ${BORDER}`,
                }}>
                    <div style={{
                        width: 60, height: 60, borderRadius: 18, margin: '0 auto 16px',
                        background: GREEN_LIGHT, display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <Check size={32} color={GREEN} strokeWidth={2.5} />
                    </div>
                    <h3 style={{ fontSize: 18, fontWeight: 800, color: INK, marginBottom: 6 }}>
                        Review submitted
                    </h3>
                    <p style={{ fontSize: 13, color: INK4, lineHeight: 1.5 }}>
                        Thanks! Your review will appear publicly once an admin approves it.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div onClick={onClose} style={{
            position: 'fixed', inset: 0, zIndex: 200,
            display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
            background: 'rgba(7,29,54,0.55)', backdropFilter: 'blur(6px)',
        }}>
            <style>{`
        @media (min-width: 768px) {
          .review-modal-shell {
            border-radius: 24px !important;
            max-height: 88vh !important;
            margin: auto !important;
          }
          .review-modal-overlay {
            align-items: center !important;
          }
        }
      `}</style>
            <div onClick={e => e.stopPropagation()} className="review-modal-shell" style={{
                width: '100%', maxWidth: 460, background: '#fff',
                borderTopLeftRadius: 24, borderTopRightRadius: 24,
                maxHeight: '92vh', overflowY: 'auto',
                boxShadow: '0 -16px 60px rgba(44,26,14,.18)',
            }}>
                {/* ── Header ─────────────────────────────────────────────────────── */}
                <div style={{
                    padding: '20px 22px 14px', position: 'relative',
                    borderBottom: `1px solid ${CREAM2}`,
                }}>
                    <button onClick={onClose} style={{
                        position: 'absolute', top: 14, right: 14,
                        width: 32, height: 32, borderRadius: 10,
                        background: CREAM2, border: 'none', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', color: INK4,
                    }}>
                        <X size={14} />
                    </button>
                    <p style={{
                        fontSize: 10, fontWeight: 700, letterSpacing: '.1em',
                        textTransform: 'uppercase', color: INK4, marginBottom: 4,
                    }}>
                        Leave a review
                    </p>
                    <h2 style={{
                        fontSize: 20, fontWeight: 800, color: INK,
                        lineHeight: 1.25, paddingRight: 32,
                    }}>
                        How did {tradieName || 'the tradie'} do?
                    </h2>
                    <p style={{ fontSize: 12, color: INK4, marginTop: 4 }}>
                        For: <span style={{ fontWeight: 600, color: INK2 }}>{jobTitle}</span>
                    </p>
                </div>

                {/* ── Star rating ───────────────────────────────────────────────── */}
                <div style={{ padding: '22px 22px 14px' }}>
                    <p style={{
                        fontSize: 11, fontWeight: 700, color: INK4, marginBottom: 12,
                        textTransform: 'uppercase', letterSpacing: '.06em',
                    }}>
                        Your rating
                    </p>
                    <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                        {[1, 2, 3, 4, 5].map(n => {
                            const filled = (hoverRating || rating) >= n;
                            return (
                                <button key={n}
                                    onClick={() => setRating(n)}
                                    onMouseEnter={() => setHoverRating(n)}
                                    onMouseLeave={() => setHoverRating(0)}
                                    aria-label={`${n} star${n > 1 ? 's' : ''}`}
                                    style={{
                                        width: 50, height: 50, padding: 0, border: 'none', cursor: 'pointer',
                                        background: 'transparent',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        transition: 'transform .12s',
                                        transform: filled ? 'scale(1.05)' : 'scale(1)',
                                    }}>
                                    <Star size={36}
                                        color={filled ? '#F59E0B' : '#D6CCC0'}
                                        fill={filled ? '#F59E0B' : 'transparent'}
                                        strokeWidth={1.6}
                                    />
                                </button>
                            );
                        })}
                    </div>
                    {rating > 0 && (
                        <p style={{
                            textAlign: 'center', marginTop: 8,
                            fontSize: 13, fontWeight: 700, color: INK2,
                        }}>
                            {RATING_LABELS[rating - 1]}
                        </p>
                    )}
                </div>

                {/* ── Comment ───────────────────────────────────────────────────── */}
                <div style={{ padding: '0 22px 16px' }}>
                    <label style={{
                        fontSize: 11, fontWeight: 700, color: INK4, marginBottom: 8,
                        textTransform: 'uppercase', letterSpacing: '.06em', display: 'block',
                    }}>
                        Tell others about your experience{' '}
                        <span style={{ color: INK4, fontWeight: 500, textTransform: 'none', letterSpacing: 0 }}>
                            (optional)
                        </span>
                    </label>
                    <textarea
                        value={comment}
                        onChange={e => setComment(e.target.value)}
                        rows={5}
                        maxLength={2000}
                        placeholder="What was the tradie like to work with? Was the job done well, on time, on budget?"
                        style={{
                            width: '100%', padding: '12px 14px', borderRadius: 12,
                            border: `1px solid ${BORDER}`, background: CREAM,
                            fontSize: 16, lineHeight: 1.6, fontFamily: 'inherit',
                            color: INK, resize: 'vertical', outline: 'none',
                            boxSizing: 'border-box',
                        }}
                    />
                    <p style={{ fontSize: 11, color: INK4, marginTop: 6, textAlign: 'right' }}>
                        {comment.length}/2000
                    </p>
                </div>

                {/* ── Notice ────────────────────────────────────────────────────── */}
                <div style={{
                    margin: '0 22px 16px', padding: 12,
                    background: CREAM2, borderRadius: 10, border: `1px solid ${BORDER}`,
                }}>
                    <p style={{ fontSize: 11, color: INK3, lineHeight: 1.5 }}>
                        Your review will be checked by our team before it appears publicly.
                    </p>
                </div>

                {/* ── Error ─────────────────────────────────────────────────────── */}
                {error && (
                    <div style={{
                        margin: '0 22px 16px',
                        display: 'flex', alignItems: 'center', gap: 8,
                        background: '#FFEBEB', border: '1px solid #F5C0C0',
                        color: '#A33030', padding: 12, borderRadius: 10, fontSize: 12,
                    }}>
                        <AlertCircle size={14} style={{ flexShrink: 0 }} />
                        <span>{error}</span>
                    </div>
                )}

                {/* ── Submit ────────────────────────────────────────────────────── */}
                <div style={{
                    padding: '16px 22px 22px', borderTop: `1px solid ${CREAM2}`,
                    position: 'sticky', bottom: 0, background: '#fff',
                    display: 'flex', gap: 8,
                }}>
                    <button onClick={onClose} disabled={submitting} style={{
                        flex: '0 0 auto', padding: '13px 18px', borderRadius: 12,
                        background: CREAM2, border: 'none', color: INK2,
                        fontWeight: 700, fontSize: 14,
                        cursor: submitting ? 'not-allowed' : 'pointer',
                        opacity: submitting ? 0.5 : 1,
                    }}>
                        Cancel
                    </button>
                    <button onClick={submit} disabled={submitting || rating < 1} style={{
                        flex: 1, padding: '13px 18px', borderRadius: 12,
                        background: rating < 1 ? CREAM2 : TERRA,
                        color: rating < 1 ? INK4 : '#fff',
                        border: 'none', fontWeight: 800, fontSize: 14,
                        cursor: (submitting || rating < 1) ? 'not-allowed' : 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                        transition: 'all .15s',
                    }}>
                        {submitting
                            ? <><Loader2 size={16} className="animate-spin" /> Submitting…</>
                            : 'Submit review'}
                    </button>
                </div>
            </div>
        </div>
    );
}
