"use client";

import React from 'react';
import Link from 'next/link';
import { Zap, CheckCircle2, ArrowRight, Search, ShieldCheck, MessageSquare } from 'lucide-react';

export default function HowItWorksPage() {
  return (
    <div className="min-h-screen bg-brand-cream font-sans">
      <nav className="bg-white border-b border-gray-100 sticky top-0 z-[100]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-brand-terracotta flex items-center justify-center text-white">
              <Zap className="w-5 h-5 fill-current" />
            </div>
            <span className="text-xl font-bold tracking-tight text-brand-terracotta">ProConnect</span>
          </Link>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">How ProConnect Works</h1>
          <p className="text-xl text-gray-600">The simplest way to get your home projects done by professionals.</p>
        </div>

        <div className="space-y-12">
          {[
            {
              step: "01",
              title: "Describe your project",
              description: "Use our AI assistant or browse manually to tell us what you need. From plumbing to electrical, we've got you covered.",
              icon: <MessageSquare className="w-6 h-6" />
            },
            {
              step: "02",
              title: "Get matched with experts",
              description: "We'll match you with top-rated, verified tradies in your area who are available to take on your job.",
              icon: <Search className="w-6 h-6" />
            },
            {
              step: "03",
              title: "Review and book",
              description: "Check profiles, read verified reviews, and book your preferred tradie instantly through our secure platform.",
              icon: <CheckCircle2 className="w-6 h-6" />
            }
          ].map((item, i) => (
            <div key={i} className="flex gap-8 items-start bg-white p-8 rounded-[2.5rem] shadow-sm border border-gray-100">
              <div className="text-4xl font-bold text-brand-terracotta/20">{item.step}</div>
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-brand-terracotta/10 flex items-center justify-center text-brand-terracotta">
                    {item.icon}
                  </div>
                  <h3 className="text-2xl font-bold text-gray-900">{item.title}</h3>
                </div>
                <p className="text-gray-600 leading-relaxed text-lg">{item.description}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-20 bg-brand-terracotta rounded-[3rem] p-12 text-center text-white">
          <h2 className="text-3xl font-bold mb-6">Ready to start your project?</h2>
          <Link href="/signup" className="inline-flex items-center gap-2 bg-white text-brand-terracotta px-8 py-4 rounded-2xl font-bold text-lg hover:bg-opacity-90 transition-all">
            Get Started Now
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </main>
    </div>
  );
}
