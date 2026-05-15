"use client";

import React, { useState, useEffect, useCallback, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Search, MapPin, Star, Filter, Zap, ChevronRight,
  LogOut, CheckCircle2,
  Loader2, AlertCircle, SlidersHorizontal, X
} from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';
import { cn } from '@/src/lib/utils';
import { TRADIE_CATEGORIES } from '@/src/constants/categories';
import api from '@/src/lib/api';

interface Tradie {
  id: string;
  business_name: string;
  suburb: string;
  state: string;
  radius_km: number;
  is_available: boolean;
  bio?: string;
  avatar_url?: string;
  rating?: number;
  review_count?: number;
  categories?: string[];
}

// ─────────────────────────────────────────────────────────────────────────────
// SearchPageContent — the real component.
// Must NOT be the default export because useSearchParams() requires
// this component to be wrapped in <Suspense> before Next.js can
// statically generate the page shell.
// ─────────────────────────────────────────────────────────────────────────────
function SearchPageContent() {
  const { isAuthenticated, logout, user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [tradies, setTradies] = useState<Tradie[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [suburb, setSuburb] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(
    searchParams.get('category') || ''
  );
  const [showFilters, setShowFilters] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);

  const fetchTradies = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (selectedCategory) params.category_slug = selectedCategory.toLowerCase().replace(/ /g, '-');
      if (suburb) params.suburb = suburb;
      const res = await api.get('/tradies/', { params });
      const data = res.data;
      setTradies(Array.isArray(data) ? data : data.tradies || []);
    } catch (err) {
      console.error('[Search] fetch failed:', err);
      setError('Could not load tradies. Please try again.');
      setTradies([]);
    } finally {
      setIsLoading(false);
    }
  }, [selectedCategory, suburb]);

  useEffect(() => { fetchTradies(); }, [fetchTradies]);

  useEffect(() => {
    if (!searchQuery) { setSuggestions([]); return; }
    setSuggestions(
      TRADIE_CATEGORIES.filter(c =>
        c.toLowerCase().includes(searchQuery.toLowerCase())
      ).slice(0, 6)
    );
  }, [searchQuery]);

  const handleCategorySelect = (cat: string) => {
    setSelectedCategory(cat);
    setSearchQuery('');
    setSuggestions([]);
  };

  const clearCategory = () => {
    setSelectedCategory('');
    setSearchQuery('');
  };

  const handleBookNow = (tradie: Tradie) => {
    const params = new URLSearchParams();
    if (selectedCategory) params.set('category', selectedCategory);
    params.set('tradie_id', tradie.id);
    params.set('tradie_name', tradie.business_name);
    router.push(`/book?${params.toString()}`);
  };

  const dashboardHref = user?.role === 'tradie' ? '/tradie/dashboard' : '/dashboard';

  return (
    <div className="min-h-screen font-sans" style={{ background: '#FFF8E7' }}>

      {/* ── Navigation ─────────────────────────────────────────────────────── */}
      <nav className="bg-[#071D36] border-b border-white/10 sticky top-0 z-[100]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex flex-wrap lg:flex-nowrap justify-between items-center gap-3 sm:gap-4">

          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 shrink-0 group">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center transition-transform group-hover:scale-105" style={{ background: '#D4AA3A', boxShadow: '0 3px 10px rgba(212,170,58,0.3)' }}>
              <Zap className="w-5 h-5 fill-current" style={{ color: '#071D36' }} />
            </div>
            <span className="text-xl font-bold tracking-tight hidden sm:block" style={{ color: '#D4AA3A' }}>ProConnect</span>
          </Link>

          {/* Search bar */}
          <div className="order-3 lg:order-none basis-full lg:basis-auto flex-1 max-w-none lg:max-w-2xl relative">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 bg-white px-4 py-2.5 rounded-2xl border border-white/30 focus-within:border-brand-gold/60 focus-within:ring-2 focus-within:ring-brand-gold/10 transition-all">
              <Search className="w-4 h-4 text-gray-400 shrink-0" />
              <input
                type="text"
                placeholder={selectedCategory || "Search for a trade..."}
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                className="bg-transparent flex-1 focus:outline-none text-sm min-w-0"
              />
              {selectedCategory && (
                <button onClick={clearCategory} className="shrink-0">
                  <X className="w-4 h-4 text-gray-400 hover:text-gray-600" />
                </button>
              )}
              <div className="hidden sm:block w-px h-5 bg-gray-200 shrink-0" />
              <MapPin className="w-4 h-4 text-gray-400 shrink-0" />
              <input
                type="text"
                placeholder="Suburb"
                value={suburb}
                onChange={e => setSuburb(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && fetchTradies()}
                className="bg-transparent w-full sm:w-24 focus:outline-none text-sm"
              />
            </div>

            {suggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-2 bg-white border border-gray-100 rounded-2xl shadow-2xl z-50 overflow-hidden py-1">
                {suggestions.map(cat => (
                  <button
                    key={cat}
                    onClick={() => handleCategorySelect(cat)}
                    className="w-full text-left px-5 py-3 hover:bg-brand-ivory transition-colors text-sm font-medium flex items-center justify-between group"
                  >
                    {cat}
                    <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-brand-gold transition-colors" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* ── Auth area ── */}
          <div className="flex items-center gap-3 shrink-0">
            {!isAuthenticated ? (
              <>
                <Link
                  href="/login"
                  className="text-white/80 font-bold text-sm hover:text-brand-gold transition-opacity hidden sm:block"
                >
                  Login
                </Link>
                <Link
                  href="/signup"
                  className="bg-brand-gold text-[#071D36] px-4 py-2 rounded-xl font-bold text-sm hover:bg-[#E8C766] hover:shadow-lg hover:shadow-brand-gold/20 transition-all"
                >
                  Sign Up
                </Link>
              </>
            ) : (
              <div className="flex items-center gap-3">
                <Link href={dashboardHref} className="flex items-center gap-2.5 group">
                  <div className="w-9 h-9 rounded-full font-black text-sm shadow-md transition-all flex items-center justify-center" style={{ background: '#D4AA3A', color: '#071D36', boxShadow: '0 3px 10px rgba(212,170,58,0.3)' }}>
                    {(user?.name || user?.email || 'U').slice(0, 1).toUpperCase()}
                  </div>
                  <div className="hidden sm:block">
                    <p className="text-xs font-black text-white leading-none truncate max-w-[90px]">
                      {user?.name?.split(' ')[0] || user?.email?.split('@')[0]}
                    </p>
                    <p className="text-[10px] font-bold mt-0.5" style={{ color: '#D4AA3A' }}>Dashboard →</p>
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
            )}
          </div>

        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8 flex flex-col lg:flex-row gap-6 lg:gap-8">

        {/* ── Sidebar filters ───────────────────────────────────────────────── */}
        <aside className={cn("w-56 shrink-0 space-y-6", "hidden lg:block")}>
          <div className="bg-white rounded-2xl p-5 space-y-4" style={{ border: '1px solid #E8D9B0' }}>
            <h3 className="font-bold text-sm flex items-center gap-2" style={{ color: '#071D36' }}>
              <SlidersHorizontal className="w-4 h-4" style={{ color: '#5BB3FF' }} />
              Categories
            </h3>
            <div className="space-y-1 max-h-96 overflow-y-auto pr-1">
              <button
                onClick={() => setSelectedCategory('')}
                className={cn(
                  "w-full text-left px-3 py-2 rounded-xl text-sm font-medium transition-colors",
                  !selectedCategory
                    ? "bg-brand-gold/10 text-brand-gold font-bold"
                    : "text-gray-600 hover:bg-gray-50 hover:text-brand-gold"
                )}
              >
                All Trades
              </button>
              {TRADIE_CATEGORIES.map(cat => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={cn(
                    "w-full text-left px-3 py-2 rounded-xl text-sm font-medium transition-colors",
                    selectedCategory === cat
                      ? "bg-brand-gold/10 text-brand-gold font-bold"
                      : "text-gray-600 hover:bg-gray-50 hover:text-brand-gold"
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>
        </aside>

        {/* ── Results ────────────────────────────────────────────────────────── */}
        <main className="flex-1 space-y-5 min-w-0">

          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <h2 className="text-lg sm:text-xl font-bold text-gray-900">
              {isLoading ? 'Finding tradies...' : (
                <>
                  {tradies.length} tradie{tradies.length !== 1 ? 's' : ''} found
                  {selectedCategory && <span className="text-brand-gold"> · {selectedCategory}</span>}
                  {suburb && <span className="text-gray-500"> near {suburb}</span>}
                </>
              )}
            </h2>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="lg:hidden flex items-center gap-2 text-sm font-bold text-gray-700 bg-white border border-gray-100 px-4 py-2 rounded-xl"
            >
              <Filter className="w-4 h-4" />
              Filter
            </button>
          </div>

          {/* Active category chip */}
          {selectedCategory && (
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-2 bg-brand-gold/10 text-brand-gold text-sm font-bold px-4 py-2 rounded-full">
                {selectedCategory}
                <button onClick={clearCategory}>
                  <X className="w-3.5 h-3.5" />
                </button>
              </span>
            </div>
          )}

          {showFilters && (
            <div className="lg:hidden bg-white rounded-2xl p-4 border border-[#E9DDBF] shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-bold text-[#071D36] text-sm flex items-center gap-2">
                  <SlidersHorizontal className="w-4 h-4" />
                  Categories
                </h3>
                <button onClick={() => setShowFilters(false)} className="w-8 h-8 rounded-full bg-brand-ivory flex items-center justify-center">
                  <X className="w-4 h-4 text-gray-500" />
                </button>
              </div>
              <div className="grid grid-cols-2 gap-2 max-h-72 overflow-y-auto pr-1">
                <button
                  onClick={() => { setSelectedCategory(''); setShowFilters(false); }}
                  className={cn(
                    "text-left px-3 py-2 rounded-xl text-xs font-bold transition-colors",
                    !selectedCategory ? "bg-brand-gold/10 text-brand-gold" : "bg-brand-ivory text-gray-600"
                  )}
                >
                  All Trades
                </button>
                {TRADIE_CATEGORIES.map(cat => (
                  <button
                    key={cat}
                    onClick={() => { setSelectedCategory(cat); setShowFilters(false); }}
                    className={cn(
                      "text-left px-3 py-2 rounded-xl text-xs font-bold transition-colors",
                      selectedCategory === cat ? "bg-brand-gold/10 text-brand-gold" : "bg-brand-ivory text-gray-600"
                    )}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="flex items-center gap-3 bg-red-50 border border-red-100 text-red-700 px-5 py-4 rounded-2xl text-sm">
              <AlertCircle className="w-5 h-5 shrink-0" />
              {error}
              <button onClick={fetchTradies} className="ml-auto font-bold underline">Retry</button>
            </div>
          )}

          {/* Loading skeletons */}
          {isLoading && (
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="bg-white rounded-3xl p-6 border border-gray-100 animate-pulse">
                  <div className="flex gap-5">
                    <div className="w-24 h-24 bg-gray-100 rounded-2xl shrink-0" />
                    <div className="flex-1 space-y-3 pt-1">
                      <div className="h-5 bg-gray-100 rounded-full w-1/3" />
                      <div className="h-4 bg-gray-100 rounded-full w-1/4" />
                      <div className="h-4 bg-gray-100 rounded-full w-2/3" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Empty state */}
          {!isLoading && !error && tradies.length === 0 && (
            <div className="bg-white rounded-3xl p-8 sm:p-16 text-center border border-gray-100">
              <div className="w-14 h-14 bg-brand-ivory rounded-2xl flex items-center justify-center mx-auto mb-4">
                <Search className="w-7 h-7 text-brand-gold" />
              </div>
              <h3 className="font-bold text-gray-900 mb-2">No tradies found</h3>
              <p className="text-gray-500 text-sm mb-6">
                Try a different category or suburb, or post a job and let tradies come to you.
              </p>
              <button
                onClick={() => router.push('/book')}
                className="bg-brand-gold text-white px-6 py-3 rounded-xl font-bold text-sm hover:shadow-lg hover:shadow-brand-gold/20 transition-all"
              >
                Post a Job Instead
              </button>
            </div>
          )}

          {/* Tradie cards */}
          {!isLoading && tradies.map(tradie => (
            <div
              key={tradie.id}
              className="bg-white rounded-3xl border border-gray-100 hover:border-brand-gold/20 hover:shadow-xl transition-all duration-300 overflow-hidden"
            >
              <div className="p-5 sm:p-6 flex flex-col sm:flex-row gap-4 sm:gap-5">
                {/* Avatar */}
                <div className="w-20 h-20 rounded-2xl bg-brand-ivory flex items-center justify-center shrink-0 overflow-hidden border border-gray-100">
                  {tradie.avatar_url ? (
                    <img src={tradie.avatar_url} alt={tradie.business_name} className="w-full h-full object-cover" />
                  ) : (
                    <span className="text-2xl font-black text-brand-gold">
                      {(tradie.business_name || '?')[0].toUpperCase()}
                    </span>
                  )}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-bold text-gray-900 text-lg truncate">{tradie.business_name}</h3>
                        {tradie.is_available && (
                          <span className="inline-flex items-center gap-1 text-xs bg-green-50 text-green-700 px-2.5 py-0.5 rounded-full font-bold shrink-0">
                            <CheckCircle2 className="w-3 h-3" />
                            Available
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 mt-1 flex-wrap">
                        <span className="flex items-center gap-1 text-sm text-gray-500">
                          <MapPin className="w-3.5 h-3.5" />
                          {tradie.suburb}, {tradie.state}
                        </span>
                        {tradie.radius_km && (
                          <span className="text-sm text-gray-400">· {tradie.radius_km}km radius</span>
                        )}
                      </div>
                    </div>

                    {tradie.rating && (
                      <div className="flex items-center gap-1.5 bg-brand-ivory px-3 py-1.5 rounded-full shrink-0">
                        <Star className="w-4 h-4 text-brand-gold fill-brand-gold" />
                        <span className="font-bold text-sm text-brand-gold">{tradie.rating.toFixed(1)}</span>
                        {tradie.review_count && (
                          <span className="text-xs text-gray-400">({tradie.review_count})</span>
                        )}
                      </div>
                    )}
                  </div>

                  {tradie.bio && (
                    <p className="text-sm text-gray-500 mt-2 line-clamp-2 leading-relaxed">{tradie.bio}</p>
                  )}

                  <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 mt-4">
                    <button
                      onClick={() => handleBookNow(tradie)}
                      className="bg-[#071D36] text-white px-5 py-2.5 rounded-xl font-bold text-sm hover:shadow-lg hover:shadow-[#071D36]/20 hover:-translate-y-0.5 transition-all"
                    >
                      Get a Quote
                    </button>
                    <button
                      onClick={() => handleBookNow(tradie)}
                      className="text-brand-gold font-bold text-sm hover:opacity-80 transition-opacity flex items-center gap-1"
                    >
                      View Profile
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}

          {/* Post job CTA */}
          {!isLoading && tradies.length > 0 && (
            <div className="bg-gray-900 rounded-3xl p-8 flex flex-col sm:flex-row items-center justify-between gap-6">
              <div>
                <h3 className="font-bold text-white text-lg">Can't find what you need?</h3>
                <p className="text-gray-400 text-sm mt-1">Post a job and let verified tradies come to you.</p>
              </div>
              <button
                onClick={() => router.push('/book')}
                className="bg-brand-gold text-white px-6 py-3 rounded-xl font-bold text-sm hover:shadow-xl hover:shadow-brand-gold/30 hover:-translate-y-0.5 transition-all shrink-0 whitespace-nowrap"
              >
                Post a Job Free
              </button>
            </div>
          )}

        </main>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// SearchPage — the exported page.
// Wraps SearchPageContent in <Suspense> so Next.js 15 can statically
// generate the page shell without hitting the useSearchParams() error.
// The Loader2 spinner shows during the server-side pre-render pass,
// then SearchPageContent hydrates on the client with full functionality.
// ─────────────────────────────────────────────────────────────────────────────
export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-screen bg-brand-ivory">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      }
    >
      <SearchPageContent />
    </Suspense>
  );
}
