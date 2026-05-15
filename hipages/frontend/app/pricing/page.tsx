"use client";

import React from 'react';
import Link from 'next/link';
import { Zap, CheckCircle2, ArrowRight, ShieldCheck, Star, Users } from 'lucide-react';

export default function PricingPage() {
  return (
    <div className="min-h-screen font-sans" style={{ background: '#FFF8E7' }}>
      {/* Navy navbar — consistent with rest of site */}
      <nav className="sticky top-0 z-[100] shadow-lg" style={{ background: '#071D36', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex justify-between items-center">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-md transition-transform group-hover:scale-105" style={{ background: '#D4AA3A', boxShadow: '0 4px 12px rgba(212,170,58,0.3)' }}>
              <Zap className="w-5 h-5 fill-current" style={{ color: '#071D36' }} />
            </div>
            <span className="text-xl font-black tracking-tight" style={{ color: '#D4AA3A' }}>ProConnect</span>
          </Link>
          <div className="flex items-center gap-5">
            <Link href="/login" className="text-sm font-semibold transition-colors" style={{ color: 'rgba(255,255,255,0.75)' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.75)')}>Sign in</Link>
            <Link href="/signup" className="px-5 py-2 rounded-xl font-bold text-sm transition-all" style={{ background: '#D4AA3A', color: '#071D36' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#E8C766')}
              onMouseLeave={e => (e.currentTarget.style.background = '#D4AA3A')}>Get Started</Link>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">Simple, Transparent Pricing</h1>
          <p className="text-xl text-gray-600">Choose the plan that's right for your business.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 max-w-5xl mx-auto">
          {/* Homeowner Plan */}
          <div className="bg-white p-12 rounded-[3rem] shadow-sm space-y-8 relative overflow-hidden" style={{ border: '1px solid #E8D9B0' }}>
            <div className="space-y-4">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: 'rgba(91,179,255,0.12)' }}>
                <Users className="w-6 h-6" style={{ color: '#5BB3FF' }} />
              </div>
              <h2 className="text-3xl font-bold" style={{ color: '#071D36' }}>For Homeowners</h2>
              <div className="text-5xl font-bold" style={{ color: '#D4AA3A' }}>Free</div>
              <p className="text-gray-500">Always free for homeowners to find and book tradies.</p>
            </div>

            <ul className="space-y-4">
              {[
                "Unlimited tradie searches",
                "AI-powered project matching",
                "Verified reviews and ratings",
                "Secure booking and payments",
                "24/7 customer support"
              ].map((feature, i) => (
                <li key={i} className="flex items-center gap-3 text-gray-600">
                  <CheckCircle2 className="w-5 h-5 text-green-500" />
                  {feature}
                </li>
              ))}
            </ul>

            <Link href="/signup?role=homeowner" className="block text-center py-4 rounded-2xl font-bold text-lg transition-all" style={{ background: '#071D36', color: '#fff' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#0D2544')}
              onMouseLeave={e => (e.currentTarget.style.background = '#071D36')}>
              Join as Homeowner
            </Link>
          </div>

          {/* Tradie Plan */}
          <div className="p-12 rounded-[3rem] shadow-2xl space-y-8 relative overflow-hidden text-white" style={{ background: '#071D36' }}>
            <div className="absolute top-0 right-0 px-6 py-2 rounded-bl-3xl font-bold text-sm" style={{ background: '#D4AA3A', color: '#071D36' }}>MOST POPULAR</div>
            <div className="space-y-4">
              <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: 'rgba(212,170,58,0.2)' }}>
                <ShieldCheck className="w-6 h-6" style={{ color: '#D4AA3A' }} />
              </div>
              <h2 className="text-3xl font-bold text-white">For Tradies</h2>
              <div className="flex items-baseline gap-2">
                <span className="text-5xl font-bold" style={{ color: '#D4AA3A' }}>$49</span>
                <span style={{ color: 'rgba(255,255,255,0.5)' }}>/month</span>
              </div>
              <p style={{ color: 'rgba(255,255,255,0.6)' }}>Grow your business with premium leads and tools.</p>
            </div>

            <ul className="space-y-4">
              {[
                "Verified tradie badge",
                "Priority lead matching",
                "Business dashboard and tools",
                "Customer review management",
                "Premium support and resources"
              ].map((feature, i) => (
                <li key={i} className="flex items-center gap-3" style={{ color: 'rgba(255,255,255,0.8)' }}>
                  <CheckCircle2 className="w-5 h-5 shrink-0" style={{ color: '#D4AA3A' }} />
                  {feature}
                </li>
              ))}
            </ul>

            <Link href="/signup?role=tradie" className="block text-center py-4 rounded-2xl font-bold text-lg transition-all" style={{ background: '#D4AA3A', color: '#071D36' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#E8C766')}
              onMouseLeave={e => (e.currentTarget.style.background = '#D4AA3A')}>
              Join as Tradie
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
