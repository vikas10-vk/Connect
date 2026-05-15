"use client";

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  Briefcase, Clock, MapPin, Calendar, DollarSign,
  AlertCircle, LayoutGrid, Loader2, CheckCircle2,
  Zap, Search, CheckCheck,
} from 'lucide-react';
import { cn } from '@/src/lib/utils';
import api from '@/src/lib/api';
import LeadDetailModal from '@/src/components/LeadDetailModal';
import MarkCompleteModal from '@/src/components/tradie/MarkCompleteModal';

// ── Types ────────────────────────────────────────────────────────────────────

interface Lead {
  id: string;
  job_id: string;
  job_title?: string;
  job_suburb?: string;
  job_state?: string;
  job_description?: string;
  job_budget_min?: number;
  job_budget_max?: number;
  job_urgency?: string;
  job_type?: string;
  service_type?: string;
  job_status?: string;
  status: string;
  sent_at: string;
  is_urgent: boolean;
  is_high_value: boolean;
}

const TABS = ['New Leads', 'Quoted', 'Active Jobs', 'Completed'] as const;
type Tab = typeof TABS[number];

// ── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function urgencyLabel(u?: string): string {
  const map: Record<string, string> = {
    emergency: 'Emergency', asap: 'ASAP',
    next_few_days: 'This week', next_few_weeks: 'Next few weeks', flexible: 'Flexible',
  };
  return u ? (map[u] || u) : '';
}

// ── Lead card ────────────────────────────────────────────────────────────────

