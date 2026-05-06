"use client";

import React from 'react';
import Link from 'next/link';
import { Send, Plus, History, LayoutGrid } from 'lucide-react';
import { cn } from '@/src/lib/utils';

export default function Quotes() {
  return (
    <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <nav className="sticky top-0 z-[100] -mx-4 md:mx-0 bg-[#0A0A0B]/95 backdrop-blur-md border-b border-white/10 px-4 md:px-0 py-3">
        <div className="flex items-center justify-between gap-3">
          <Link href="/tradie/dashboard" className="inline-flex items-center gap-2 text-[#1DE9B6] font-black text-xs uppercase tracking-[0.18em]">
            <LayoutGrid className="w-4 h-4" />
            Dashboard
          </Link>
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Quotes</span>
        </div>
      </nav>

      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="space-y-1">
          <h1 className="text-4xl font-black tracking-tighter text-white uppercase">Quotes</h1>
          <p className="text-gray-500 font-bold text-base">Track and manage your sent proposals.</p>
        </div>
        <button className="bg-tradie-accent text-tradie-dark px-10 py-5 rounded-2xl font-black text-xs uppercase tracking-[0.2em] flex items-center gap-3 hover:scale-105 transition-transform shadow-2xl shadow-tradie-accent/30">
          <Plus className="w-5 h-5" />
          <span>Create Quote</span>
        </button>
      </header>

      <div className="bg-tradie-card rounded-[3rem] p-24 flex flex-col items-center justify-center text-center space-y-8 border-2 border-dashed border-white/5 shadow-2xl">
        <div className="w-24 h-24 rounded-[2.5rem] bg-white/5 flex items-center justify-center text-white/10">
          <Send className="w-12 h-12" />
        </div>
        <div className="space-y-3">
          <h3 className="text-3xl font-black text-gray-400 tracking-tight uppercase">No quotes sent yet</h3>
          <p className="text-gray-500 font-bold max-w-xs mx-auto leading-relaxed">Send professional quotes to your leads to start winning more high-value jobs.</p>
        </div>
        <button className="px-8 py-4 rounded-2xl bg-white/5 text-gray-400 font-black text-xs uppercase tracking-[0.2em] hover:bg-white/10 transition-all">
          View Quote History
        </button>
      </div>
    </div>
  );
}
