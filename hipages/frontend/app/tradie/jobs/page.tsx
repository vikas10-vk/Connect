"use client";

import React from 'react';
import Link from 'next/link';
import { 
  Briefcase, 
  Clock, 
  CheckCircle2, 
  MapPin, 
  ChevronRight,
  Search,
  Filter,
  Calendar,
  AlertCircle,
  LayoutGrid
} from 'lucide-react';
import { cn } from '@/src/lib/utils';

const tabs = ['New Leads', 'Active Jobs', 'Completed', 'Quoted'];

interface JobCardProps {
  title: string;
  location: string;
  time: string;
  urgent?: boolean;
  onAccept?: () => void;
  onDecline?: () => void;
}

function JobCard({ title, location, time, urgent, onAccept, onDecline }: JobCardProps) {
  return (
    <div 
      style={{ backgroundColor: '#141416' }}
      className="rounded-[3rem] p-10 border border-white/5 hover:border-white/10 transition-all group flex flex-col lg:flex-row lg:items-center justify-between gap-8 shadow-2xl relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 w-64 h-64 bg-white/[0.02] rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl" />
      <div className="flex items-center gap-8 relative z-10">
        <div className={cn(
          "w-24 h-24 rounded-[2rem] flex items-center justify-center shadow-inner shrink-0",
          urgent ? "bg-red-500/10 text-red-500" : "bg-tradie-accent/10 text-tradie-accent"
        )}>
          <Briefcase className="w-10 h-10" />
        </div>
        <div className="space-y-3">
          <div className="flex items-center gap-4">
            <h3 className="text-3xl font-black text-white tracking-tight">{title}</h3>
            {urgent && (
              <span className="bg-red-500 text-white text-[10px] font-black uppercase tracking-[0.2em] px-4 py-1.5 rounded-full flex items-center gap-2 shadow-xl shadow-red-500/20">
                <AlertCircle className="w-3 h-3" />
                Urgent
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-8 text-gray-500 font-bold">
            <div className="flex items-center gap-2.5">
              <MapPin className="w-5 h-5 text-[#1DE9B6]" />
              <span className="text-sm tracking-wide">{location}</span>
            </div>
            <div className="flex items-center gap-2.5">
              <Clock className="w-5 h-5 text-[#1DE9B6]" />
              <span className="text-sm tracking-wide">{time}</span>
            </div>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-4 relative z-10">
        <button 
          onClick={onDecline}
          className="flex-1 lg:flex-none px-10 py-5 rounded-2xl border border-white/10 font-black text-xs uppercase tracking-[0.2em] text-gray-500 hover:bg-white/5 transition-all"
        >
          Decline
        </button>
        <button 
          onClick={onAccept}
          className="flex-1 lg:flex-none px-12 py-5 rounded-2xl bg-[#1DE9B6] text-[#0A0A0B] font-black text-xs uppercase tracking-[0.2em] hover:scale-105 transition-transform shadow-2xl shadow-[#1DE9B6]/30"
        >
          Accept Lead
        </button>
      </div>
    </div>
  );
}

export default function Jobs() {
  const [activeTab, setActiveTab] = React.useState('New Leads');

  return (
    <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <nav className="sticky top-0 z-[100] -mx-4 md:mx-0 bg-[#0A0A0B]/95 backdrop-blur-md border-b border-white/10 px-4 md:px-0 py-3">
        <div className="flex items-center justify-between gap-3">
          <Link href="/tradie/dashboard" className="inline-flex items-center gap-2 text-[#1DE9B6] font-black text-xs uppercase tracking-[0.18em]">
            <LayoutGrid className="w-4 h-4" />
            Dashboard
          </Link>
          <span className="text-[10px] font-black uppercase tracking-[0.2em] text-gray-500">Jobs</span>
        </div>
      </nav>

      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div className="space-y-1">
          <h1 className="text-4xl font-black tracking-tighter text-white uppercase">Jobs</h1>
          <p className="text-gray-500 font-bold text-base">Manage your project pipeline and active leads.</p>
        </div>
        <div className="flex gap-4">
          <div className="relative group">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-500 group-focus-within:text-[#1DE9B6] transition-colors" />
            <input 
              type="text" 
              placeholder="Search jobs..."
              style={{ backgroundColor: '#141416' }}
              className="border border-white/10 rounded-2xl pl-12 pr-6 py-4 text-sm focus:outline-none focus:ring-2 focus:ring-[#1DE9B6]/20 transition-all w-72 text-white font-bold"
            />
          </div>
          <button 
            style={{ backgroundColor: '#141416' }}
            className="border border-white/10 p-4 rounded-2xl text-gray-400 hover:text-white transition-all hover:scale-105"
          >
            <Filter className="w-6 h-6" />
          </button>
        </div>
      </header>

      <div className="flex flex-wrap gap-6">
        {tabs.map((tab) => (
          <button 
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "px-10 py-5 rounded-2xl text-xs font-black uppercase tracking-[0.2em] transition-all flex items-center gap-4 border",
              activeTab === tab 
                ? "bg-[#1DE9B6] text-[#0A0A0B] border-[#1DE9B6] shadow-2xl shadow-[#1DE9B6]/30" 
                : "bg-white/5 text-gray-500 border-white/5 hover:bg-white/10 hover:text-gray-300"
            )}
          >
            {tab}
            {tab === 'New Leads' && (
              <span className="bg-red-500 text-white text-[10px] px-2.5 py-1 rounded-lg shadow-xl shadow-red-500/20">1</span>
            )}
          </button>
        ))}
      </div>

      <div className="space-y-6">
        {activeTab === 'New Leads' ? (
          <JobCard 
            title="Plumbing Repair"
            location="Richmond, VIC"
            time="Posted 2 hours ago"
            urgent
          />
        ) : (
          <div 
            style={{ backgroundColor: '#141416' }}
            className="rounded-[3rem] p-24 flex flex-col items-center justify-center text-center space-y-6 border-2 border-dashed border-white/5"
          >
            <div className="w-24 h-24 rounded-[2.5rem] bg-white/5 flex items-center justify-center text-white/10">
              <Briefcase className="w-12 h-12" />
            </div>
            <div className="space-y-2">
              <h3 className="text-2xl font-black text-gray-400">No {activeTab.toLowerCase()} yet</h3>
              <p className="text-gray-500 font-medium max-w-xs mx-auto leading-relaxed">Your {activeTab.toLowerCase()} will appear here once you take action on new leads.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
