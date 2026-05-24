"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/src/contexts/AuthContext';
import { motion } from 'motion/react';
import {
  LayoutGrid,
  Briefcase,
  ShieldCheck,
  Send,
  Settings,
  User,
  LogOut,
  Zap,
  X
} from 'lucide-react';
import { cn } from '@/src/lib/utils';

const navItems = [
  { icon: LayoutGrid, label: 'Dashboard', path: '/tradie/dashboard' },
  { icon: Briefcase, label: 'Jobs', path: '/tradie/jobs', badge: 1 },
  { icon: ShieldCheck, label: 'Licences & Docs', path: '/tradie/docs' },
  { icon: Send, label: 'Quotes', path: '/tradie/quotes' },
  { icon: Settings, label: 'Preferences', path: '/tradie/preferences' },
  { icon: User, label: 'Profile', path: '/tradie/profile' },
];

interface SidebarProps {
  onClose?: () => void;
}

export function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname();
  const { logout } = useAuth();

  return (
    <div
      style={{ backgroundColor: '#071D36', borderRight: '1px solid rgba(255,255,255,0.08)' }}
      className="w-64 md:w-72 h-full flex flex-col text-white shrink-0 min-h-0 overflow-hidden"
    >
      {/* Logo header */}
      <div className="p-6 md:p-7 flex items-center justify-between gap-4" style={{ borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 md:w-11 md:h-11 rounded-2xl flex items-center justify-center shadow-lg transition-transform hover:scale-105"
            style={{ background: '#D4AA3A', boxShadow: '0 4px 14px rgba(212,170,58,0.35)' }}>
            <Zap className="w-5 h-5 md:w-6 md:h-6 fill-current" style={{ color: '#071D36' }} />
          </div>
          <div>
            <h1 className="text-lg md:text-xl font-black tracking-tight" style={{ color: '#D4AA3A' }}>ProConnect</h1>
            <p className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.4)' }}>Tradie Hub</p>
          </div>
        </div>
        <button onClick={onClose} className="md:hidden p-2 rounded-lg transition-colors"
          style={{ color: 'rgba(255,255,255,0.4)' }}
          onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}>
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav className="flex-1 px-3 md:px-4 py-4 space-y-1 overflow-y-auto custom-scrollbar">
        <p className="text-[10px] font-bold uppercase tracking-widest px-3 pb-2" style={{ color: 'rgba(255,255,255,0.35)' }}>Navigation</p>
        {navItems.map((item) => {
          const isActive = pathname === item.path;
          return (
            <Link
              key={item.path}
              href={item.path}
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group relative overflow-hidden",
                isActive
                  ? "font-black"
                  : "font-semibold hover:bg-white/5"
              )}
              style={{
                background: isActive ? 'rgba(212,170,58,0.15)' : 'transparent',
                border: isActive ? '1px solid rgba(212,170,58,0.25)' : '1px solid transparent',
              }}
            >
              {isActive && (
                <motion.div
                  layoutId="activeNav"
                  className="absolute inset-0 bg-gradient-to-r from-yellow-400/10 to-transparent pointer-events-none"
                />
              )}
              <item.icon className={cn(
                "w-5 h-5 transition-all duration-200 relative z-10",
                isActive ? "" : "group-hover:scale-110"
              )}
              style={{ color: isActive ? '#D4AA3A' : '#5BB3FF' }}
              />
              <span className="flex-1 text-sm relative z-10 transition-colors duration-200"
                style={{ color: isActive ? '#D4AA3A' : 'rgba(255,255,255,0.75)' }}
                onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.color = '#D4AA3A'; }}
                onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.color = 'rgba(255,255,255,0.75)'; }}>
                {item.label}
              </span>
              {item.badge && (
                <span className="text-[10px] font-black px-2.5 py-0.5 rounded-lg relative z-10"
                  style={{ background: '#D4AA3A', color: '#071D36' }}>
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 mt-auto" style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
        <button onClick={logout} className="flex items-center gap-3 px-4 py-3 w-full rounded-xl transition-all duration-200 group"
          style={{ color: 'rgba(255,255,255,0.4)' }}
          onMouseEnter={e => { e.currentTarget.style.color = '#FF6B6B'; e.currentTarget.style.background = 'rgba(255,80,80,0.08)'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.4)'; e.currentTarget.style.background = 'transparent'; }}>
          <LogOut className="w-5 h-5 transition-transform group-hover:-translate-x-1" />
          <span className="text-sm font-semibold">Sign Out</span>
        </button>
      </div>
    </div>
  );
}
