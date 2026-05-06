"use client";

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2, MapPin, ShieldCheck, Briefcase, ArrowLeft, Zap, AlertCircle, Check } from 'lucide-react';
import api from '@/src/lib/api';

// ── Palette (matches homeowner dashboard) ────────────────────────────────────
const CREAM = '#FDFAF5';
const CREAM2 = '#F5F0E8';
const TERRA = '#C5563A';
const TERRA_LIGHT = '#F5EDE9';
const TERRA_DARK = '#9B3E2A';
const INK = '#2C1A0E';
const INK2 = '#4A3728';
const INK3 = '#7A6558';
const INK4 = '#A89080';
const BORDER = '#E8E0D0';
const GREEN = '#2E7D5A';
const GREEN_LIGHT = '#E8F5EE';

interface Category { id: string; name: string; }

interface PublicProfile {
    id: string;
    business_name: string;
    bio?: string | null;
    suburb?: string | null;
    state?: string | null;
    is_available: boolean;
    avatar_url?: string | null;
    cover_photo_url?: string | null;
    is_verified: boolean;
    full_name?: string | null;
    categories: Category[];
    // Note: ratings, review count, reviews list, solo/team are intentionally
    // not part of the response — backend hides them on public profiles.
}

const initials = (name?: string | null) =>
    name ? name.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2) : 'T';

