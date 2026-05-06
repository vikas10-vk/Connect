"use client";

import React, { Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/src/contexts/AuthContext';
import { Zap, Mail, Lock, ArrowRight, Shield, AlertCircle } from 'lucide-react';
import Link from 'next/link';

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [error, setError] = React.useState('');
  const [submitting, setSubmitting] = React.useState(false);

  const sessionExpired = searchParams.get('session') === 'expired';
  const returnTo = searchParams.get('returnTo') || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const user = await login(email, password, 'homeowner');
      // If the user is a tradie, send them to /tradie/login next time.
      // For this attempt, route them to their dashboard.
      if (user?.role === 'tradie') {
        router.push('/tradie/dashboard');
      } else {
        router.push(returnTo);
      }
    } catch (err: any) {
      setError(err.message || 'Invalid email or password');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md bg-white rounded-3xl sm:rounded-[3rem] shadow-2xl p-6 sm:p-10 space-y-7 sm:space-y-8 border border-[#E9DDBF]">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 rounded-2xl bg-[#071D36] flex items-center justify-center text-brand-gold">
          <Zap className="w-8 h-8 fill-current" />
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold text-[#071D36]">Welcome back</h1>
        <p className="text-gray-500 text-center">Sign in to your homeowner account</p>
      </div>

      {sessionExpired && (
        <div className="bg-amber-50 text-amber-700 p-3 rounded-xl text-sm font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          Your session expired. Please sign in again.
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-500 p-3 rounded-xl text-sm font-medium flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="space-y-4">
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
                className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-12 py-4 focus:outline-none focus:ring-2 focus:ring-brand-gold/20 transition-all"
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-700 ml-1">Password</label>
            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-gray-50 border border-gray-100 rounded-2xl px-12 py-4 focus:outline-none focus:ring-2 focus:ring-brand-gold/20 transition-all"
              />
            </div>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-[#071D36] text-white py-4 rounded-2xl font-bold hover:scale-[1.02] hover:bg-[#0E2E55] transition-transform flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100"
        >
          {submitting ? 'Signing in…' : <>Sign In <ArrowRight className="w-5 h-5" /></>}
        </button>
      </form>

      <div className="space-y-3">
        <p className="text-center text-sm text-gray-500">
          Don't have an account?{' '}
          <Link href="/signup" className="text-brand-gold font-bold hover:underline">
            Sign Up
          </Link>
        </p>

        <div className="pt-3 border-t border-gray-100 space-y-1.5">
          <div className="flex items-center justify-center gap-2">
            <Shield className="w-4 h-4 text-gray-400" />
            <p className="text-xs text-gray-500">
              Tradesperson signing in?{' '}
              <Link href="/tradie/login" className="text-brand-gold font-bold hover:underline">
                Tradie sign in
              </Link>
            </p>
          </div>
          <div className="flex items-center justify-center gap-2">
            <Shield className="w-4 h-4 text-gray-400" />
            <p className="text-xs text-gray-500">
              New tradie?{' '}
              <Link href="/tradie/onboarding" className="text-brand-gold font-bold hover:underline">
                Join as a tradie
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-brand-ivory flex items-center justify-center p-4 sm:p-6">
      <Suspense fallback={<div className="text-brand-gold font-bold">Loading...</div>}>
        <LoginForm />
      </Suspense>
    </div>
  );
}
