"use client";

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Zap, Shield, CheckCircle, ArrowRight,
  User, LogOut, LayoutGrid, ChevronRight,
  Search, Users, Clock, FileText, Star,
} from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';
import { motion, AnimatePresence } from 'motion/react';

import { PROBLEM_SUGGESTIONS, detectCategory } from '@/src/constants/problems';

const MARKET_STATS = [
  { icon: Users, value: '48,200+', label: 'active tradies' },
  { icon: Clock, value: '1.8 hrs', label: 'avg first quote' },
  { icon: FileText, value: '3,140', label: 'jobs this week' },
  { icon: Star, value: '96%', label: 'satisfaction' },
];

const CATEGORY_STATS: Record<string, { tradies: number; avgHours: number }> = {
  'plumbing': { tradies: 1840, avgHours: 1.2 },
  'electrical': { tradies: 1530, avgHours: 1.5 },
  'carpentry': { tradies: 920, avgHours: 2.1 },
  'painting': { tradies: 1100, avgHours: 2.8 },
  'landscaping': { tradies: 780, avgHours: 3.2 },
  'roofing': { tradies: 640, avgHours: 2.4 },
  'air conditioning': { tradies: 560, avgHours: 1.8 },
  'tiling': { tradies: 720, avgHours: 2.2 },
  'handyman': { tradies: 1200, avgHours: 1.6 },
  'pest control': { tradies: 480, avgHours: 2.0 },
  'fencing': { tradies: 390, avgHours: 3.0 },
};

function getCategoryStat(category: string) {
  return CATEGORY_STATS[category.toLowerCase()] || null;
}

