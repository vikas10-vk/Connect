"use client";
/**
 * TradieStudioLayout
 *
 * Shared shell used by ALL tradie studio pages:
 *   /tradie/dashboard, /tradie/preferences, /tradie/profile, /tradie/licences
 *
 * Features:
 *  - Sticky sidebar that stays visible on scroll (correct height containment)
 *  - Unified nav  -  shows Leads + Active Jobs only when approved
 *  - Available/Offline status toggle in the sidebar header
 *  - Live verification status badge
 *  - Mobile hamburger + slide-out drawer
 *  - Passes isApproved, verificationStatus to children via render prop
 */

import React, { useEffect, useState, useCallback, Suspense } from 'react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import {
  Zap, LayoutDashboard, Inbox, Briefcase,
  ShieldCheck, SlidersHorizontal, UserCircle,
  LogOut, Menu, X,
} from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';
import { toast } from 'sonner';
import api from '@/src/lib/api';

// ─── Design tokens ────────────────────────────────────────────────────────────
const C = {
  bg: '#FFF8E7', paper: '#FFF8E7', panel: '#071D36', card: '#FFFFFF',
  line: 'rgba(255,255,255,0.10)', lineSoft: 'rgba(255,255,255,0.06)',
  ink: '#071D36', ink2: '#173452', ink3: '#56677A', ink4: '#8A785A',
  brass: '#D4AA3A', brassL: '#F7EBC5', brassB: '#E8C766',
  sage: '#5B7560', sageL: '#EDF3EE',
  amber: '#9A6B1E', amberL: '#F7EED8',
  rose: '#A8423A', roseL: '#F7E6E4',
  iconBlue: '#5BB3FF',
  navText: 'rgba(255,255,255,0.80)',
};
const DISPLAY = "'Fraunces', 'Playfair Display', Georgia, serif";
const UI = "'Inter', 'DM Sans', -apple-system, system-ui, sans-serif";

export interface TradieStudioContext {
  isApproved: boolean;
  verificationStatus: string;
  isAvailable: boolean;
  businessName: string;
  avatarUrl: string;
  newLeadCount: number;
  refreshStatus: () => void;
}

interface NavItem {
  label: string;
  icon: React.ElementType;
  href: string;
  badge?: number | string;
  warn?: boolean; // shows amber ! indicator
}

interface Props {
  children: (ctx: TradieStudioContext) => React.ReactNode;
}

