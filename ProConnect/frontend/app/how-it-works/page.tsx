"use client";

import React from 'react';
import Link from 'next/link';
import { Zap, CheckCircle2, ArrowRight, Search, ShieldCheck, MessageSquare } from 'lucide-react';

export default function HowItWorksPage() {
  return (
    <div className="min-h-screen font-sans" style={{ background: '#FFF8E7' }}>
      {/* Navbar  -  matches site-wide navy */}
      <nav className="sticky top-0 z-[100] shadow-lg" style={{ background: '#071D36', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="max-w-7xl mx-auto px-6 py-3.5 flex justify-between items-center">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-md transition-transform group-hover:scale-105" style={{ background: '#D4AA3A', boxShadow: '0 4px 12px rgba(212,170,58,0.3)' }}>
              <Zap className="w-5 h-5 fill-current" style={{ color: '#071D36' }} />
            </div>
            <span className="text-xl font-black tracking-tight" style={{ color: '#D4AA3A' }}>ProConnect</span>
          </Link>
          <div className="flex items-center gap-6">
            <Link href="/search" className="text-sm font-semibold transition-colors" style={{ color: 'rgba(255,255,255,0.8)' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}>Browse Tradies</Link>
            <Link href="/login" className="text-sm font-semibold transition-colors" style={{ color: 'rgba(255,255,255,0.8)' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}>Sign in</Link>
            <Link href="/signup" className="px-5 py-2 rounded-xl font-bold text-sm transition-all"
              style={{ background: '#D4AA3A', color: '#071D36' }}
              onMouseEnter={e => (e.currentTarget.style.background = '#E8C766')}
              onMouseLeave={e => (e.currentTarget.style.background = '#D4AA3A')}>Get Started</Link>
          </div>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold mb-6" style={{ color: '#071D36' }}>How ProConnect Works</h1>
          <p className="text-xl" style={{ color: '#56677A' }}>The simplest way to get your home projects done by professionals.</p>
        </div>

        <div className="space-y-6">
          {[
            {
              step: "01",
              title: "Describe your project",
              description: "Use our AI assistant or browse manually to tell us what you need. From plumbing to electrical, we've got you covered.",
              icon: <MessageSquare className="w-6 h-6" style={{ color: '#5BB3FF' }} />
            },
            {
              step: "02",
              title: "Get matched with experts",
              description: "We'll match you with top-rated, verified tradies in your area who are available to take on your job.",
              icon: <Search className="w-6 h-6" style={{ color: '#5BB3FF' }} />
            },
            {
              step: "03",
              title: "Review and book",
              description: "Check profiles, read verified reviews, and book your preferred tradie instantly through our secure platform.",
              icon: <CheckCircle2 className="w-6 h-6" style={{ color: '#5BB3FF' }} />
            }
          ].map((item, i) => (
            <div key={i} className="flex gap-8 items-start p-8 rounded-3xl shadow-sm" style={{ background: '#FFFFFF', border: '1px solid #E8D9B0' }}>
              <div className="text-4xl font-bold shrink-0" style={{ color: 'rgba(212,170,58,0.25)' }}>{item.step}</div>
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: 'rgba(91,179,255,0.12)' }}>
                    {item.icon}
                  </div>
                  <h3 className="text-xl font-bold" style={{ color: '#071D36' }}>{item.title}</h3>
                </div>
                <p className="leading-relaxed" style={{ color: '#56677A' }}>{item.description}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-20 rounded-3xl p-12 text-center" style={{ background: '#071D36' }}>
          <h2 className="text-3xl font-bold mb-6" style={{ color: '#D4AA3A' }}>Ready to start your project?</h2>
          <Link href="/signup" className="inline-flex items-center gap-2 px-8 py-4 rounded-2xl font-bold text-lg transition-all"
            style={{ background: '#D4AA3A', color: '#071D36' }}
            onMouseEnter={e => (e.currentTarget.style.background = '#E8C766')}
            onMouseLeave={e => (e.currentTarget.style.background = '#D4AA3A')}>
            Get Started Now
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </main>
    </div>
  );
}
