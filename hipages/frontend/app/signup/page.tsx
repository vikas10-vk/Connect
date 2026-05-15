"use client";

import React, { Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/src/contexts/AuthContext';
import { Zap, Mail, Lock, ArrowRight, User, Shield, Loader2, AlertCircle, CheckCircle } from 'lucide-react';
import Link from 'next/link';

// ── Password rules — must match backend RegisterRequest validator exactly ──────
function validatePassword(password: string): string | null {
  if (password.length < 8) return 'Password must be at least 8 characters.'
  if (!password.split('').some(c => c >= 'A' && c <= 'Z' || c >= 'À' && c <= 'Ö'))
    return 'Password must contain at least one uppercase letter.'
  if (!password.split('').some(c => c >= 'a' && c <= 'z' || c >= 'à' && c <= 'ö'))
    return 'Password must contain at least one lowercase letter.'
  if (!/\d/.test(password)) return 'Password must contain at least one number.'
  return null
}

// Small helper to show per-rule status
function PwdRule({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: ok ? '#16A34A' : '#9CA3AF' }}>
      <CheckCircle size={12} style={{ flexShrink: 0, opacity: ok ? 1 : 0.35 }} />
      {label}
    </div>
  )
}

function SignupForm() {
  const { register } = useAuth();
  const router = useRouter();
  const [name, setName] = React.useState('');
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [pwdFocused, setPwdFocused] = React.useState(false);
  const [error, setError] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);

  // Live password rule checks
  const hasUpper = /[A-Z]/.test(password)
  const hasLower = /[a-z]/.test(password)
  const hasDigit = /\d/.test(password)
  const hasLength = password.length >= 8
  const showRules = pwdFocused && password.length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (name.trim().length < 2) { setError('Please enter your full name.'); return; }
    if (!email.includes('@')) { setError('Please enter a valid email.'); return; }

    // Client-side password check — same rules as backend
    const pwdError = validatePassword(password)
    if (pwdError) { setError(pwdError); return; }

    setSubmitting(true);
    try {
      await register({
        email: email.trim().toLowerCase(),
        password,
        name: name.trim(),
        role: 'homeowner',
      });
      // Backend sends OTP on register → go to verification page
      router.push('/verify-email');
    } catch (err: any) {
      // AuthContext now surfaces the real Pydantic error message
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-white rounded-3xl sm:rounded-[3rem] p-6 sm:p-10 space-y-6" style={{ border: '1px solid #E8D9B0', boxShadow: '0 20px 60px rgba(7,29,54,0.12)' }}>
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-[#071D36] flex items-center justify-center">
          <Zap className="w-8 h-8 fill-current text-[#D4AA3A]" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold text-[#071D36]">Get started</h1>
        <p className="text-gray-500 text-center text-sm">
          Post a job and get matched with verified tradies.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 p-3 rounded-xl text-sm font-medium flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Full name */}
        <div className="space-y-2">
          <label className="text-sm font-bold text-gray-700 ml-1">Full Name</label>
          <div className="relative">
            <User className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Smith"
              className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-12 py-4 focus:outline-none focus:ring-2 focus:ring-[#D4AA3A]/20 focus:border-[#D4AA3A]/40 transition-all"
            />
          </div>
        </div>

        {/* Email */}
        <div className="space-y-2">
          <label className="text-sm font-bold text-gray-700 ml-1">Email Address</label>
          <div className="relative">
            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-12 py-4 focus:outline-none focus:ring-2 focus:ring-[#D4AA3A]/20 focus:border-[#D4AA3A]/40 transition-all"
            />
          </div>
        </div>

        {/* Password */}
        <div className="space-y-2">
          <label className="text-sm font-bold text-gray-700 ml-1">Password</label>
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onFocus={() => setPwdFocused(true)}
              onBlur={() => setPwdFocused(false)}
              placeholder="Min 8 chars, uppercase, number"
              className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-12 py-4 focus:outline-none focus:ring-2 focus:ring-[#D4AA3A]/20 focus:border-[#D4AA3A]/40 transition-all"
            />
          </div>

          {/* Live password rules — shown while typing */}
          {showRules && (
            <div className="pt-1 pl-1 grid grid-cols-2 gap-1">
              <PwdRule ok={hasLength} label="8+ characters" />
              <PwdRule ok={hasUpper} label="Uppercase letter" />
              <PwdRule ok={hasLower} label="Lowercase letter" />
              <PwdRule ok={hasDigit} label="Number (0–9)" />
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-[#071D36] text-white py-4 rounded-2xl font-bold hover:bg-[#0E2E55] transition-colors flex items-center justify-center gap-2 shadow-lg shadow-[#071D36]/20 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {submitting
            ? <><Loader2 className="w-5 h-5 animate-spin" /> Creating account…</>
            : <><ArrowRight className="w-5 h-5" /> Create Account</>
          }
        </button>
      </form>

      <div className="space-y-3 pt-1">
        <p className="text-center text-sm text-gray-500">
          Already have an account?{' '}
          <Link href="/login" className="text-[#D4AA3A] font-bold hover:underline">Sign In</Link>
        </p>
        <div className="pt-2 border-t border-gray-100 space-y-1.5">
          <div className="flex items-center justify-center gap-2">
            <Shield className="w-4 h-4 text-gray-300" />
            <p className="text-xs text-gray-400">
              Tradesperson?{' '}
              <Link href="/tradie/onboarding" className="text-[#D4AA3A] font-bold hover:underline">Join as a tradie</Link>
            </p>
          </div>
          <div className="flex items-center justify-center gap-2">
            <Shield className="w-4 h-4 text-gray-300" />
            <p className="text-xs text-gray-400">
              Already a tradie?{' '}
              <Link href="/tradie/login" className="text-[#D4AA3A] font-bold hover:underline">Tradie sign in</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-6" style={{ background: '#FFF8E7' }}>
      <Suspense fallback={<div className="text-[#D4AA3A] font-bold">Loading...</div>}>
        <SignupForm />
      </Suspense>
    </div>
  );
}
