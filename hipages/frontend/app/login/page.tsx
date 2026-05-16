"use client";

import React, { Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/src/contexts/AuthContext';
import { Zap, Mail, Lock, ArrowRight, Shield, AlertCircle, Loader2 } from 'lucide-react';
import Link from 'next/link';

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [error, setError] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);

  const returnTo = searchParams.get('returnTo') || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      // No expected_role passed — the backend accepts any valid role.
      // Role-based routing happens silently below; the login page itself
      // never mentions or exposes the existence of an admin panel.
      const user = await login(email.trim().toLowerCase(), password);

      if (user?.role === 'admin') {
        router.push('/admin');
        return;
      }

      if (user?.role === 'tradie') {
        router.push('/tradie/dashboard');
        return;
      }

      // If email not yet verified, send to OTP page first
      if (!user?.email_verified) {
        router.push('/verify-email');
        return;
      }

      router.push(returnTo);
    } catch (err: any) {
      setError(err.message || 'Invalid email or password');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-white rounded-3xl sm:rounded-[2rem] shadow-2xl p-6 sm:p-10 space-y-7 sm:space-y-8" style={{ border: '1px solid #E8D9B0', boxShadow: '0 20px 60px rgba(7,29,54,0.12)' }}>
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-[#071D36] flex items-center justify-center text-brand-gold">
          <Zap className="w-8 h-8 fill-current" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold text-[#071D36]">Welcome back</h1>
        <p className="text-gray-500 text-center">Sign in to your homeowner account</p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-500 p-3 rounded-xl text-sm font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-bold text-[#071D36] ml-1">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#071D36]" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full bg-white border border-[#E8D9B0] rounded-2xl px-12 py-4 focus:outline-none focus:ring-2 focus:ring-brand-gold/25 focus:border-brand-gold transition-all"
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-bold text-[#071D36] ml-1">Password</label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[#071D36]" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-white border border-[#E8D9B0] rounded-2xl px-12 py-4 focus:outline-none focus:ring-2 focus:ring-brand-gold/25 focus:border-brand-gold transition-all"
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-[#071D36] text-white py-4 rounded-2xl font-bold hover:scale-[1.02] hover:bg-[#0E2E55] transition-transform flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
        >
          {submitting
            ? <><Loader2 className="w-5 h-5 animate-spin" /> Signing in…</>
            : <><ArrowRight className="w-5 h-5" /> Sign In</>
          }
        </button>
      </form>

      <div className="pt-3 border-t border-[#D7E4F1]">
        <div className="flex items-center justify-center gap-2">
          <Shield className="w-4 h-4 text-[#071D36]" />
          <Link href="/tradie/login" className="text-sm text-brand-gold font-bold hover:underline">
            Join as tradie
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 sm:p-6" style={{ background: '#FFF8E7' }}>
      <Suspense fallback={<div className="text-brand-gold font-bold">Loading...</div>}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