function TradieStudioLayoutInner({ children }: Props) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [isApproved, setIsApproved] = useState(false);
  const [verificationStatus, setVerificationStatus] = useState('pending_review');
  const [isAvailable, setIsAvailable] = useState(false);
  const [businessName, setBusinessName] = useState('');
  const [avatarUrl, setAvatarUrl] = useState('');
  const [newLeadCount, setNewLeadCount] = useState(0);
  const [activeJobCount, setActiveJobCount] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [togglingAvail, setTogglingAvail] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.get('/tradies/profile/me');
      const d = res.data;
      setVerificationStatus(d.verification_status || 'pending_review');
      setIsApproved(d.verification_status === 'verified');
      setIsAvailable(d.is_available ?? false);
      setBusinessName(d.business_name || '');
      setAvatarUrl(d.avatar_url || '');
    } catch { /* ignore */ }
  }, []);

  const fetchLeadCount = useCallback(async () => {
    if (!isApproved) return;
    try {
      // Use the same dashboard endpoint so badge counts are always consistent
      // with what the tradie actually sees in each tab.
      const res = await api.get('/tradies/dashboard/me');
      const leads: { status: string; job_status?: string }[] = res.data?.leads || [];

      // "Leads" badge: only unquoted leads the tradie hasn't acted on yet
      setNewLeadCount(leads.filter(l => l.status === 'sent').length);

      // "Active jobs" badge: leads whose job is active and won by this tradie (or quoted pending a decision)
      const activeCount = leads.filter(l => {
        if (l.status === 'rejected') return false;
        if (l.status === 'accepted') {
          const DONE_JOB_STATUSES = new Set(['confirmed', 'closed']);
          return l.job_status == null || !DONE_JOB_STATUSES.has(l.job_status);
        }
        if (l.status === 'quoted') {
          const SOMEONE_ELSE_HIRED = new Set(['hired', 'in_progress', 'awaiting_scope_approval', 'partial_stop', 'completed', 'disputed', 'confirmed', 'closed']);
          if (l.job_status != null && SOMEONE_ELSE_HIRED.has(l.job_status)) {
            return false;
          }
          return true;
        }
        return false;
      }).length;

      setActiveJobCount(activeCount);
    } catch { /* ignore */ }
  }, [isApproved]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    fetchLeadCount();
  }, [fetchLeadCount]);

  const toggleAvailability = async () => {
    if (!isApproved || togglingAvail) return;
    setTogglingAvail(true);
    const prev = isAvailable;
    setIsAvailable(!prev);
    try {
      const res = await api.patch('/tradies/availability/toggle');
      setIsAvailable(res.data.is_available);
    } catch (e: any) {
      setIsAvailable(prev);
      toast.error(e?.response?.data?.detail || 'Could not update status.');
    } finally {
      setTogglingAvail(false);
    }
  };

  const ctx: TradieStudioContext = {
    isApproved, verificationStatus, isAvailable,
    businessName, avatarUrl, newLeadCount,
    refreshStatus: fetchStatus,
  };

  const NAV_ITEMS: NavItem[] = [
    { label: 'Overview', icon: LayoutDashboard, href: '/tradie/dashboard' },
    ...(isApproved ? [
      { label: 'Leads', icon: Inbox, href: '/tradie/dashboard?tab=leads', badge: newLeadCount || undefined },
      { label: 'Active jobs', icon: Briefcase, href: '/tradie/dashboard?tab=active', badge: activeJobCount || undefined },
    ] : []),
    { label: 'Licences & Docs', icon: ShieldCheck, href: '/tradie/licences', warn: !isApproved },
    { label: 'Preferences', icon: SlidersHorizontal, href: '/tradie/preferences' },
    { label: 'Profile', icon: UserCircle, href: '/tradie/profile' },
  ];

  const isActive = (href: string) => {
    // For dashboard sub-tabs the href includes a ?tab= query param.
    // We need to match both the pathname AND the tab param so that
    // "Overview" (/tradie/dashboard) and "Leads" (/tradie/dashboard?tab=leads)
    // are never both highlighted at the same time.
    const [base, query] = href.split('?');
    if (pathname !== base) return false;
    if (!query) {
      // Overview  -  active only when there's no ?tab= param in the URL.
      return !searchParams.get('tab');
    }
    const hrefParams = new URLSearchParams(query);
    return hrefParams.get('tab') === searchParams.get('tab');
  };

  const initials = (businessName || user?.email || 'T')[0].toUpperCase();

  const SidebarContent = () => (
    <div style={{
      display: 'flex', flexDirection: 'column',
      height: '100%', overflow: 'hidden',
    }}>
      {/* Logo */}
      <div style={{ padding: '20px 20px 14px', borderBottom: `1px solid ${C.lineSoft}`, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 9, background: C.brass, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, boxShadow: '0 4px 12px rgba(212,170,58,0.35)' }}>
            <Zap size={17} color={C.ink} fill={C.ink} />
          </div>
          <div>
            <p style={{ fontFamily: DISPLAY, fontSize: 17, fontWeight: 700, color: C.brass, margin: 0, letterSpacing: '-0.01em', lineHeight: 1 }}>ProConnect</p>
            <p style={{ fontSize: 9, fontWeight: 700, color: 'rgba(255,255,255,0.4)', margin: '3px 0 0', textTransform: 'uppercase', letterSpacing: '0.14em' }}>Tradie Studio</p>
          </div>
        </div>
      </div>

      {/* Status toggle */}
      <div style={{ margin: '12px 14px', padding: '12px 14px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)', borderRadius: 10, flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'rgba(255,255,255,0.45)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Status</span>
          {/* Toggle */}
          <button onClick={toggleAvailability} disabled={!isApproved || togglingAvail}
            style={{ width: 40, height: 22, borderRadius: 11, flexShrink: 0, background: isAvailable && isApproved ? C.ink : C.line, border: 'none', cursor: isApproved ? 'pointer' : 'not-allowed', position: 'relative', transition: 'background 0.2s', opacity: isApproved ? 1 : 0.5 }}>
            <div style={{ width: 16, height: 16, borderRadius: '50%', background: C.card, position: 'absolute', top: 3, left: isAvailable && isApproved ? 21 : 3, transition: 'left 0.2s cubic-bezier(0.4,0,0.2,1)', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
          </button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{
            width: 7, height: 7, borderRadius: '50%',
            background: isAvailable && isApproved ? C.sage : C.ink4,
            boxShadow: isAvailable && isApproved ? `0 0 0 3px ${C.sage}20` : 'none',
            transition: 'all 0.3s', flexShrink: 0,
          }} />
          <span style={{ fontSize: 12.5, fontWeight: 600, color: 'rgba(255,255,255,0.85)' }}>
            {!isApproved
              ? (verificationStatus === 'rejected' ? 'Rejected' : verificationStatus === 'suspended' ? 'Suspended' : 'Pending approval')
              : isAvailable ? 'Available' : 'Offline'}
          </span>
        </div>
      </div>

      {/* Nav */}
      <nav style={{ padding: '0 10px', display: 'flex', flexDirection: 'column', gap: 2, flex: 1, overflowY: 'auto' }}>
        <p style={{ fontSize: 9, fontWeight: 700, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.14em', padding: '10px 12px 8px', margin: 0 }}>Workspace</p>
        {NAV_ITEMS.map(item => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <button key={item.label}
              onClick={() => { router.push(item.href); setSidebarOpen(false); }}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '9px 12px', borderRadius: 10, border: active ? '1px solid rgba(212,170,58,0.25)' : '1px solid transparent',
                cursor: 'pointer', width: '100%',
                boxSizing: 'border-box',
                background: active ? 'rgba(212,170,58,0.13)' : 'transparent',
                color: active ? C.brass : item.warn ? C.amber : C.navText,
                fontSize: 13.5, fontWeight: active ? 600 : 500,
                transition: 'all 0.15s', textAlign: 'left', fontFamily: UI,
              }}
              onMouseEnter={e => {
                if (!active) {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
                  // turn label gold on hover
                  const label = e.currentTarget.querySelector('.nav-label') as HTMLElement;
                  if (label) label.style.color = C.brass;
                }
              }}
              onMouseLeave={e => {
                if (!active) {
                  e.currentTarget.style.background = 'transparent';
                  const label = e.currentTarget.querySelector('.nav-label') as HTMLElement;
                  if (label) label.style.color = C.navText;
                }
              }}>
              <Icon size={15} strokeWidth={active ? 2.2 : 1.8} style={{ color: active ? C.brass : C.iconBlue, flexShrink: 0 }} />
              <span className="nav-label" style={{ flex: 1, color: active ? C.brass : C.navText, transition: 'color 0.15s' }}>{item.label}</span>
              {item.warn && !active && (
                <span style={{ fontSize: 9, fontWeight: 700, padding: '1px 6px', borderRadius: 8, background: C.amberL, color: C.amber }}>!</span>
              )}
              {item.badge ? (
                <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 7px', borderRadius: 10, background: C.brass, color: C.ink, minWidth: 18, textAlign: 'center' }}>
                  {item.badge}
                </span>
              ) : null}
            </button>
          );
        })}
      </nav>

      {/* User footer */}
      <div style={{ padding: '12px 14px', borderTop: `1px solid ${C.lineSoft}`, flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 34, height: 34, borderRadius: 9, background: C.brass, border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, overflow: 'hidden' }}>
            {avatarUrl
              ? <img src={avatarUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
              : <span style={{ fontSize: 13, fontWeight: 700, color: C.ink }}>{initials}</span>}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontSize: 12.5, fontWeight: 600, color: 'rgba(255,255,255,0.9)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{businessName || 'Tradie'}</p>
            <p style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.email}</p>
          </div>
          <button onClick={logout} title="Sign out"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.35)', padding: 6, borderRadius: 6, display: 'flex', transition: 'all 0.15s' }}
            onMouseEnter={e => { e.currentTarget.style.color = '#FF6B6B'; e.currentTarget.style.background = 'rgba(255,80,80,0.12)'; }}
            onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.35)'; e.currentTarget.style.background = 'transparent'; }}>
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      <style>{`
        .ts-shell { display: flex; height: 100vh; overflow: hidden; background: ${C.bg}; font-family: ${UI}; }
        .ts-sidebar {
          width: 248px; min-width: 248px; flex: 0 0 248px;
          background: #071D36; border-right: 1px solid rgba(255,255,255,0.08);
          height: 100vh; overflow: hidden;
          position: sticky; top: 0;
          display: flex; flex-direction: column;
        }
        .ts-main { flex: 1; overflow-y: auto; min-width: 0; background: ${C.bg}; }
        .ts-mobile-bar {
          display: none; position: fixed; top: 0; left: 0; right: 0; z-index: 100;
          background: #071D36; backdrop-filter: blur(12px); border-bottom: 1px solid rgba(255,255,255,0.08);
          padding: 12px 16px; align-items: center; justify-content: space-between; gap: 12px;
        }
        .ts-drawer-overlay {
          display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); backdrop-filter: blur(2px); z-index: 99;
        }
        .ts-drawer {
          position: fixed; top: 0; left: -260px; width: 248px; min-width: 248px; height: 100vh;
          background: #071D36; border-right: 1px solid rgba(255,255,255,0.08);
          z-index: 201; transition: left 0.25s ease;
          box-shadow: 4px 0 32px rgba(0,0,0,0.4);
        }
        .ts-drawer.open { left: 0; }
        .ts-close-btn {
          position: absolute; top: 14px; right: 14px; background: none; border: none;
          cursor: pointer; color: ${C.ink3}; padding: 4px; border-radius: 6px; display: flex; z-index: 1;
        }
        @media (max-width: 768px) {
          .ts-sidebar { display: none; }
          .ts-mobile-bar { display: flex; }
          .ts-main { padding-top: 56px; }
        }
        @media (min-width: 769px) {
          .ts-drawer-overlay, .ts-drawer { display: none !important; }
        }
      `}</style>

      <div className="ts-shell">
        {/* Desktop sidebar  -  sticky, full height, never scrolls away */}
        <aside className="ts-sidebar">
          <SidebarContent />
        </aside>

        {/* Mobile top bar */}
        <div className="ts-mobile-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 30, height: 30, borderRadius: 8, background: C.brass, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 2px 8px rgba(212,170,58,0.35)' }}>
              <Zap size={15} color={C.ink} fill={C.ink} />
            </div>
            <span style={{ fontFamily: DISPLAY, fontSize: 16, fontWeight: 700, color: C.brass, letterSpacing: '-0.01em' }}>ProConnect</span>
          </div>
          <button onClick={() => setSidebarOpen(true)}
            style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, padding: '6px 8px', cursor: 'pointer', display: 'flex', color: 'rgba(255,255,255,0.8)' }}>
            <Menu size={18} />
          </button>
        </div>

        {/* Mobile drawer */}
        {sidebarOpen && (
          <>
            <div className="ts-drawer-overlay" onClick={() => setSidebarOpen(false)} style={{ display: 'block' }} />
            <div className={`ts-drawer open`} style={{ display: 'flex', flexDirection: 'column' }}>
              <button className="ts-close-btn" onClick={() => setSidebarOpen(false)}><X size={16} /></button>
              <SidebarContent />
            </div>
          </>
        )}

        {/* Main scrollable area */}
        <main className="ts-main">
          {children(ctx)}
        </main>
      </div>
    </>
  );
}

export default function TradieStudioLayout({ children }: Props) {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', background: '#FFF8E7' }} />}>
      <TradieStudioLayoutInner>{children}</TradieStudioLayoutInner>
    </Suspense>
  );
}