function LeadCard({
  lead,
  onView,
  onMarkComplete,
}: {
  lead: Lead;
  onView: () => void;
  onMarkComplete?: () => void;
}) {
  const isQuoted     = lead.status === 'quoted';
  const isCompleted  = lead.job_status === 'completed' || lead.job_status === 'closed';
  const isInProgress = lead.job_status === 'in_progress' || lead.job_status === 'hired';

  return (
    <div
      style={{ backgroundColor: '#FFFFFF' }}
      className="rounded-[2.5rem] p-8 border border-[#E8D9B0] hover:border-[#D4AA3A]/40 transition-all relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 w-48 h-48 bg-white/[0.015] rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl pointer-events-none" />

      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
        {/* Left: info */}
        <div className="flex items-start gap-5 flex-1 min-w-0">
          <div className={cn(
            "w-14 h-14 rounded-2xl flex items-center justify-center shrink-0",
            lead.is_urgent ? "bg-red-500/10 text-red-400" : "bg-[#1DE9B6]/10 text-[#1DE9B6]",
          )}>
            <Briefcase className="w-6 h-6" />
          </div>

          <div className="flex-1 min-w-0 space-y-2">
            {/* Badges */}
            <div className="flex flex-wrap gap-2">
              {lead.is_urgent && (
                <span className="bg-red-500 text-white text-[10px] font-black uppercase tracking-[0.15em] px-3 py-1 rounded-full flex items-center gap-1.5">
                  <AlertCircle className="w-3 h-3" /> Urgent
                </span>
              )}
              {lead.is_high_value && (
                <span className="bg-yellow-500/20 text-yellow-400 text-[10px] font-black uppercase tracking-[0.15em] px-3 py-1 rounded-full">
                  💰 High Value
                </span>
              )}
              {isQuoted && (
                <span className="bg-[#1DE9B6]/15 text-[#1DE9B6] text-[10px] font-black uppercase tracking-[0.15em] px-3 py-1 rounded-full">
                  Quoted
                </span>
              )}
              {isInProgress && (
                <span className="bg-emerald-500/15 text-emerald-400 text-[10px] font-black uppercase tracking-[0.15em] px-3 py-1 rounded-full flex items-center gap-1">
                  <CheckCircle2 className="w-3 h-3" /> In Progress
                </span>
              )}
              {isCompleted && (
                <span className="bg-green-500/15 text-green-400 text-[10px] font-black uppercase tracking-[0.15em] px-3 py-1 rounded-full">
                  Completed
                </span>
              )}
            </div>

            {/* Title */}
            <h3 className="text-lg font-black text-[#071D36] tracking-tight truncate">
              {lead.job_title || 'Untitled Job'}
            </h3>

            {/* Meta */}
            <div className="flex flex-wrap items-center gap-5 text-gray-500">
              {lead.job_suburb && (
                <span className="flex items-center gap-1.5 text-xs font-bold">
                  <MapPin className="w-3.5 h-3.5 text-[#1DE9B6]" />
                  {lead.job_suburb}{lead.job_state ? `, ${lead.job_state}` : ''}
                </span>
              )}
              <span className="flex items-center gap-1.5 text-xs font-bold">
                <Clock className="w-3.5 h-3.5 text-[#1DE9B6]" />
                {timeAgo(lead.sent_at)}
              </span>
              {lead.job_urgency && (
                <span className="flex items-center gap-1.5 text-xs font-bold">
                  <Calendar className="w-3.5 h-3.5 text-[#1DE9B6]" />
                  {urgencyLabel(lead.job_urgency)}
                </span>
              )}
              {(lead.job_budget_min || lead.job_budget_max) && (
                <span className="flex items-center gap-1.5 text-xs font-bold">
                  <DollarSign className="w-3.5 h-3.5 text-[#1DE9B6]" />
                  {lead.job_budget_max
                    ? `Up to $${lead.job_budget_max.toLocaleString()}`
                    : `From $${lead.job_budget_min?.toLocaleString()}`}
                </span>
              )}
            </div>

            {/* Description snippet */}
            {lead.job_description && (
              <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">
                {lead.job_description}
              </p>
            )}
          </div>
        </div>

        {/* Right: action buttons */}
        <div className="shrink-0 flex flex-col sm:flex-row gap-2 items-end sm:items-center">
          {isInProgress && (
            <button
              onClick={onMarkComplete}
              className="px-7 py-3.5 rounded-2xl bg-emerald-600 hover:bg-emerald-500 text-white font-black text-xs uppercase tracking-[0.15em] transition-all flex items-center gap-2 shadow-lg shadow-emerald-900/30"
            >
              <CheckCheck className="w-4 h-4" /> Mark complete
            </button>
          )}
          {isCompleted ? (
            <button
              onClick={onView}
              className="px-8 py-4 rounded-2xl border border-[#E8D9B0] font-black text-xs uppercase tracking-[0.15em] text-gray-500 hover:bg-[#F5EDD0] transition-all"
            >
              View Details
            </button>
          ) : isQuoted ? (
            <button
              onClick={onView}
              className="px-8 py-4 rounded-2xl border border-[#1DE9B6]/30 bg-[#1DE9B6]/10 text-[#1DE9B6] font-black text-xs uppercase tracking-[0.15em] hover:bg-[#1DE9B6]/15 transition-all flex items-center gap-2"
            >
              <CheckCircle2 className="w-4 h-4" /> View Quote
            </button>
          ) : (
            <button
              onClick={onView}
              className="px-10 py-4 rounded-2xl bg-[#1DE9B6] text-[#071D36] font-black text-xs uppercase tracking-[0.15em] hover:scale-105 transition-transform shadow-2xl shadow-[#1DE9B6]/25 flex items-center gap-2"
            >
              <Zap className="w-4 h-4" /> View &amp; Quote
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ tab }: { tab: Tab }) {
  const msgs: Record<Tab, { title: string; sub: string }> = {
    'New Leads':   { title: 'No new leads yet',      sub: 'New job leads matching your skills will appear here.' },
    'Quoted':      { title: 'No quotes sent yet',    sub: 'Leads you have quoted will show here.' },
    'Active Jobs': { title: 'No active jobs',        sub: 'Jobs you have been hired for will appear here.' },
    'Completed':   { title: 'No completed jobs yet', sub: 'Finished jobs will be archived here.' },
  };
  const { title, sub } = msgs[tab];
  return (
    <div
      style={{ backgroundColor: '#FFFFFF' }}
      className="rounded-[3rem] p-20 flex flex-col items-center justify-center text-center space-y-5 border-2 border-dashed border-[#E8D9B0]"
    >
      <div className="w-20 h-20 rounded-[2rem] bg-gray-100 flex items-center justify-center">
        <Briefcase className="w-9 h-9 text-gray-300" />
      </div>
      <div className="space-y-2">
        <h3 className="text-xl font-black text-[#071D36]">{title}</h3>
        <p className="text-gray-500 font-medium max-w-xs mx-auto leading-relaxed text-sm">{sub}</p>
      </div>
    </div>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function Jobs() {
  const [activeTab, setActiveTab]       = useState<Tab>('New Leads');
  const [leads, setLeads]               = useState<Lead[]>([]);
  const [isLoading, setIsLoading]       = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [markCompleteLead, setMarkCompleteLead] = useState<Lead | null>(null);
  const [search, setSearch]             = useState('');

  const loadLeads = useCallback(async () => {
    setIsLoading(true); setError(null);
    try {
      const res = await api.get('/leads/my-leads');
      setLeads(res.data || []);
    } catch {
      setError('Could not load leads. Check your connection and try again.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { loadLeads(); }, [loadLeads]);

  // Tab filters
  const byTab = (lead: Lead): boolean => {
    switch (activeTab) {
      case 'New Leads':   return lead.status === 'sent' || lead.status === 'new';
      case 'Quoted':      return lead.status === 'quoted';
      case 'Active Jobs': return lead.job_status === 'in_progress' || lead.job_status === 'hired';
      case 'Completed':   return lead.job_status === 'completed' || lead.job_status === 'closed';
      default: return true;
    }
  };

  const filtered = leads
    .filter(byTab)
    .filter(l =>
      !search ||
      (l.job_title || '').toLowerCase().includes(search.toLowerCase()) ||
      (l.job_suburb || '').toLowerCase().includes(search.toLowerCase())
    );

  const counts: Record<Tab, number> = {
    'New Leads':   leads.filter(l => l.status === 'sent' || l.status === 'new').length,
    'Quoted':      leads.filter(l => l.status === 'quoted').length,
    'Active Jobs': leads.filter(l => l.job_status === 'in_progress' || l.job_status === 'hired').length,
    'Completed':   leads.filter(l => l.job_status === 'completed' || l.job_status === 'closed').length,
  };

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">

      {/* Lead detail modal */}
      {selectedLead && (
        <LeadDetailModal
          lead={selectedLead}
          onClose={() => setSelectedLead(null)}
          onQuoteSubmitted={() => { setSelectedLead(null); loadLeads(); }}
        />
      )}

      {/* Mark complete modal */}
      {markCompleteLead && (
        <MarkCompleteModal
          jobId={markCompleteLead.job_id}
          jobTitle={markCompleteLead.job_title}
          onClose={() => setMarkCompleteLead(null)}
          onCompleted={() => { setMarkCompleteLead(null); loadLeads(); }}
        />
      )}

      {/* Breadcrumb */}
      <nav className="sticky top-0 z-[100] -mx-4 md:mx-0 bg-[#071D36]/95 backdrop-blur-md border-b border-white/10 px-4 md:px-0 py-3">
        <div className="flex items-center justify-between gap-3">
          <Link
            href="/tradie/dashboard"
            className="inline-flex items-center gap-2 text-[#1DE9B6] font-black text-xs uppercase tracking-[0.18em]"
          >
            <LayoutGrid className="w-4 h-4" /> Dashboard
          </Link>
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">My Jobs</span>
        </div>
      </nav>

      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-5">
        <div>
          <h1 className="text-4xl font-black tracking-tighter text-[#071D36] uppercase">Jobs</h1>
          <p className="text-gray-500 font-bold text-sm mt-1">
            {isLoading ? 'Loading…' : `${leads.length} total lead${leads.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <div className="flex gap-3">
          <div className="relative group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 group-focus-within:text-[#1DE9B6] transition-colors" />
            <input
              type="text"
              placeholder="Search jobs or suburb…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{ backgroundColor: '#FFFFFF' }}
              className="border border-[#E8D9B0] rounded-2xl pl-10 pr-5 py-3.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1DE9B6]/20 transition-all w-52 text-[#071D36] font-medium placeholder-gray-400"
            />
          </div>
        </div>
      </header>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 bg-red-500/10 border border-red-500/20 text-red-400 px-5 py-4 rounded-2xl text-sm font-bold">
          <AlertCircle className="w-4 h-4 shrink-0" /> {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-wrap gap-3">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-7 py-4 rounded-2xl text-xs font-black uppercase tracking-[0.18em] transition-all flex items-center gap-3 border",
              activeTab === tab
                ? "bg-[#1DE9B6] text-[#071D36] border-[#1DE9B6] shadow-2xl shadow-[#1DE9B6]/25"
                : "bg-[#F5EDD0] text-[#071D36] border-[#E8D9B0] hover:bg-[#E8D9B0] hover:text-[#071D36]"
            )}
          >
            {tab}
            {counts[tab] > 0 && (
              <span className={cn(
                "text-[10px] px-2 py-0.5 rounded-lg font-black",
                activeTab === tab ? "bg-[#071D36]/20 text-[#071D36]" : "bg-red-500 text-white"
              )}>
                {counts[tab]}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Lead list */}
      <div className="space-y-4">
        {isLoading ? (
          <div
            style={{ backgroundColor: '#FFFFFF' }}
            className="rounded-[3rem] p-20 flex flex-col items-center justify-center gap-4 border border-white/5"
          >
            <Loader2 className="w-10 h-10 text-[#1DE9B6] animate-spin" />
            <p className="text-gray-500 font-bold text-sm uppercase tracking-widest">Loading leads…</p>
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState tab={activeTab} />
        ) : (
          filtered.map(lead => (
            <LeadCard
              key={lead.id}
              lead={lead}
              onView={() => setSelectedLead(lead)}
              onMarkComplete={() => setMarkCompleteLead(lead)}
            />
          ))
        )}
      </div>
    </div>
  );
}

