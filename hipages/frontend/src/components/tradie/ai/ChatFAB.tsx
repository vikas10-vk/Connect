"use client";

import { useState } from "react";
import { Sparkles, X } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { usePathname } from "next/navigation";
import { useAuth } from "@/src/contexts/AuthContext";
import AIChatInterface from "./AIChatInterface";

export default function ChatFAB() {
    const [isOpen, setIsOpen] = useState(false);
    const pathname = usePathname();
    const { isAuthenticated, user } = useAuth();
    const isTradie = user?.role === 'tradie';

    // Don't show on the dedicated chat page or auth pages
    const hiddenPaths = ["/ai-chat", "/login", "/signup"];
    if (hiddenPaths.some((p) => pathname?.startsWith(p))) return null;
    if (!isAuthenticated || isTradie) return null;

    return (
        <>
            {/* ── Full-screen overlay ─────────────────────────────────────────── */}
            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
                        onClick={() => setIsOpen(false)}
                    />
                )}
            </AnimatePresence>

            <AnimatePresence>
                {isOpen && (
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        transition={{ type: "spring", damping: 25, stiffness: 300 }}
                        className="fixed bottom-24 right-4 sm:right-6 z-50 w-[calc(100vw-2rem)] sm:w-[400px] h-[600px] bg-brand-cream rounded-3xl shadow-2xl overflow-hidden flex flex-col border border-gray-100"
                    >
                        {/* Chat header */}
                        <div className="bg-white border-b border-gray-100 px-5 py-4 flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl bg-brand-terracotta flex items-center justify-center shadow-md shadow-brand-terracotta/20">
                                <Sparkles className="w-5 h-5 text-white fill-current" />
                            </div>
                            <div>
                                <p className="font-bold text-gray-900 text-sm">ProConnect AI</p>
                                <p className="text-xs text-green-500 font-medium">● Online</p>
                            </div>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="ml-auto w-8 h-8 rounded-xl hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-gray-600 transition-colors"
                            >
                                <X className="w-4 h-4" />
                            </button>
                        </div>

                        {/* Chat interface fills the rest */}
                        <div className="flex-1 overflow-hidden">
                            <AIChatInterface />
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Floating action button ──────────────────────────────────────── */}
            <div className="fixed bottom-6 right-4 sm:right-6 z-50">
                {/* Pulse ring */}
                {!isOpen && (
                    <span className="absolute inset-0 rounded-2xl bg-brand-terracotta opacity-20 animate-ping" />
                )}

                <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => setIsOpen((prev) => !prev)}
                    className="relative w-14 h-14 rounded-2xl bg-brand-terracotta text-white flex items-center justify-center shadow-xl shadow-brand-terracotta/30 hover:shadow-2xl hover:shadow-brand-terracotta/40 transition-shadow"
                    aria-label="Open AI assistant"
                >
                    <AnimatePresence mode="wait">
                        {isOpen ? (
                            <motion.span
                                key="close"
                                initial={{ rotate: -90, opacity: 0 }}
                                animate={{ rotate: 0, opacity: 1 }}
                                exit={{ rotate: 90, opacity: 0 }}
                                transition={{ duration: 0.15 }}
                            >
                                <X className="w-6 h-6" />
                            </motion.span>
                        ) : (
                            <motion.span
                                key="open"
                                initial={{ rotate: 90, opacity: 0 }}
                                animate={{ rotate: 0, opacity: 1 }}
                                exit={{ rotate: -90, opacity: 0 }}
                                transition={{ duration: 0.15 }}
                            >
                                <Sparkles className="w-6 h-6 fill-current" />
                            </motion.span>
                        )}
                    </AnimatePresence>
                </motion.button>
            </div>
        </>
    );
}
