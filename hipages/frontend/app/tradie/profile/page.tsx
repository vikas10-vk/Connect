"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Zap, User, LogOut, Camera, Save, ChevronDown,
  MapPin, Briefcase, Shield, CheckCircle2, Loader2,
  AlertCircle, ArrowLeft
} from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';
import { toast } from 'sonner';
import api from '@/src/lib/api';
import { cn } from '@/src/lib/utils';
import { TRADIE_CATEGORIES } from '@/src/constants/categories';

interface ProfileData {
  business_name: string;
  bio: string;
  suburb: string;
  state: string;
  postcode: string;
  radius_km: number;
  is_available: boolean;
  abn: string;
  avatar_url: string;
}

const AU_STATES = ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT'];

export default function TradieProfile() {
  const { user, logout } = useAuth();
  const router = useRouter();

  const [profile, setProfile] = useState<ProfileData>({
    business_name: '',
    bio: '',
    suburb: '',
    state: '',
    postcode: '',
    radius_km: 25,
    is_available: true,
    abn: '',
    avatar_url: '',
  });
  const [isLoading, setSaving] = useState(false);
  const [isFetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Load existing profile ──────────────────────────────────────────────────
  useEffect(() => {
    async function load() {
      try {
        const res = await api.get(`/tradies/profile/me`);
        const d = res.data;
        setProfile({
          business_name: d.business_name || '',
          bio: d.bio || '',
          suburb: d.suburb || '',
          state: d.state || '',
          postcode: d.postcode || '',
          radius_km: d.radius_km || 25,
          is_available: d.is_available ?? true,
          abn: d.abn || '',
          avatar_url: d.avatar_url || '',
        });
      } catch {
        // New profile — blank fields
      } finally {
        setFetching(false);
      }
    }
    load();
  }, [user?.id]);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.patch('/tradies/profile/me', profile);
      toast.success('Profile saved successfully!');
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to save profile.';
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const field = (key: keyof ProfileData, value: string | number | boolean) => {
    setProfile(prev => ({ ...prev, [key]: value }));
  };

  if (isFetching) {
    return (
      <div className="min-h-screen bg-brand-cream flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-brand-terracotta animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-brand-cream font-sans">

      {/* ── Navigation ────────────────────────────────────────────────────── */}
      <nav className="bg-white/95 backdrop-blur-md border-b border-gray-100 sticky top-0 z-[100] shadow-sm">
        <div className="max-w-5xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/tradie/dashboard')}
              className="flex items-center gap-2 text-gray-500 hover:text-gray-800 transition-colors font-bold text-sm"
            >
              <ArrowLeft className="w-4 h-4" />
              Dashboard
            </button>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-gray-50 px-3 py-1.5 rounded-full border border-gray-100">
              <User className="w-4 h-4 text-brand-terracotta" />
              <span className="text-xs font-bold text-gray-700 hidden sm:block">{user?.email?.split('@')[0]}</span>
              <button onClick={logout} className="p-1 hover:text-red-500 transition-colors">
                <LogOut className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-3xl mx-auto px-6 py-10 space-y-6">

        {/* ── Header ──────────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-black text-gray-900 tracking-tight">My Profile</h1>
            <p className="text-gray-500 mt-1">Edit your public tradie profile shown to homeowners.</p>
          </div>
          <button
            onClick={handleSave}
            disabled={isLoading}
            className="flex items-center gap-2 bg-brand-terracotta text-white px-5 py-2.5 rounded-xl font-bold text-sm hover:shadow-lg hover:shadow-brand-terracotta/20 hover:-translate-y-0.5 transition-all disabled:opacity-50"
          >
            {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            Save Profile
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-3 bg-red-50 border border-red-100 text-red-700 px-5 py-4 rounded-2xl text-sm">
            <AlertCircle className="w-5 h-5 shrink-0" />
            {error}
          </div>
        )}

        {/* ── Avatar section ───────────────────────────────────────────────── */}
        <div className="bg-white rounded-3xl border border-gray-100 p-8 shadow-sm">
          <div className="flex items-center gap-6">
            <div className="relative">
              <div className="w-20 h-20 rounded-2xl bg-brand-cream border border-gray-100 overflow-hidden flex items-center justify-center">
                {profile.avatar_url ? (
                  <img src={profile.avatar_url} alt="Avatar" className="w-full h-full object-cover" />
                ) : (
                  <User className="w-8 h-8 text-brand-terracotta" />
                )}
              </div>
              <button className="absolute -bottom-2 -right-2 w-8 h-8 bg-brand-terracotta text-white rounded-full flex items-center justify-center shadow-md hover:scale-110 transition-transform">
                <Camera className="w-4 h-4" />
              </button>
            </div>
            <div>
              <h2 className="text-lg font-bold text-gray-900">{profile.business_name || user?.name || 'Your Business'}</h2>
              <p className="text-sm text-gray-500">{user?.email}</p>
              <div className="flex items-center gap-1.5 mt-1.5">
                <div className={cn(
                  "w-2 h-2 rounded-full",
                  profile.is_available ? "bg-green-500" : "bg-gray-400"
                )} />
                <span className="text-xs font-bold text-gray-600">
                  {profile.is_available ? 'Available for work' : 'Not available'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Business info ─────────────────────────────────────────────────── */}
        <div className="bg-white rounded-3xl border border-gray-100 p-8 shadow-sm space-y-5">
          <h3 className="font-bold text-gray-900 flex items-center gap-2">
            <Briefcase className="w-4 h-4 text-brand-terracotta" />
            Business Information
          </h3>

          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-700">Business name *</label>
            <input
              type="text"
              placeholder="e.g. Smith's Plumbing Services"
              value={profile.business_name}
              onChange={e => field('business_name', e.target.value)}
              className="w-full bg-brand-cream/50 border border-gray-200 rounded-xl px-4 py-3.5 text-sm font-medium focus:outline-none focus:border-brand-terracotta/50 focus:ring-2 focus:ring-brand-terracotta/10 transition-all"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-700">ABN</label>
            <input
              type="text"
              placeholder="12 345 678 901"
              value={profile.abn}
              onChange={e => field('abn', e.target.value)}
              maxLength={14}
              className="w-full bg-brand-cream/50 border border-gray-200 rounded-xl px-4 py-3.5 text-sm font-medium focus:outline-none focus:border-brand-terracotta/50 focus:ring-2 focus:ring-brand-terracotta/10 transition-all"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-700">Bio</label>
            <textarea
              rows={4}
              placeholder="Tell homeowners about your experience, specialties, and why they should choose you..."
              value={profile.bio}
              onChange={e => field('bio', e.target.value)}
              className="w-full bg-brand-cream/50 border border-gray-200 rounded-xl px-4 py-4 text-sm font-medium focus:outline-none focus:border-brand-terracotta/50 focus:ring-2 focus:ring-brand-terracotta/10 transition-all resize-none"
            />
            <p className="text-xs text-gray-400">{profile.bio.length}/500 characters</p>
          </div>
        </div>

        {/* ── Location ──────────────────────────────────────────────────────── */}
        <div className="bg-white rounded-3xl border border-gray-100 p-8 shadow-sm space-y-5">
          <h3 className="font-bold text-gray-900 flex items-center gap-2">
            <MapPin className="w-4 h-4 text-brand-terracotta" />
            Service Area
          </h3>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-bold text-gray-700">Suburb *</label>
              <input
                type="text"
                placeholder="Your base suburb"
                value={profile.suburb}
                onChange={e => field('suburb', e.target.value)}
                className="w-full bg-brand-cream/50 border border-gray-200 rounded-xl px-4 py-3.5 text-sm font-medium focus:outline-none focus:border-brand-terracotta/50 focus:ring-2 focus:ring-brand-terracotta/10 transition-all"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-bold text-gray-700">State *</label>
              <div className="relative">
                <select
                  value={profile.state}
                  onChange={e => field('state', e.target.value)}
                  className="w-full bg-brand-cream/50 border border-gray-200 rounded-xl px-4 py-3.5 text-sm font-medium focus:outline-none focus:border-brand-terracotta/50 focus:ring-2 focus:ring-brand-terracotta/10 transition-all appearance-none"
                >
                  <option value="">Select state</option>
                  {AU_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
                <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-bold text-gray-700">Postcode</label>
              <input
                type="text"
                placeholder="e.g. 2000"
                value={profile.postcode}
                onChange={e => field('postcode', e.target.value)}
                maxLength={4}
                className="w-full bg-brand-cream/50 border border-gray-200 rounded-xl px-4 py-3.5 text-sm font-medium focus:outline-none focus:border-brand-terracotta/50 focus:ring-2 focus:ring-brand-terracotta/10 transition-all"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-bold text-gray-700">Service radius (km)</label>
              <input
                type="number"
                min={5}
                max={200}
                value={profile.radius_km}
                onChange={e => field('radius_km', Number(e.target.value))}
                className="w-full bg-brand-cream/50 border border-gray-200 rounded-xl px-4 py-3.5 text-sm font-medium focus:outline-none focus:border-brand-terracotta/50 focus:ring-2 focus:ring-brand-terracotta/10 transition-all"
              />
            </div>
          </div>
        </div>

        {/* ── Availability toggle ───────────────────────────────────────────── */}
        <div className="bg-white rounded-3xl border border-gray-100 p-8 shadow-sm">
          <h3 className="font-bold text-gray-900 flex items-center gap-2 mb-5">
            <Shield className="w-4 h-4 text-brand-terracotta" />
            Availability
          </h3>

          <div className="flex items-center justify-between p-5 bg-brand-cream/50 rounded-2xl border border-gray-100">
            <div>
              <p className="font-bold text-gray-900">Available for new jobs</p>
              <p className="text-sm text-gray-500 mt-0.5">
                {profile.is_available
                  ? 'You are visible to homeowners and receiving leads.'
                  : 'You are hidden from search results.'}
              </p>
            </div>

            <button
              onClick={() => field('is_available', !profile.is_available)}
              className={cn(
                "w-14 h-7 rounded-full relative transition-all duration-300 shadow-inner",
                profile.is_available ? "bg-brand-terracotta" : "bg-gray-200"
              )}
            >
              <div className={cn(
                "absolute top-1 w-5 h-5 rounded-full bg-white shadow-sm transition-all duration-300",
                profile.is_available ? "right-1" : "left-1"
              )} />
            </button>
          </div>
        </div>

        {/* ── Save button (bottom) ─────────────────────────────────────────── */}
        <button
          onClick={handleSave}
          disabled={isLoading}
          className="w-full bg-brand-terracotta text-white py-4 rounded-2xl font-bold text-base flex items-center justify-center gap-2 hover:shadow-xl hover:shadow-brand-terracotta/25 hover:-translate-y-0.5 transition-all disabled:opacity-50"
        >
          {isLoading ? (
            <><Loader2 className="w-5 h-5 animate-spin" /> Saving...</>
          ) : (
            <><Save className="w-5 h-5" /> Save Profile</>
          )}
        </button>
      </main>
    </div>
  );
}