export default function LandingPage() {
  const { isAuthenticated, logout, user } = useAuth();
  const router = useRouter();

  // ── No auto-redirect on cold landing ─────────────────────────────────────
  // Removed the useEffect that pushed tradies straight to /tradie/dashboard.
  // Logged-in users still see the landing — they can navigate themselves
  // via the Dashboard button in the header.

  const [scrolled, setScrolled] = useState(false);
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<typeof PROBLEM_SUGGESTIONS>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const [activeIdx, setActiveIdx] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', fn);
    return () => window.removeEventListener('scroll', fn);
  }, []);

  useEffect(() => {
    if (query.length < 2) {
      setSuggestions([]);
      setShowDropdown(false);
      setActiveIdx(-1);
      return;
    }
    const q = query.toLowerCase();
    const matches = PROBLEM_SUGGESTIONS.filter(s =>
      s.problem.toLowerCase().includes(q) ||
      s.category.toLowerCase().includes(q)
    ).slice(0, 6);
    setSuggestions(matches);
    setShowDropdown(matches.length > 0);
    setActiveIdx(-1);
  }, [query]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(e.target as Node) &&
        inputRef.current && !inputRef.current.contains(e.target as Node)
      ) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const navigateToBook = (problem: string, category: string) => {
    if (!problem.trim()) { router.push('/book'); return; }
    const cat = category || detectCategory(problem);
    const params = new URLSearchParams({ q: problem });
    if (cat) params.set('category', cat);
    router.push(`/book?${params.toString()}`);
  };

  const handleSearch = () => {
    setShowDropdown(false);
    navigateToBook(query, detectCategory(query));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showDropdown) {
      if (e.key === 'Enter') handleSearch();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIdx(i => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIdx >= 0 && suggestions[activeIdx]) {
        const s = suggestions[activeIdx];
        setQuery(s.problem);
        setShowDropdown(false);
        navigateToBook(s.problem, s.category);
      } else {
        handleSearch();
      }
    } else if (e.key === 'Escape') {
      setShowDropdown(false);
    }
  };

  const handleSuggestionClick = (s: typeof PROBLEM_SUGGESTIONS[0]) => {
    setQuery(s.problem);
    setShowDropdown(false);
    navigateToBook(s.problem, s.category);
  };

  const detectedCategory = detectCategory(query);
  const categoryStat = detectedCategory ? getCategoryStat(detectedCategory) : null;

  const STEPS = [
    { num: '01', title: 'Describe your job', body: 'Type what needs doing in plain language. Our AI reads it and matches the right category automatically.' },
    { num: '02', title: 'AI writes the brief', body: 'Our AI reads your description and writes a professional scope of work tradies can quote from accurately.' },
    { num: '03', title: 'Verified tradies quote', body: 'Only tradies in your area with matching skills receive the job. You get real quotes — not phone spam.' },
    { num: '04', title: 'You decide, they deliver', body: 'Review quotes with full context on each tradie. Accept the one you trust. Done.' },
  ];

  // Where to send the dashboard button if user is already logged in
  const dashboardHref = user?.role === 'tradie' ? '/tradie/dashboard' : '/dashboard';

  return (
    <div className="min-h-screen font-sans overflow-x-hidden" style={{ fontFamily: "'DM Sans', sans-serif", background: '#FFF8E7' }}>

      {/* ── Nav ── */}
      <nav className={`sticky top-0 z-50 transition-all duration-300 bg-[#071D36] ${scrolled ? 'shadow-lg shadow-[#071D36]/10' : ''}`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6">
          <div className="flex items-center justify-between py-3 sm:py-4 gap-3">
            <Link href="/" className="flex items-center gap-2 shrink-0">
              <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-[#D4AA3A] flex items-center justify-center text-[#071D36] shadow-md shadow-[#D4AA3A]/30">
                <Zap className="w-4 h-4 sm:w-5 sm:h-5 fill-current" />
              </div>
              <span className="text-lg sm:text-xl font-black text-[#D4AA3A] tracking-tight">ProConnect</span>
            </Link>

            <div className="hidden md:flex items-center gap-8">
              <Link href="/search" className="text-sm font-semibold transition-colors" style={{ color: 'rgba(255,255,255,0.8)' }}
                onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}>Browse Tradies</Link>
              <Link href="/how-it-works" className="text-sm font-semibold transition-colors" style={{ color: 'rgba(255,255,255,0.8)' }}
                onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}>How it Works</Link>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {!isAuthenticated ? (
                <>
                  {/* Tradie entry — separated visually */}
                  <Link href="/tradie/onboarding"
                    className="hidden md:flex items-center gap-1.5 text-sm font-bold transition-colors px-3 py-2 rounded-xl whitespace-nowrap border-r pr-4"
                    style={{ color: 'rgba(255,255,255,0.75)', borderColor: 'rgba(255,255,255,0.15)' }}
                    onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.75)')}>
                    <Shield className="w-4 h-4" style={{ color: '#5BB3FF' }} /> Join as a Tradie
                  </Link>

                  {/* Homeowner buttons */}
                  <Link href="/login" className="text-sm font-bold transition-colors px-2 sm:px-3 py-2"
                    style={{ color: 'rgba(255,255,255,0.8)' }}
                    onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
                    onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}>Sign in</Link>
                  <Link href="/signup" className="px-3 py-2 sm:px-5 sm:py-2.5 rounded-xl font-bold text-xs sm:text-sm transition-colors whitespace-nowrap"
                    style={{ background: '#D4AA3A', color: '#071D36', boxShadow: '0 4px 12px rgba(212,170,58,0.25)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = '#E8C766')}
                    onMouseLeave={e => (e.currentTarget.style.background = '#D4AA3A')}>
                    Get Started
                  </Link>
                </>
              ) : (
                <div className="flex items-center gap-2">
                  <Link href={dashboardHref}
                    className="hidden sm:flex items-center gap-2 text-sm font-bold transition-opacity hover:opacity-80"
                    style={{ color: '#D4AA3A' }}>
                    <LayoutGrid className="w-4 h-4" style={{ color: '#5BB3FF' }} /> Dashboard
                  </Link>
                  <div className="flex items-center gap-3">
                    {/* Circular avatar with initials */}
                    <Link href={dashboardHref} className="flex items-center gap-2.5 group">
                      <div className="w-9 h-9 rounded-full flex items-center justify-center font-black text-sm shadow-md transition-all"
                        style={{ background: '#D4AA3A', color: '#071D36', boxShadow: '0 4px 12px rgba(212,170,58,0.3)' }}>
                        {(user?.name || user?.email || 'U').slice(0, 1).toUpperCase()}
                      </div>
                      <div className="hidden sm:block">
                        <p className="text-xs font-black text-white leading-none truncate max-w-[100px]">
                          {user?.name?.split(' ')[0] || user?.email?.split('@')[0]}
                        </p>
                        <p className="text-[10px] font-bold mt-0.5" style={{ color: '#D4AA3A' }}>View dashboard →</p>
                      </div>
                    </Link>
                    <button
                      onClick={logout}
                      className="w-8 h-8 rounded-full flex items-center justify-center transition-all"
                      style={{ background: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.5)', border: '1px solid rgba(255,255,255,0.12)' }}
                      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,80,80,0.15)'; e.currentTarget.style.color = '#FF6B6B'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.1)'; e.currentTarget.style.color = 'rgba(255,255,255,0.5)'; }}
                      title="Sign out"
                    >
                      <LogOut className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Mobile row 2 */}
          <div className="flex md:hidden items-center gap-1 pb-2 overflow-x-auto -mx-1 px-1">
            <Link href="/search" className="text-xs font-semibold whitespace-nowrap px-3 py-1.5 rounded-lg transition-colors"
              style={{ color: 'rgba(255,255,255,0.75)' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.75)')}>Browse Tradies</Link>
            <span className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
            <Link href="/how-it-works" className="text-xs font-semibold whitespace-nowrap px-3 py-1.5 rounded-lg transition-colors"
              style={{ color: 'rgba(255,255,255,0.75)' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.75)')}>How it Works</Link>
            {!isAuthenticated && (
              <>
                <span className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>|</span>
                <Link href="/tradie/onboarding" className="text-xs font-semibold whitespace-nowrap px-3 py-1.5 rounded-lg" style={{ color: '#D4AA3A' }}>Join as a Tradie</Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="pt-12 sm:pt-20 pb-12 sm:pb-20 px-4 sm:px-6 max-w-7xl mx-auto text-center">
        <motion.h1
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.08 }}
          className="text-3xl sm:text-5xl lg:text-6xl xl:text-[4.5rem] font-black text-[#071D36] leading-tight tracking-tighter mb-8 sm:mb-10"
        >
          Propel your agenda with skilled support
        </motion.h1>

        <motion.div
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.16 }}
          className="max-w-2xl mx-auto w-full relative"
        >
          <div className="flex flex-row items-center bg-white rounded-full p-2 pl-4 sm:pl-5 shadow-xl shadow-[#D4AA3A]/5 border border-gray-200 hover:border-[#D4AA3A]/30 transition-all">
            <Search className="w-4 h-4 sm:w-5 sm:h-5 text-[#D4AA3A] shrink-0" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
              placeholder="e.g. fix leaking tap, broken fence, no power..."
              className="flex-1 min-w-0 bg-transparent border-none focus:outline-none focus:ring-0 text-sm sm:text-base px-3 sm:px-4 text-gray-800 placeholder-gray-400 py-2"
            />
            {detectedCategory && (
              <span className="hidden sm:flex items-center gap-1 text-[11px] font-bold text-[#D4AA3A] bg-[#D4AA3A]/8 px-2.5 py-1 rounded-full mr-2 whitespace-nowrap">
                {detectedCategory}
              </span>
            )}
            <button
              onClick={handleSearch}
              className="bg-[#071D36] text-white px-4 sm:px-6 py-2.5 sm:py-3 rounded-full font-black text-sm sm:text-base flex items-center gap-2 hover:bg-[#0E2E55] transition-colors whitespace-nowrap shadow-md shadow-[#071D36]/20 shrink-0"
            >
              Find now <ArrowRight className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </button>
          </div>

          <AnimatePresence>
            {showDropdown && suggestions.length > 0 && (
              <motion.div
                ref={dropdownRef}
                initial={{ opacity: 0, y: -4, scale: 0.99 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -4, scale: 0.99 }}
                transition={{ duration: 0.12 }}
                className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-100 rounded-3xl shadow-2xl z-50 overflow-hidden"
              >
                <div className="px-3 pt-3 pb-1">
                  <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wider px-2 mb-2">Common issues — click to get quotes</p>
                </div>
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    onMouseEnter={() => setActiveIdx(i)}
                    onClick={() => handleSuggestionClick(s)}
                    className={`w-full text-left px-5 py-3 flex items-center gap-3 transition-colors ${activeIdx === i ? 'bg-[#D4AA3A]/5' : 'hover:bg-gray-50'}`}
                  >
                    <span className="text-lg shrink-0">{s.icon}</span>
                    <span className="flex-1 text-sm font-semibold text-gray-800">{s.problem}</span>
                    <span className="text-[11px] font-bold text-[#D4AA3A] bg-[#D4AA3A]/8 px-2.5 py-1 rounded-full shrink-0">
                      {s.category}
                    </span>
                    <ArrowRight className="w-3.5 h-3.5 text-gray-300 shrink-0" />
                  </button>
                ))}
                <div className="px-5 py-3 border-t border-gray-50">
                  <button onClick={handleSearch} className="text-xs font-bold text-[#D4AA3A] hover:underline flex items-center gap-1">
                    Search for "{query}" <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="max-w-2xl mx-auto mt-5"
        >
          <div className="backdrop-blur rounded-2xl px-4 py-3 shadow-sm" style={{ background: 'rgba(255,255,255,0.9)', border: '1px solid #E8D9B0' }}>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              {MARKET_STATS.map((stat, i) => (
                <React.Fragment key={stat.label}>
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-lg bg-[#D4AA3A]/8 flex items-center justify-center shrink-0">
                      <stat.icon className="w-3.5 h-3.5 text-[#D4AA3A]" />
                    </div>
                    <div>
                      <p className="text-sm font-black text-[#1C0E06] leading-none">{stat.value}</p>
                      <p className="text-[10px] text-gray-400 font-medium mt-0.5">{stat.label}</p>
                    </div>
                  </div>
                  {i < MARKET_STATS.length - 1 && <div className="h-6 w-px bg-gray-100 hidden sm:block" />}
                </React.Fragment>
              ))}
            </div>

            <AnimatePresence>
              {categoryStat && detectedCategory && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-3 pt-3 border-t border-gray-100 flex items-center gap-2"
                >
                  <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse shrink-0" />
                  <p className="text-xs text-gray-600 font-medium">
                    <span className="font-bold text-[#1C0E06]">{categoryStat.tradies.toLocaleString()} {detectedCategory.toLowerCase()} tradies</span>
                    {' '}active right now · avg first quote in{' '}
                    <span className="font-bold text-[#1C0E06]">{categoryStat.avgHours}h</span>
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </section>

      {/* ── How it works ── */}
      <section className="py-16 sm:py-24 px-4 sm:px-6 max-w-7xl mx-auto">
        <div className="text-center mb-12 sm:mb-16">
          <p className="text-xs font-black text-[#D4AA3A] uppercase tracking-widest mb-3">How it works</p>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-black text-[#1C0E06] tracking-tight">
            Post a job in under 3 minutes.
          </h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {STEPS.map((s, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }} transition={{ delay: i * 0.08 }}
              className="relative bg-white rounded-3xl p-6 sm:p-7 border border-[#D7E4F1] shadow-sm hover:shadow-md hover:border-[#D4AA3A]/40 transition-all">
              <div className="text-4xl sm:text-5xl font-black text-[#D4AA3A]/10 mb-4 leading-none">{s.num}</div>
              <h3 className="text-sm sm:text-base font-black text-gray-900 mb-2">{s.title}</h3>
              <p className="text-sm text-gray-500 leading-relaxed">{s.body}</p>
              {i < STEPS.length - 1 && (
                <div className="hidden lg:flex absolute top-1/2 -right-3 -translate-y-1/2 w-6 h-6 bg-[#D4AA3A]/10 rounded-full items-center justify-center z-10">
                  <ChevronRight className="w-3 h-3 text-[#D4AA3A]" />
                </div>
              )}
            </motion.div>
          ))}
        </div>
        <div className="text-center mt-10">
          <button onClick={() => router.push('/book')}
            className="bg-[#D4AA3A] text-white px-7 sm:px-8 py-3.5 sm:py-4 rounded-2xl font-black text-sm sm:text-base hover:bg-[#B8891D] transition-colors shadow-lg shadow-[#D4AA3A]/20 inline-flex items-center gap-3">
            Post your job now <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>
        </div>
      </section>

      {/* ── Tradie CTA — both Sign in and Join now ── */}
      <section className="py-12 sm:py-20 px-4 sm:px-6">
        <div className="max-w-5xl mx-auto bg-white rounded-3xl sm:rounded-[2rem] p-8 sm:p-12 md:p-16 text-center relative overflow-hidden shadow-2xl shadow-[#071D36]/10 border border-[#D7E4F1]">
          <div className="relative z-10">
            <p className="text-xs font-black text-[#D4AA3A] uppercase tracking-widest mb-4">For tradies</p>
            <h2 className="text-2xl sm:text-3xl md:text-5xl font-black text-[#1C0E06] tracking-tight mb-5 sm:mb-6">
              Grow your business<br />with quality leads.
            </h2>
            <p className="text-gray-600 text-sm sm:text-base md:text-lg mb-8 sm:mb-10 max-w-xl mx-auto leading-relaxed">
              Get matched with homeowners in your area. Verified profiles, clear quotes, no spam.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4 justify-center">
              <Link href="/tradie/onboarding"
                className="bg-[#D4AA3A] text-white px-7 py-3.5 sm:py-4 rounded-2xl font-black text-sm sm:text-base hover:bg-[#B8891D] transition-colors shadow-xl shadow-[#D4AA3A]/20 inline-flex items-center justify-center gap-3">
                Join as a Tradie <ArrowRight className="w-4 h-4 sm:w-5 sm:h-5" />
              </Link>
              <Link href="/tradie/login"
                className="bg-white text-[#D4AA3A] border-2 border-[#D4AA3A] px-7 py-3.5 sm:py-4 rounded-2xl font-bold text-sm sm:text-base hover:bg-[#D4AA3A]/5 transition-colors inline-flex items-center justify-center gap-3">
                Tradie sign in
              </Link>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 mt-7 sm:mt-8">
              {['Free to join', 'Verified network', 'Cancel anytime'].map(t => (
                <div key={t} className="flex items-center gap-1.5 text-gray-500 text-xs sm:text-sm font-medium">
                  <CheckCircle className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-[#D4AA3A] shrink-0" /> {t}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="pt-12 sm:pt-16 pb-8 sm:pb-10 px-4 sm:px-6" style={{ background: '#FFF8E7', borderTop: '1px solid #E8D9B0', color: '#071D36' }}>
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-8 sm:gap-10 mb-10 sm:mb-14">
            <div className="col-span-2 space-y-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-[#D4AA3A] flex items-center justify-center shrink-0">
                  <Zap className="w-4 h-4 sm:w-5 sm:h-5 fill-current text-white" />
                </div>
                <span className="text-lg sm:text-xl font-black tracking-tight text-[#1C0E06]">ProConnect</span>
              </div>
              <p className="text-gray-600 text-sm leading-relaxed max-w-xs">
                Australia's smartest trades marketplace. Post a job, get verified quotes, get it done.
              </p>
              <div className="flex gap-4 pt-1">
                {['Instagram', 'Facebook', 'LinkedIn'].map(s => (
                  <Link key={s} href="#" className="text-xs text-gray-500 hover:text-[#D4AA3A] transition-colors font-semibold">{s}</Link>
                ))}
              </div>
            </div>
            {[
              {
                heading: 'Homeowners', links: [
                  { label: 'Find a Tradie', href: '/search' },
                  { label: 'How it Works', href: '/how-it-works' },
                  { label: 'Sign in', href: '/login' },
                  { label: 'Get started', href: '/signup' },
                ]
              },
              {
                heading: 'Tradies', links: [
                  { label: 'Join the network', href: '/tradie/onboarding' },
                  { label: 'Tradie sign in', href: '/tradie/login' },
                  { label: 'Why ProConnect', href: '/tradie' },
                ]
              },
              {
                heading: 'Company', links: [
                  { label: 'About Us', href: '#' },
                  { label: 'Contact', href: '#' },
                  { label: 'Privacy Policy', href: '#' },
                  { label: 'Terms of Service', href: '#' },
                ]
              },
            ].map(col => (
              <div key={col.heading} className="col-span-1">
                <h4 className="text-[10px] sm:text-xs font-black uppercase tracking-widest text-[#1C0E06] mb-4 sm:mb-5">{col.heading}</h4>
                <ul className="space-y-2.5 sm:space-y-3">
                  {col.links.map(l => (
                    <li key={l.label}><Link href={l.href} className="text-xs sm:text-sm text-gray-600 hover:text-[#D4AA3A] transition-colors font-medium">{l.label}</Link></li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="pt-6 sm:pt-8 border-t border-gray-100 flex flex-col sm:flex-row justify-between items-center gap-3 text-center sm:text-left">
            <p className="text-xs sm:text-sm text-gray-500">© 2026 ProConnect Australia Pty Ltd. All rights reserved.</p>
            <p className="text-xs sm:text-sm text-gray-500">Made for Australian homeowners & tradies.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
