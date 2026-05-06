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
        <nav className="bg-white/90 backdrop-blur-md border-b border-gray-100 sticky top-0 z-[100] shadow-sm">
            <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
                <Link href="/" className="flex items-center gap-2 group">
                    <div className="w-10 h-10 rounded-xl bg-brand-terracotta flex items-center justify-center text-white shadow-lg shadow-brand-terracotta/20 group-hover:scale-105 transition-transform">
                        <Zap className="w-6 h-6 fill-current" />
                    </div>
                    <span className="text-2xl font-bold tracking-tight text-brand-terracotta">ProConnect</span>
                </Link>

                <div className="flex items-center gap-8">
                    <div className="hidden md:flex items-center gap-6">
                        <Link href="/search" className="text-sm font-medium text-gray-600 hover:text-brand-terracotta transition-colors">Browse Tradies</Link>
                        <Link href="/how-it-works" className="text-sm font-medium text-gray-600 hover:text-brand-terracotta transition-colors">How it Works</Link>
                    </div>

                    <div className="flex items-center gap-4">
                        {!isAuthenticated ? (
                            <>
                                <Link href="/signup?role=tradie" className="hidden sm:flex items-center gap-2 text-brand-terracotta font-bold text-sm hover:opacity-80 transition-opacity">
                                    <Shield className="w-4 h-4" />
                                    Tradie Portal
                                </Link>
                                <div className="h-4 w-px bg-gray-200 hidden sm:block" />
                                <Link href="/login" className="text-brand-terracotta font-bold text-sm hover:opacity-80 transition-opacity">
                                    Login
                                </Link>
                                <Link href="/signup" className="bg-brand-terracotta text-white px-6 py-2.5 rounded-xl font-bold text-sm hover:shadow-lg hover:shadow-brand-terracotta/20 transition-all">
                                    Sign Up
                                </Link>
                            </>
                        ) : (
                            <div className="flex items-center gap-4">
                                <Link
                                    href={user?.role === 'tradie' ? '/tradie/dashboard' : '/dashboard'}
                                    className="flex items-center gap-2 text-brand-terracotta font-bold text-sm"
                                >
                                    <LayoutGrid className="w-4 h-4" />
                                    Dashboard
                                </Link>
                                <div className="flex items-center gap-2 bg-gray-50 px-3 py-1.5 rounded-full border border-gray-100">
                                    <User className="w-4 h-4 text-brand-terracotta" />
                                    <span className="text-xs font-bold text-gray-700">{user?.email.split('@')[0]}</span>
                                    <button onClick={logout} className="p-1 hover:text-red-500 transition-colors">
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