export default function TradiePublicProfilePage() {
    const params = useParams();
    const router = useRouter();
    const id = (params?.id as string) || '';

    const [profile, setProfile] = useState<PublicProfile | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!id) return;
        let cancelled = false;
        (async () => {
            setLoading(true);
            setError(null);
            try {
                const res = await api.get(`/tradies/${id}/public`);
                if (!cancelled) setProfile(res.data);
            } catch (err: any) {
                if (cancelled) return;
                if (err?.response?.status === 404) setError('This tradie is not available.');
                else setError('Could not load profile. Please refresh.');
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [id]);

    if (loading) {
        return (
            <div style={{ minHeight: '100vh', background: CREAM, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Loader2 size={32} color={TERRA} className="animate-spin" />
            </div>
        );
    }

    if (error || !profile) {
        return (
            <div style={{ minHeight: '100vh', background: CREAM, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
                <div style={{
                    maxWidth: 380, width: '100%', textAlign: 'center', background: '#fff',
                    padding: '36px 28px', borderRadius: 20, border: `1px solid ${BORDER}`,
                }}>
                    <div style={{
                        width: 56, height: 56, borderRadius: 18, margin: '0 auto 16px',
                        background: '#FFEBEB', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <AlertCircle size={28} color="#A33030" />
                    </div>
                    <h2 style={{ fontSize: 18, fontWeight: 800, color: INK, marginBottom: 6 }}>Profile unavailable</h2>
                    <p style={{ fontSize: 13, color: INK4, marginBottom: 18 }}>{error || 'Profile not found.'}</p>
                    <Link href="/" style={{
                        display: 'inline-flex', alignItems: 'center', gap: 6,
                        padding: '10px 18px', borderRadius: 12,
                        background: TERRA, color: '#fff', textDecoration: 'none',
                        fontWeight: 700, fontSize: 13,
                    }}>
                        <ArrowLeft size={14} /> Back home
                    </Link>
                </div>
            </div>
        );
    }

    const locationLabel = [profile.suburb, profile.state].filter(Boolean).join(', ');
    const firstCategory = profile.categories[0]?.name;
    const categoryQuery = firstCategory ? `?category=${encodeURIComponent(firstCategory)}` : '';
    const firstName = profile.business_name.split(' ')[0];

    return (
        <div style={{ minHeight: '100vh', background: CREAM, fontFamily: "'DM Sans', sans-serif" }}>
            <style>{`
        .pp-cta-mobile { display: none; }
        .pp-cta-inline { display: flex; }
        @media (max-width: 767px) {
          .pp-hero { height: 180px !important; }
          .pp-avatar {
            width: 90px !important; height: 90px !important;
            font-size: 28px !important; margin-top: -45px !important;
          }
          .pp-name { font-size: 22px !important; }
          .pp-grid { grid-template-columns: 1fr !important; }
          .pp-cta-inline { display: none !important; }
          .pp-cta-mobile {
            display: flex !important;
            position: fixed; bottom: 0; left: 0; right: 0;
            padding: 12px 16px;
            border-top: 1px solid ${BORDER};
            background: #fff;
            z-index: 30;
            box-shadow: 0 -4px 16px rgba(0,0,0,0.06);
          }
          .pp-content-wrap { padding-bottom: 90px !important; }
        }
      `}</style>

            {/* ── Top bar ─────────────────────────────────────────────────────── */}
            <header style={{
                position: 'sticky', top: 0, zIndex: 100,
                background: 'rgba(253,250,245,0.92)', backdropFilter: 'blur(10px)',
                borderBottom: `1px solid ${BORDER}`,
                padding: '14px 20px',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            }}>
                <button onClick={() => router.back()} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '8px 14px', borderRadius: 10,
                    background: 'transparent', border: 'none', cursor: 'pointer',
                    color: INK2, fontWeight: 600, fontSize: 13,
                }}>
                    <ArrowLeft size={16} /> Back
                </button>
                <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
                    <div style={{
                        width: 30, height: 30, borderRadius: 9, background: TERRA,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <Zap size={16} fill="#fff" color="#fff" />
                    </div>
                    <span style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, color: TERRA, fontSize: 16 }}>ProConnect</span>
                </Link>
            </header>

            <div className="pp-content-wrap" style={{ maxWidth: 960, margin: '0 auto', padding: '0 20px' }}>
                {/* ── Cover hero ─────────────────────────────────────────────────── */}
                <div className="pp-hero" style={{
                    height: 240, marginTop: 20, borderRadius: 24, overflow: 'hidden',
                    position: 'relative',
                    background: profile.cover_photo_url
                        ? `url(${profile.cover_photo_url}) center/cover no-repeat`
                        : `linear-gradient(135deg, ${TERRA} 0%, ${TERRA_DARK} 100%)`,
                }}>
                    {!profile.cover_photo_url && (
                        <div style={{
                            position: 'absolute', inset: 0,
                            background: 'radial-gradient(circle at 30% 30%, rgba(255,255,255,0.15), transparent 60%)',
                        }} />
                    )}
                </div>

                {/* ── Header card (overlaps the hero) ────────────────────────────── */}
                <div style={{
                    background: '#fff', borderRadius: 20,
                    border: `1px solid ${BORDER}`, padding: '0 24px 24px',
                    marginTop: -40, position: 'relative', zIndex: 2,
                }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
                        <div className="pp-avatar" style={{
                            width: 110, height: 110, borderRadius: 28, marginTop: -55,
                            background: profile.avatar_url
                                ? `url(${profile.avatar_url}) center/cover no-repeat`
                                : `linear-gradient(135deg, ${TERRA}, ${TERRA_DARK})`,
                            border: '4px solid #fff',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            color: '#fff', fontWeight: 800, fontSize: 36,
                            boxShadow: '0 8px 24px rgba(44,26,14,0.15)',
                            flexShrink: 0,
                        }}>
                            {!profile.avatar_url && initials(profile.business_name)}
                        </div>

                        {profile.is_available && (
                            <div style={{
                                marginTop: 18, display: 'flex', alignItems: 'center', gap: 6,
                                padding: '6px 12px', borderRadius: 20,
                                background: GREEN_LIGHT, color: GREEN,
                                fontSize: 12, fontWeight: 700,
                            }}>
                                <span style={{ width: 8, height: 8, borderRadius: '50%', background: GREEN, display: 'inline-block' }} />
                                Available now
                            </div>
                        )}
                    </div>

                    <div style={{ marginTop: 14 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                            <h1 className="pp-name" style={{ fontSize: 28, fontWeight: 800, color: INK, lineHeight: 1.2 }}>
                                {profile.business_name}
                            </h1>
                            {profile.is_verified && (
                                <span style={{
                                    display: 'inline-flex', alignItems: 'center', gap: 4,
                                    padding: '4px 10px', borderRadius: 20,
                                    background: '#E0F4FF', color: '#0077AA',
                                    fontSize: 11, fontWeight: 700,
                                }}>
                                    <ShieldCheck size={12} /> Verified
                                </span>
                            )}
                        </div>

                        {locationLabel && (
                            <p style={{
                                marginTop: 8, display: 'flex', alignItems: 'center', gap: 6,
                                fontSize: 14, color: INK3,
                            }}>
                                <MapPin size={14} /> {locationLabel}
                            </p>
                        )}
                    </div>

                    {/* Inline desktop CTA */}
                    <div className="pp-cta-inline" style={{ marginTop: 18, gap: 10 }}>
                        <Link href={`/book${categoryQuery}`} style={{
                            flex: 1, maxWidth: 280,
                            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                            padding: '13px 20px', borderRadius: 14,
                            background: TERRA, color: '#fff', textDecoration: 'none',
                            fontWeight: 800, fontSize: 14,
                            boxShadow: '0 6px 16px rgba(197,86,58,0.25)',
                        }}>
                            <Briefcase size={16} /> Get a quote
                        </Link>
                    </div>
                </div>

                {/* ── Body grid ──────────────────────────────────────────────────── */}
                <div className="pp-grid" style={{
                    marginTop: 20, display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20,
                }}>
                    {/* Left: bio + services */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                        {profile.bio && (
                            <div style={{ background: '#fff', borderRadius: 18, border: `1px solid ${BORDER}`, padding: 22 }}>
                                <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', color: INK4, marginBottom: 10 }}>
                                    About
                                </p>
                                <p style={{ fontSize: 15, color: INK2, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                                    {profile.bio}
                                </p>
                            </div>
                        )}

                        <div style={{ background: '#fff', borderRadius: 18, border: `1px solid ${BORDER}`, padding: 22 }}>
                            <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', color: INK4, marginBottom: 14 }}>
                                Services offered
                            </p>
                            {profile.categories.length === 0 ? (
                                <p style={{ fontSize: 14, color: INK4 }}>No services listed yet.</p>
                            ) : (
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                                    {profile.categories.map(cat => (
                                        <span key={cat.id} style={{
                                            padding: '8px 14px', borderRadius: 20,
                                            background: TERRA_LIGHT, color: TERRA,
                                            fontSize: 13, fontWeight: 600,
                                        }}>
                                            {cat.name}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Right: trust sidebar */}
                    <aside style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                        <div style={{ background: '#fff', borderRadius: 18, border: `1px solid ${BORDER}`, padding: 22 }}>
                            <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', color: INK4, marginBottom: 12 }}>
                                Trust & verification
                            </p>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                {[
                                    { label: 'Identity verified', shown: profile.is_verified },
                                    { label: 'Approved by ProConnect', shown: true },
                                    { label: 'Available for new work', shown: profile.is_available },
                                ].map(item => (
                                    <div key={item.label} style={{
                                        display: 'flex', alignItems: 'center', gap: 10,
                                        fontSize: 13, color: item.shown ? INK2 : INK4,
                                    }}>
                                        <div style={{
                                            width: 22, height: 22, borderRadius: 7,
                                            background: item.shown ? GREEN_LIGHT : CREAM2,
                                            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                                        }}>
                                            <Check size={13} color={item.shown ? GREEN : INK4} strokeWidth={2.5} />
                                        </div>
                                        {item.label}
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div style={{
                            background: '#fff', borderRadius: 18, border: `1px solid ${BORDER}`, padding: 20,
                        }}>
                            <p style={{ fontSize: 13, color: INK3, lineHeight: 1.6, marginBottom: 10 }}>
                                Ready to get started?
                            </p>
                            <Link href={`/book${categoryQuery}`} style={{
                                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                                padding: '11px 16px', borderRadius: 12,
                                background: CREAM2, color: INK2, textDecoration: 'none',
                                fontWeight: 700, fontSize: 13,
                                border: `1px solid ${BORDER}`,
                            }}>
                                <Briefcase size={14} /> Post a job
                            </Link>
                        </div>
                    </aside>
                </div>
            </div>

            {/* ── Mobile sticky CTA ──────────────────────────────────────────────── */}
            <div className="pp-cta-mobile">
                <Link href={`/book${categoryQuery}`} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                    padding: '14px', borderRadius: 14, width: '100%',
                    background: TERRA, color: '#fff', textDecoration: 'none',
                    fontWeight: 800, fontSize: 15,
                    boxShadow: '0 6px 16px rgba(197,86,58,0.25)',
                }}>
                    <Briefcase size={16} /> Get a quote from {firstName}
                </Link>
            </div>
        </div>
    );
}
