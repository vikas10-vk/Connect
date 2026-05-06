"use client";

import React, { useEffect, useState, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import {
  Zap, Loader2, LayoutDashboard, Search,
  Sparkles, LogOut, Briefcase,
  ChevronRight, Settings, Menu, X, History,
  CheckCircle2, ArrowRight,
} from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';
import HomeownerDashboardView from './HomeownerDashboardView';

// ── Palette (matches dashboard) ───────────────────────────────────────────────
const CREAM = '#FBF8EF';
const CREAM2 = '#F1EBDD';
const TERRA = '#D4AA3A';
const TERRA_MID = '#EBCB66';
const TERRA_DRK = '#0D2544';
const INK = '#071D36';
const INK2 = '#173452';
const INK3 = '#56677A';
const INK4 = '#8A785A';
const BORDER = '#E9DDBF';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, exact: true },
  { href: '/book', label: 'Post a Job', icon: Briefcase },
  { href: '/search', label: 'Find Tradies', icon: Search },
  { href: '/dashboard?view=history', label: 'Job History', icon: History, viewParam: 'history' },
  { href: '/dashboard?view=completed', label: 'Completed Jobs', icon: CheckCircle2, viewParam: 'completed' },
];

function DashboardContent() {
  const { user, logout, isLoading, isAuthenticated } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentView = searchParams.get('view');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 1024);
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  useEffect(() => {
    if (!isLoading) {
      if (!isAuthenticated) router.push('/login');
      else if (user?.role === 'tradie') router.push('/tradie/dashboard');
    }
  }, [isLoading, isAuthenticated, user, router]);

  if (isLoading) {
    return (
      <div style={{ minHeight: '100vh', background: CREAM, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Loader2 style={{ width: 36, height: 36, color: TERRA, animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  const firstName = user?.name?.split(' ')[0] || user?.email?.split('@')[0] || 'there';
  const userInitials = (user?.name || user?.email || 'U').slice(0, 2).toUpperCase();

  const isActive = (item: typeof NAV_ITEMS[0]) => {
    if (item.viewParam) return currentView === item.viewParam;
    if (item.exact) return pathname === '/dashboard' && !currentView;
    return pathname === item.href;
  };

  return (
    <div style={{ minHeight: '100vh', background: CREAM, display: 'flex', fontFamily: "'DM Sans', sans-serif", overflowX: 'hidden', maxWidth: '100vw' }}>

      {/* ── Mobile overlay ── */}
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(7,29,54,.35)', zIndex: 30 }}
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        style={{
          width: 240,
          minWidth: 240,
          flexShrink: 0,
          background: '#fff',
          borderRight: `1px solid ${BORDER}`,
          display: 'flex',
          flexDirection: 'column',
          height: '100vh',
          position: 'fixed',
          top: 0,
          left: 0,
          zIndex: 40,
          transition: 'transform .3s',
          transform: isMobile
            ? (sidebarOpen ? 'translateX(0)' : 'translateX(-100%)')
            : 'none',
        }}
      >
        {/* Logo */}
        <div style={{ padding: '20px 20px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: `1px solid ${BORDER}` }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
            <div style={{ width: 34, height: 34, background: TERRA, borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: `0 4px 12px rgba(212,170,58,.25)` }}>
              <Zap style={{ width: 18, height: 18, fill: '#fff', color: '#fff' }} />
            </div>
            <span style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: 17, color: TERRA }}>ProConnect</span>
          </Link>
          {isMobile && (
            <button
              onClick={() => setSidebarOpen(false)}
              style={{ width: 28, height: 28, borderRadius: 8, border: 'none', background: CREAM2, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: INK4 }}
            >
              <X style={{ width: 14, height: 14 }} />
            </button>
          )}
        </div>

        {/* User chip */}
        <div style={{ margin: '14px 14px 0', background: CREAM2, borderRadius: 14, padding: '11px 12px', display: 'flex', alignItems: 'center', gap: 10, border: `1px solid ${BORDER}` }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: TERRA, color: '#fff', fontFamily: 'Syne, sans-serif', fontWeight: 800, fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            {userInitials}
          </div>
          <div style={{ minWidth: 0 }}>
            <p style={{ fontSize: 13, fontWeight: 600, color: TERRA_DRK, lineHeight: 1.2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{firstName}</p>
            <p style={{ fontSize: 10, color: INK4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.email}</p>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '6px 8px', display: 'flex', flexDirection: 'column', gap: 1, overflowY: 'auto' }}>
          <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '.1em', textTransform: 'uppercase', color: INK4, padding: '14px 10px 6px' }}>Menu</p>
          {NAV_ITEMS.map(item => {
            const active = isActive(item);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setSidebarOpen(false)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '9px 12px', borderRadius: 12,
                  textDecoration: 'none', fontSize: 13, fontWeight: 600,
                  color: active ? '#fff' : INK2,
                  background: active ? TERRA : 'transparent',
                  transition: 'all .15s',
                }}
                onMouseEnter={e => { if (!active) e.currentTarget.style.background = CREAM2; }}
                onMouseLeave={e => { if (!active) e.currentTarget.style.background = 'transparent'; }}
              >
                <div style={{
                  width: 28, height: 28, borderRadius: 9, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: active ? 'rgba(255,255,255,.2)' : CREAM2,
                }}>
                  <item.icon style={{ width: 14, height: 14, color: active ? '#fff' : TERRA }} />
                </div>
                <span style={{ flex: 1 }}>{item.label}</span>
                {active && <ChevronRight style={{ width: 14, height: 14, opacity: .7 }} />}
              </Link>
            );
          })}
        </nav>


        {/* Bottom */}
        <div style={{ padding: '10px 8px', borderTop: `1px solid ${BORDER}`, display: 'flex', gap: 4 }}>
          {[
            { icon: Settings, label: 'Settings', href: '/settings', danger: false },
            { icon: LogOut, label: 'Sign Out', onClick: logout, danger: true },
          ].map(({ icon: Icon, label, href, onClick, danger }) => {
            const El = href ? Link : 'button';
            const props: any = href
              ? { href, style: {}, onClick: () => setSidebarOpen(false) }
              : { onClick, style: { background: 'none', border: 'none', width: '100%' } };
            return (
              <El
                key={label}
                {...props}
                style={{
                  flex: 1, display: 'flex', alignItems: 'center', gap: 6,
                  padding: '8px 10px', borderRadius: 10,
                  fontSize: 12, fontWeight: 500,
                  color: danger ? '#A33030' : INK3,
                  textDecoration: 'none', cursor: 'pointer',
                  background: 'none', border: 'none',
                  transition: 'background .15s',
                  ...props.style,
                }}
                onMouseEnter={(e: any) => e.currentTarget.style.background = danger ? '#FFEBEB' : CREAM2}
                onMouseLeave={(e: any) => e.currentTarget.style.background = 'none'}
              >
                <Icon style={{ width: 14, height: 14, opacity: .75 }} /> {label}
              </El>
            );
          })}
        </div>
      </aside>

      {/* ── Main ── */}
      <div style={{ flex: 1, minWidth: 0, width: '100%', maxWidth: '100vw', marginLeft: isMobile ? 0 : 240, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Mobile topbar — only on mobile */}
        {isMobile && (
          <div
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 18px',
              background: '#fff', borderBottom: `1px solid ${BORDER}`,
              position: 'sticky', top: 0, zIndex: 20,
              width: '100%', maxWidth: '100vw',
            }}>
            <button
              onClick={() => setSidebarOpen(true)}
              style={{ width: 36, height: 36, borderRadius: 10, background: CREAM2, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', color: INK3 }}
            >
              <Menu style={{ width: 16, height: 16 }} />
            </button>
            <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
              <div style={{ width: 28, height: 28, borderRadius: 8, background: TERRA, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <Zap style={{ width: 14, height: 14, fill: '#fff', color: '#fff' }} />
              </div>
              <span style={{ fontFamily: 'Syne, sans-serif', fontWeight: 800, color: TERRA, fontSize: 15 }}>ProConnect</span>
            </Link>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: CREAM2, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ color: TERRA, fontSize: 12, fontWeight: 800 }}>{userInitials}</span>
            </div>
          </div>
        )}

        <main style={{ flex: 1, overflowY: 'auto', overflowX: 'hidden', width: '100%', maxWidth: '100vw' }}>
          <HomeownerDashboardView />
        </main>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', background: CREAM, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Loader2 style={{ width: 36, height: 36, color: TERRA, animation: 'spin 1s linear infinite' }} /></div>}>
      <DashboardContent />
    </Suspense>
  );
}
