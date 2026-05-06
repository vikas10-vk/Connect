"use client";

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/src/contexts/AuthContext';
import { motion } from 'motion/react';
import { 
  LayoutGrid, 
  Inbox, 
  Briefcase, 
  DollarSign, 
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
  { icon: ShieldCheck, label: 'Docs', path: '/tradie/docs' },
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
      style={{ backgroundColor: '#0A0A0B' }}
      className="w-64 md:w-72 h-full flex flex-col text-white border-r border-white/10 shrink-0 min-h-0 overflow-hidden"
    >
      <div className="p-6 md:p-8 flex items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 md:w-12 md:h-12 rounded-2xl bg-[#1DE9B6] flex items-center justify-center text-[#0A0A0B] shadow-lg shadow-[#1DE9B6]/20">
            <Zap className="w-6 h-6 md:w-7 md:h-7 fill-current" />
          </div>
          <h1 className="text-xl md:text-2xl font-black tracking-tight uppercase">Hub</h1>
        </div>
        <button onClick={onClose} className="md:hidden p-2 text-gray-500 hover:text-white">
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav className="flex-1 px-4 md:px-6 py-2 md:py-4 space-y-1 md:space-y-2 overflow-y-auto custom-scrollbar">
        {navItems.map((item) => {
          const isActive = pathname === item.path;
          return (
            <Link
              key={item.path}
              href={item.path}
              onClick={onClose}
              className={cn(
                "flex items-center gap-3 md:gap-4 px-4 md:px-6 py-2.5 md:py-3 rounded-2xl transition-all duration-500 group relative overflow-hidden",
                isActive 
                  ? "bg-[#141416] text-[#1DE9B6] font-black shadow-2xl border border-white/10" 
                  : "text-gray-500 hover:bg-white/5 hover:text-white font-bold"
              )}
            >
              {isActive && (
                <motion.div 
                  layoutId="activeNav"
                  className="absolute inset-0 bg-gradient-to-r from-[#1DE9B6]/10 to-transparent"
                />
              )}
              <item.icon className={cn(
                "w-5 h-5 transition-transform duration-500 group-hover:scale-110 relative z-10",
                isActive ? "text-[#1DE9B6]" : "group-hover:text-white"
              )} />
              <span className="flex-1 text-sm tracking-widest uppercase relative z-10">{item.label}</span>
              {item.badge && (
                <span className="bg-[#1DE9B6] text-[#0A0A0B] text-[10px] font-black px-2.5 py-1 rounded-lg shadow-lg relative z-10">
                  {item.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 mt-auto border-t border-white/5">
        <button onClick={logout} className="flex items-center gap-3 px-4 py-3 w-full text-gray-500 hover:text-red-400 transition-all duration-300 rounded-xl hover:bg-red-500/5 group">
          <LogOut className="w-5 h-5 transition-transform group-hover:-translate-x-1" />
          <span className="text-sm font-bold tracking-wide">Sign Out</span>
        </button>
      </div>
    </div>
  );
}
