"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Zap, Sparkles, ArrowLeft } from "lucide-react";
import { useAuth } from "@/src/contexts/AuthContext";
import AIChatInterface from "@/src/components/tradie/ai/AIChatInterface";

export default function AIChatPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-brand-ivory flex items-center justify-center">
        <div className="w-8 h-8 rounded-xl bg-brand-terracotta animate-pulse" />
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-brand-ivory flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-100 sticky top-0 z-[100]">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link
            href="/"
            className="w-9 h-9 rounded-xl hover:bg-gray-100 flex items-center justify-center text-gray-400 hover:text-gray-600 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </Link>

          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-brand-terracotta flex items-center justify-center shadow-md shadow-brand-terracotta/20">
              <Sparkles className="w-5 h-5 text-white fill-current" />
            </div>
            <div>
              <p className="font-bold text-gray-900 text-sm leading-none">ProConnect AI</p>
              <p className="text-xs text-green-500 font-medium mt-0.5">Online</p>
            </div>
          </div>

          <Link href="/" className="ml-auto flex items-center gap-1.5 group">
            <div className="w-7 h-7 rounded-lg bg-brand-terracotta flex items-center justify-center text-white group-hover:scale-105 transition-transform">
              <Zap className="w-4 h-4 fill-current" />
            </div>
            <span className="text-base font-bold tracking-tight text-brand-gold hidden sm:block">
              ProConnect
            </span>
          </Link>
        </div>
      </header>

      {/* Chat takes full remaining height */}
      <main className="flex-1 flex flex-col max-w-3xl w-full mx-auto">
        <AIChatInterface />
      </main>
    </div>
  );
}
