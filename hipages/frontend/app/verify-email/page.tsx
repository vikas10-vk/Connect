"use client";

import React, { Suspense, useState, useRef, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'motion/react';
import { Zap, Mail, ArrowRight, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';
import api from '@/src/lib/api';

const C = {
    paper: '#FFF8E7', card: '#FFFFFF',
    ink: '#071D36', ink2: '#374151', ink3: '#6B7280', ink4: '#9CA3AF',
    gold: '#D4AA3A', goldL: '#FEF9EC', goldB: '#E8C766',
    rose: '#EF4444', roseL: '#FEF2F2',
    sage: '#16A34A', sageL: '#F0FDF4',
    line: '#E9DDBF',
};

function VerifyEmailForm() {
    const { user, fetchUser } = useAuth();
    const router = useRouter();

    const [code, setCode] = useState(['', '', '', '', '', '']);
    const [error, setError] = useState('');
    const [success, setSuccess] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [resending, setResending] = useState(false);
    const [resendCooldown, setResendCooldown] = useState(0);
    const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
    const cooldownRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // If user is already verified, go straight to dashboard
    useEffect(() => {
        if (user?.email_verified) {
            router.replace('/dashboard');
        }
    }, [user, router]);

    // Cleanup interval on unmount
    useEffect(() => {
        return () => { if (cooldownRef.current) clearInterval(cooldownRef.current); };
    }, []);

    const startCooldown = useCallback((seconds = 60) => {
        setResendCooldown(seconds);
        cooldownRef.current = setInterval(() => {
            setResendCooldown(prev => {
                if (prev <= 1) {
                    clearInterval(cooldownRef.current!);
                    return 0;
                }
                return prev - 1;
            });
        }, 1000);
    }, []);

    const handleChange = (idx: number, val: string) => {
        // Accept paste of full code
        if (val.length > 1) {
            const digits = val.replace(/\D/g, '').slice(0, 6).split('');
            const next = [...code];
            digits.forEach((d, i) => { if (i < 6) next[i] = d; });
            setCode(next);
            const focusIdx = Math.min(digits.length, 5);
            inputRefs.current[focusIdx]?.focus();
            return;
        }
        const digit = val.replace(/\D/g, '');
        const next = [...code];
        next[idx] = digit;
        setCode(next);
        if (digit && idx < 5) {
            inputRefs.current[idx + 1]?.focus();
        }
    };

    const handleKeyDown = (idx: number, e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Backspace' && !code[idx] && idx > 0) {
            inputRefs.current[idx - 1]?.focus();
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const fullCode = code.join('');
        if (fullCode.length < 6) { setError('Please enter the full 6-digit code.'); return; }
        setError('');
        setSubmitting(true);
        try {
            await api.post('/auth/verify-email-otp', { code: fullCode });
            setSuccess(true);
            // Refresh user so email_verified flips to true in context
            await fetchUser();
            setTimeout(() => router.push('/dashboard'), 1200);
        } catch (err: any) {
            const msg = err?.response?.data?.detail;
            setError(typeof msg === 'string' ? msg : 'Invalid or expired code. Try again.');
            setCode(['', '', '', '', '', '']);
            inputRefs.current[0]?.focus();
        } finally {
            setSubmitting(false);
        }
    };

    const handleResend = async () => {
        if (resendCooldown > 0) return;
        setResending(true);
        setError('');
        try {
            await api.post('/auth/resend-email-otp');
            startCooldown(60);
        } catch (err: any) {
            const msg = err?.response?.data?.detail;
            if (typeof msg === 'string' && msg.includes('wait')) {
                // Extract seconds from "Please wait X seconds" message
                const match = msg.match(/(\d+)/);
                if (match) startCooldown(parseInt(match[1]));
            }
            setError(typeof msg === 'string' ? msg : 'Could not resend. Try again shortly.');
        } finally {
            setResending(false);
        }
    };

    const inputBase: React.CSSProperties = {
        width: 52, height: 60, borderRadius: 14,
        border: `2px solid ${C.line}`,
        background: '#FFFFFF',
        fontSize: 28, fontWeight: 800,
        color: C.ink, textAlign: 'center',
        outline: 'none', fontFamily: "'Inter', monospace",
        transition: 'all 0.15s', caretColor: C.gold,
    };

    return (
        <div style={{
            minHeight: '100vh', background: C.paper,
            fontFamily: "'DM Sans', 'Inter', sans-serif",
            display: 'flex', flexDirection: 'column',
        }}>
            {/* Header */}
            <header style={{
                padding: '18px 24px', borderBottom: `1px solid ${C.line}`,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                background: C.ink,
            }}>
                <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
                    <div style={{ width: 34, height: 34, borderRadius: 10, background: C.gold, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <Zap size={18} color={C.ink} fill={C.ink} />
                    </div>
                    <span style={{ fontSize: 18, fontWeight: 900, color: C.gold, letterSpacing: '-0.02em' }}>ProConnect</span>
                </Link>
                <Link href="/login" style={{ fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.6)', textDecoration: 'none' }}>
                    ← Back to sign in
                </Link>
            </header>

            {/* Main */}
            <main style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 24px' }}>
                <motion.div
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.28 }}
                    style={{
                        width: '100%', maxWidth: 440,
                        background: C.card, borderRadius: 28,
                        border: `1px solid ${C.line}`,
                        boxShadow: '0 20px 60px rgba(7,29,54,0.10), 0 4px 12px rgba(7,29,54,0.06)',
                        padding: '40px 36px',
                    }}
                >
                    {success ? (
                        <motion.div
                            initial={{ opacity: 0, scale: 0.95 }}
                            animate={{ opacity: 1, scale: 1 }}
                            style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}
                        >
                            <div style={{ width: 64, height: 64, borderRadius: '50%', background: C.sageL, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <CheckCircle size={32} color={C.sage} />
                            </div>
                            <div>
                                <h2 style={{ fontSize: 24, fontWeight: 800, color: C.ink, margin: '0 0 8px', letterSpacing: '-0.02em' }}>Email verified!</h2>
                                <p style={{ fontSize: 14, color: C.ink3, margin: 0 }}>Taking you to your dashboard…</p>
                            </div>
                            <Loader2 size={18} color={C.gold} style={{ animation: 'spin 1s linear infinite' }} />
                        </motion.div>
                    ) : (
                        <>
                            {/* Icon + heading */}
                            <div style={{ textAlign: 'center', marginBottom: 28 }}>
                                <div style={{
                                    width: 56, height: 56, borderRadius: 16,
                                    background: C.goldL, border: `1px solid ${C.goldB}`,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    margin: '0 auto 16px',
                                }}>
                                    <Mail size={26} color={C.gold} />
                                </div>
                                <h1 style={{ fontSize: 26, fontWeight: 800, color: C.ink, margin: '0 0 8px', letterSpacing: '-0.02em' }}>
                                    Check your email
                                </h1>
                                <p style={{ fontSize: 14, color: C.ink3, margin: 0, lineHeight: 1.6 }}>
                                    We sent a 6-digit code to{' '}
                                    <strong style={{ color: C.ink2 }}>{user?.email || 'your email'}</strong>.
                                    Enter it below to verify your account.
                                </p>
                            </div>

                            {/* Error */}
                            {error && (
                                <div style={{
                                    display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20,
                                    background: C.roseL, border: `1px solid ${C.rose}30`,
                                    color: C.rose, padding: '10px 14px', borderRadius: 10, fontSize: 13,
                                }}>
                                    <AlertCircle size={14} style={{ flexShrink: 0 }} />{error}
                                </div>
                            )}

                            {/* OTP inputs */}
                            <form onSubmit={handleSubmit}>
                                <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginBottom: 24 }}>
                                    {code.map((digit, idx) => (
                                        <input
                                            key={idx}
                                            ref={el => { inputRefs.current[idx] = el; }}
                                            type="text"
                                            inputMode="numeric"
                                            maxLength={6}
                                            value={digit}
                                            onChange={e => handleChange(idx, e.target.value)}
                                            onKeyDown={e => handleKeyDown(idx, e)}
                                            onFocus={e => {
                                                e.target.style.borderColor = C.gold;
                                                e.target.style.background = C.goldL;
                                                e.target.style.boxShadow = `0 0 0 3px ${C.gold}20`;
                                            }}
                                            onBlur={e => {
                                                e.target.style.borderColor = digit ? C.gold : C.line;
                                                e.target.style.background = C.paper;
                                                e.target.style.boxShadow = 'none';
                                            }}
                                            style={{
                                                ...inputBase,
                                                borderColor: digit ? C.gold : C.line,
                                            }}
                                            autoFocus={idx === 0}
                                        />
                                    ))}
                                </div>

                                <button
                                    type="submit"
                                    disabled={submitting || code.join('').length < 6}
                                    style={{
                                        width: '100%', padding: '15px',
                                        borderRadius: 14, border: 'none',
                                        background: submitting || code.join('').length < 6 ? C.ink3 : C.ink,
                                        color: '#fff', fontSize: 15, fontWeight: 700,
                                        cursor: submitting || code.join('').length < 6 ? 'not-allowed' : 'pointer',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                                        transition: 'background 0.15s',
                                    }}
                                    onMouseEnter={e => { if (!submitting && code.join('').length === 6) e.currentTarget.style.background = '#000'; }}
                                    onMouseLeave={e => { if (!submitting && code.join('').length === 6) e.currentTarget.style.background = C.ink; }}
                                >
                                    {submitting
                                        ? <><Loader2 size={15} style={{ animation: 'spin 1s linear infinite' }} /> Verifying…</>
                                        : <><ArrowRight size={15} /> Verify email</>
                                    }
                                </button>
                            </form>

                            {/* Resend */}
                            <div style={{ textAlign: 'center', marginTop: 22 }}>
                                <p style={{ fontSize: 13, color: C.ink4, marginBottom: 8 }}>
                                    Didn't receive the code?
                                </p>
                                <button
                                    onClick={handleResend}
                                    disabled={resendCooldown > 0 || resending}
                                    style={{
                                        background: 'none', border: 'none', padding: 0,
                                        fontSize: 13, fontWeight: 700,
                                        color: resendCooldown > 0 ? C.ink4 : C.gold,
                                        cursor: resendCooldown > 0 ? 'not-allowed' : 'pointer',
                                        display: 'inline-flex', alignItems: 'center', gap: 5,
                                    }}
                                >
                                    {resending
                                        ? <><Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> Sending…</>
                                        : resendCooldown > 0
                                            ? `Resend in ${resendCooldown}s`
                                            : <>Resend code</>
                                    }
                                </button>
                            </div>

                            {/* Wrong email */}
                            <div style={{
                                marginTop: 24, paddingTop: 18,
                                borderTop: `1px solid ${C.line}`,
                                textAlign: 'center',
                            }}>
                                <p style={{ fontSize: 12, color: C.ink4, margin: 0 }}>
                                    Wrong email?{' '}
                                    <Link href="/signup" style={{ color: C.ink2, fontWeight: 600, textDecoration: 'underline' }}>
                                        Register again
                                    </Link>
                                </p>
                            </div>
                        </>
                    )}
                </motion.div>
            </main>

            <style>{`
                * { box-sizing: border-box; }
                body { margin: 0; }
                @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
                input[type="text"]::-webkit-outer-spin-button,
                input[type="text"]::-webkit-inner-spin-button { -webkit-appearance: none; }
            `}</style>
        </div>
    );
}

export default function VerifyEmailPage() {
    return (
        <Suspense fallback={
            <div style={{ minHeight: '100vh', background: '#FFF8E7', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Loader2 size={22} color="#D4AA3A" style={{ animation: 'spin 1s linear infinite' }} />
            </div>
        }>
            <VerifyEmailForm />
        </Suspense>
    );
}
