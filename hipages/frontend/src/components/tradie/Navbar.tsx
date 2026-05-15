"use client";

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Zap, Shield, User, LogOut, LayoutGrid } from 'lucide-react';
import { useAuth } from '@/src/contexts/AuthContext';

export default function Navbar() {
    const { isAuthenticated, logout, user } = useAuth();
    const router = useRouter();

    return (
        <nav className="sticky top-0 z-[100] shadow-lg" style={{ background: '#071D36', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
            <div className="max-w-7xl mx-auto px-6 py-3.5 flex justify-between items-center">
                <Link href="/" className="flex items-center gap-2.5 group">
                    <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-md transition-transform group-hover:scale-105" style={{ background: '#D4AA3A', boxShadow: '0 4px 12px rgba(212,170,58,0.3)' }}>
                        <Zap className="w-5 h-5 fill-current" style={{ color: '#071D36' }} />
                    </div>
                    <span className="text-xl font-black tracking-tight" style={{ color: '#D4AA3A' }}>ProConnect</span>
                </Link>

                <div className="flex items-center gap-8">
                    <div className="hidden md:flex items-center gap-6">
                        <Link href="/search" className="nav-item group flex items-center gap-1.5 text-sm font-semibold transition-colors" style={{ color: 'rgba(255,255,255,0.8)' }}
                            onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
                            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}>Browse Tradies</Link>
                        <Link href="/how-it-works" className="nav-item group flex items-center gap-1.5 text-sm font-semibold transition-colors" style={{ color: 'rgba(255,255,255,0.8)' }}
                            onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
                            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}>How it Works</Link>
                    </div>

                    <div className="flex items-center gap-4">
                        {!isAuthenticated ? (
                            <>
                                <Link href="/signup?role=tradie" className="hidden sm:flex items-center gap-1.5 text-sm font-bold transition-colors"
                                    style={{ color: 'rgba(255,255,255,0.75)', borderRight: '1px solid rgba(255,255,255,0.15)', paddingRight: 16 }}
                                    onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
                                    onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.75)')}>
                                    <Shield className="w-4 h-4" style={{ color: '#5BB3FF' }} />
                                    Tradie Portal
                                </Link>
                                <Link href="/login" className="text-sm font-bold transition-colors"
                                    style={{ color: 'rgba(255,255,255,0.8)' }}
                                    onMouseEnter={e => (e.currentTarget.style.color = '#D4AA3A')}
                                    onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}>Login</Link>
                                <Link href="/signup" className="px-5 py-2.5 rounded-xl font-bold text-sm transition-all shadow-md"
                                    style={{ background: '#D4AA3A', color: '#071D36', boxShadow: '0 4px 12px rgba(212,170,58,0.3)' }}
                                    onMouseEnter={e => (e.currentTarget.style.background = '#E8C766')}
                                    onMouseLeave={e => (e.currentTarget.style.background = '#D4AA3A')}>Sign Up</Link>
                            </>
                        ) : (
                            <div className="flex items-center gap-4">
                                <Link
                                    href={user?.role === 'tradie' ? '/tradie/dashboard' : '/dashboard'}
                                    className="flex items-center gap-2 text-sm font-bold transition-colors group"
                                    style={{ color: '#D4AA3A' }}>
                                    <LayoutGrid className="w-4 h-4 transition-colors" style={{ color: '#5BB3FF' }} />
                                    Dashboard
                                </Link>
                                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full" style={{ background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.12)' }}>
                                    <User className="w-4 h-4" style={{ color: '#5BB3FF' }} />
                                    <span className="text-xs font-bold" style={{ color: 'rgba(255,255,255,0.9)' }}>{user?.email.split('@')[0]}</span>
                                    <button onClick={logout} className="p-1 transition-colors" style={{ color: 'rgba(255,255,255,0.5)' }}
                                        onMouseEnter={e => (e.currentTarget.style.color = '#FF6B6B')}
                                        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.5)')}>
                                        <LogOut className="w-3 h-3" />
                                    </button>
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </nav>
    );
}
