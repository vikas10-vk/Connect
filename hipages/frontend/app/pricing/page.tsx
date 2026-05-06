"use client";

import React from 'react';
import Link from 'next/link';
import { Zap, CheckCircle2, ArrowRight, ShieldCheck, Star, Users } from 'lucide-react';

export default function PricingPage() {
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

      <main className="max-w-7xl mx-auto px-6 py-20">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">Simple, Transparent Pricing</h1>
          <p className="text-xl text-gray-600">Choose the plan that's right for your business.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 max-w-5xl mx-auto">
          {/* Homeowner Plan */}
          <div className="bg-white p-12 rounded-[3rem] shadow-sm border border-gray-100 space-y-8 relative overflow-hidden">
            <div className="space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-brand-terracotta/10 flex items-center justify-center text-brand-terracotta">
                <Users className="w-6 h-6" />
              </div>
              <h2 className="text-3xl font-bold text-gray-900">For Homeowners</h2>
              <div className="text-5xl font-bold text-brand-terracotta">Free</div>
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

            <Link href="/signup?role=homeowner" className="block text-center bg-brand-terracotta text-white py-4 rounded-2xl font-bold text-lg hover:bg-opacity-90 transition-all">
              Join as Homeowner
            </Link>
          </div>

          {/* Tradie Plan */}
          <div className="bg-gray-900 p-12 rounded-[3rem] shadow-2xl space-y-8 relative overflow-hidden text-white">
            <div className="absolute top-0 right-0 bg-brand-terracotta px-6 py-2 rounded-bl-3xl font-bold text-sm">MOST POPULAR</div>
            <div className="space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-brand-terracotta flex items-center justify-center text-white">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h2 className="text-3xl font-bold">For Tradies</h2>
              <div className="flex items-baseline gap-2">
                <span className="text-5xl font-bold text-brand-terracotta">$49</span>
                <span className="text-gray-400">/month</span>
              </div>
              <p className="text-gray-400">Grow your business with premium leads and tools.</p>
            </div>

            <ul className="space-y-4">
              {[
                "Verified tradie badge",
                "Priority lead matching",
                "Business dashboard and tools",
                "Customer review management",
                "Premium support and resources"
              ].map((feature, i) => (
                <li key={i} className="flex items-center gap-3 text-gray-300">
                  <CheckCircle2 className="w-5 h-5 text-brand-terracotta" />
                  {feature}
                </li>
              ))}
            </ul>

            <Link href="/signup?role=tradie" className="block text-center bg-brand-terracotta text-white py-4 rounded-2xl font-bold text-lg hover:bg-opacity-90 transition-all">
              Join as Tradie
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
