"use client";

import React, { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'motion/react';
import {
    Zap, Mail, Lock, ArrowRight, AlertCircle, Loader2,
    Eye, EyeOff, ShieldCheck,
} from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';

// ─── Atelier design tokens (matches tradie dashboard exactly) ────────────────
const C = {
    paper: '#FFF8E7', panel: '#071D36', card: '#FFFFFF',
    line: '#E8D9B0', lineSoft: '#F0E4C4',
    ink: '#071D36', ink2: '#173452', ink3: '#56677A', ink4: '#8A785A',
    brass: '#D4AA3A', brassL: '#F7EBC5', brassB: '#E8C766',
    sage: '#5B7560', sageL: '#EDF3EE',
    amber: '#9A6B1E', amberL: '#F7EED8',
    rose: '#A8423A', roseL: '#F7E6E4',
};
const SHADOW_SM = '0 1px 3px rgba(26,26,26,0.05), 0 1px 2px rgba(26,26,26,0.03)';
const SHADOW_LG = '0 20px 60px rgba(26,26,26,0.14), 0 4px 12px rgba(26,26,26,0.06)';
const DISPLAY = "'Fraunces', 'Playfair Display', Georgia, serif";
const UI = "'Inter', 'DM Sans', -apple-system, system-ui, sans-serif";

function TradieLoginForm() {
    const { login } = useAuth();
    const router = useRouter();
    const searchParams = useSearchParams();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPwd, setShowPwd] = useState(false);
    const [error, setError] = useState('');
    const [submitting, setSubmitting] = useState(false);

    const sessionExpired = searchParams.get('session') === 'expired';

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        if (!email.includes('@')) { setError('Please enter a valid email.'); return; }
        if (!password) { setError('Please enter your password.'); return; }
        setSubmitting(true);
        try {
            const user = await login(email.trim().toLowerCase(), password, 'tradie');
            // If a homeowner accidentally lands here, route them home
            if (user?.role === 'homeowner') {
                router.push('/dashboard');
            } else {
                router.push('/tradie/dashboard');
            }
        } catch (err: any) {
            setError(err?.message || 'Invalid email or password');
        } finally {
            setSubmitting(false);
        }
    };

    const inputStyle: React.CSSProperties = {
        width: '100%', padding: '14px 16px 14px 44px', borderRadius: 12,
        border: `1.5px solid ${C.line}`, background: C.paper,
        fontSize: 14.5, color: C.ink, outline: 'none',
        boxSizing: 'border-box', fontFamily: UI, transition: 'all 0.15s',
    };
    const inputFocusOn = (e: any) => { e.target.style.borderColor = C.brass; e.target.style.background = C.card; };
    const inputFocusOff = (e: any) => { e.target.style.borderColor = C.line; e.target.style.background = C.paper; };

    return (
        <div style={{
            minHeight: '100vh', background: C.paper, fontFamily: UI, color: C.ink,
            display: 'flex', flexDirection: 'column',
        }}>
            {/* Header — navy, matches site-wide navbar */}
            <header style={{
                padding: '16px 28px', borderBottom: '1px solid rgba(255,255,255,0.08)',
                background: '#071D36', backdropFilter: 'blur(10px)',
                position: 'sticky', top: 0, zIndex: 100,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16,
                boxShadow: '0 2px 12px rgba(7,29,54,0.35)',
            }}>
                <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
                    <div style={{
                        width: 34, height: 34, borderRadius: 9, background: C.brass,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        boxShadow: '0 3px 10px rgba(212,170,58,0.35)',
                    }}>
                        <Zap size={17} color={C.ink} fill={C.ink} />
                    </div>
                    <div>
                        <p style={{ fontFamily: DISPLAY, fontSize: 17, fontWeight: 700, color: C.brass, margin: 0, letterSpacing: '-0.01em', lineHeight: 1 }}>ProConnect</p>
                        <p style={{ fontSize: 9, fontWeight: 700, color: 'rgba(255,255,255,0.4)', margin: '3px 0 0', textTransform: 'uppercase', letterSpacing: '0.14em' }}>Tradie Studio</p>
                    </div>
                </Link>
                <Link href="/" style={{ fontSize: 12.5, fontWeight: 600, color: 'rgba(255,255,255,0.55)', textDecoration: 'none' }}
                    onMouseEnter={(e: any) => (e.currentTarget.style.color = C.brass)}
                    onMouseLeave={(e: any) => (e.currentTarget.style.color = 'rgba(255,255,255,0.55)')}>
                    ← Back to home
                </Link>
            </header>

            {/* Centered card */}
            <main style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: '40px 24px',
            }}>
                <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    style={{
                        width: '100%', maxWidth: 460,
                        background: C.card, borderRadius: 18, border: `1px solid ${C.line}`,
                        boxShadow: SHADOW_LG, padding: '40px 36px',
                    }}
                >
                    {/* Heading */}
                    <div style={{ marginBottom: 28 }}>
                        <p style={{
                            fontSize: 11, fontWeight: 700, color: C.brass,
                            textTransform: 'uppercase', letterSpacing: '0.16em',
                            margin: '0 0 10px',
                        }}>Tradie sign in</p>
                        <h1 style={{
                            fontFamily: DISPLAY, fontSize: 32, fontWeight: 400, color: C.ink,
                            margin: '0 0 8px', letterSpacing: '-0.025em', lineHeight: 1.15,
                        }}>
                            Welcome back
                        </h1>
                        <p style={{ fontSize: 14, color: C.ink2, margin: 0, lineHeight: 1.6 }}>
                            Sign in to access your tradie dashboard, manage leads, and grow your business.
                        </p>
                    </div>

                    {/* Session expired banner */}
                    {sessionExpired && (
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18,
                            background: C.amberL, border: `1px solid ${C.amber}30`, color: C.amber,
                            padding: '10px 14px', borderRadius: 10, fontSize: 13, fontWeight: 500,
                        }}>
                            <AlertCircle size={14} />
                            Your session expired. Please sign in again.
                        </div>
                    )}

                    {/* Error */}
                    {error && (
                        <div style={{
                            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18,
                            background: C.roseL, border: `1px solid ${C.rose}30`, color: C.rose,
                            padding: '10px 14px', borderRadius: 10, fontSize: 13,
                        }}>
                            <AlertCircle size={14} />{error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

                        {/* Email */}
                        <div>
                            <label style={{
                                fontSize: 11, fontWeight: 600, color: C.ink2,
                                textTransform: 'uppercase', letterSpacing: '0.08em',
                                display: 'block', marginBottom: 8,
                            }}>Email</label>
                            <div style={{ position: 'relative' }}>
                                <Mail size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                <input
                                    type="email"
                                    value={email}
                                    onChange={e => setEmail(e.target.value)}
                                    placeholder="you@example.com"
                                    autoComplete="email"
                                    required
                                    style={inputStyle}
                                    onFocus={inputFocusOn}
                                    onBlur={inputFocusOff}
                                />
                            </div>
                        </div>

                        {/* Password */}
                        <div>
                            <label style={{
                                fontSize: 11, fontWeight: 600, color: C.ink2,
                                textTransform: 'uppercase', letterSpacing: '0.08em',
                                display: 'block', marginBottom: 8,
                            }}>Password</label>
                            <div style={{ position: 'relative' }}>
                                <Lock size={15} style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: C.ink3, pointerEvents: 'none' }} />
                                <input
                                    type={showPwd ? 'text' : 'password'}
                                    value={password}
                                    onChange={e => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    autoComplete="current-password"
                                    required
                                    style={{ ...inputStyle, paddingRight: 44 }}
                                    onFocus={inputFocusOn}
                                    onBlur={inputFocusOff}
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPwd(s => !s)}
                                    style={{
                                        position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                                        background: 'none', border: 'none', cursor: 'pointer',
                                        color: C.ink3, padding: 4, display: 'flex',
                                    }}
                                >
                                    {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                                </button>
                            </div>
                        </div>

                        {/* Submit */}
                        <button
                            type="submit"
                            disabled={submitting}
                            style={{
                                marginTop: 8, padding: '15px 22px', borderRadius: 12,
                                border: 'none', background: submitting ? C.ink3 : C.ink, color: C.card,
                                fontSize: 14, fontWeight: 600,
                                cursor: submitting ? 'not-allowed' : 'pointer',
                                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                                transition: 'background 0.15s',
                            }}
                            onMouseEnter={e => { if (!submitting) e.currentTarget.style.background = '#0E2E55'; }}
                            onMouseLeave={e => { if (!submitting) e.currentTarget.style.background = C.ink; }}
                        >
                            {submitting ? <Loader2 size={15} className="animate-spin" /> : <ArrowRight size={15} />}
                            {submitting ? 'Signing in…' : 'Sign in'}
                        </button>
                    </form>

                    {/* Footer links */}
                    <div style={{
                        marginTop: 28, paddingTop: 20,
                        borderTop: `1px solid ${C.lineSoft}`,
                        textAlign: 'center',
                    }}>
                        <p style={{ fontSize: 13, color: C.ink3, margin: '0 0 12px' }}>
                            New to ProConnect?{' '}
                            <Link href="/tradie/onboarding" style={{ color: C.brass, fontWeight: 600, textDecoration: 'none' }}>
                                Join as a tradie
                            </Link>
                        </p>
                        <div style={{
                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                            paddingTop: 8, fontSize: 11.5, color: C.ink4,
                        }}>
                            <ShieldCheck size={12} />
                            <span>
                                Are you a homeowner?{' '}
                                <Link href="/login" style={{ color: C.ink2, fontWeight: 600, textDecoration: 'underline' }}>
                                    Sign in here
                                </Link>
                            </span>
                        </div>
                    </div>
                </motion.div>
            </main>

            <style>{`
        * { box-sizing: border-box; }
        body { margin: 0; }
        @import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600&family=Inter:wght@400;500;600;700&display=swap');
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .animate-spin { animation: spin 1s linear infinite; }
        ::selection { background: ${C.brass}; color: ${C.card}; }
        @media (max-width: 480px) {
          input { font-size: 16px !important; }
        }
      `}</style>
        </div>
    );
}

export default function TradieLoginPage() {
    return (
        <Suspense fallback={
            <div style={{
                minHeight: '100vh', background: C.paper, display: 'flex',
                alignItems: 'center', justifyContent: 'center',
            }}>
                <Loader2 size={20} color={C.brass} className="animate-spin" />
            </div>
        }>
            <TradieLoginForm />
        </Suspense>
    );
}
