"use client";

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
    BookmarkCheck, ArrowRight, Trash2, Clock,
    MapPin, Zap, ChevronRight
} from 'lucide-react';

const DRAFT_KEY = 'proconnect_job_draft';

interface Draft {
    step: number;
    selectedCategory: string;
    jobTitle: string;
    description: string;
    suburb: string;
    state: string;
    urgency: string;
    savedAt: string;
}

const STEP_LABELS = ['', 'Service', 'Details', 'Location', 'Timing', 'Account'];
const STEP_COLORS = ['', '#D4AA3A', '#4F46E5', '#0EA5E9', '#8B5CF6', '#10B981'];

function timeAgo(iso: string): string {
    try {
        const diff = Date.now() - new Date(iso).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return `${mins}m ago`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs}h ago`;
        return `${Math.floor(hrs / 24)}d ago`;
    } catch { return ''; }
}

export default function DraftBanner() {
    const router = useRouter();
    const [draft, setDraft] = useState<Draft | null>(null);
    const [dismissed, setDismissed] = useState(false);

    useEffect(() => {
        try {
            const saved = localStorage.getItem(DRAFT_KEY);
            if (saved) setDraft(JSON.parse(saved));
        } catch { /* ignore */ }
    }, []);

    if (!draft || dismissed) return null;

    const progress = Math.round((draft.step / 5) * 100);
    const stepColor = STEP_COLORS[draft.step] || '#D4AA3A';
    const stepLabel = STEP_LABELS[draft.step] || 'Step ' + draft.step;

    const handleContinue = () => {
        router.push('/book');
    };

    const handleDelete = () => {
        try { localStorage.removeItem(DRAFT_KEY); } catch { /* ignore */ }
        setDismissed(true);
    };

    return (
        <div className="bg-white rounded-3xl border-2 border-dashed overflow-hidden mb-5 shadow-sm"
            style={{ borderColor: stepColor + '40' }}>

            {/* Top accent bar */}
            <div className="h-1 w-full" style={{ background: `linear-gradient(90deg, ${stepColor}, ${stepColor}88)` }} />

            <div className="p-5">
                {/* Header row */}
                <div className="flex items-start justify-between gap-4 mb-4">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-2xl flex items-center justify-center shrink-0"
                            style={{ background: stepColor + '15' }}>
                            <BookmarkCheck className="w-5 h-5" style={{ color: stepColor }} />
                        </div>
                        <div>
                            <p className="font-black text-brand-gold text-sm leading-tight">Unfinished job booking</p>
                            <p className="text-xs text-brand-gold/50 mt-0.5 flex items-center gap-1">
                                <Clock className="w-3 h-3" /> Saved {timeAgo(draft.savedAt)}
                            </p>
                        </div>
                    </div>

                    {/* Delete */}
                    <button onClick={handleDelete}
                        className="w-8 h-8 rounded-xl bg-red-50 text-brand-gold flex items-center justify-center hover:bg-red-100 hover:text-red-600 transition-all shrink-0">
                        <Trash2 className="w-3.5 h-3.5" />
                    </button>
                </div>

                {/* Draft details */}
                <div className="bg-brand-gold/5 rounded-2xl p-4 mb-4 space-y-2">
                    {draft.selectedCategory && (
                        <div className="flex items-center gap-2">
                            <Zap className="w-3.5 h-3.5 text-brand-gold/50 shrink-0" />
                            <span className="text-xs font-bold text-brand-gold">{draft.selectedCategory}</span>
                        </div>
                    )}
                    {draft.jobTitle && (
                        <div className="flex items-center gap-2">
                            <BookmarkCheck className="w-3.5 h-3.5 text-brand-gold/50 shrink-0" />
                            <span className="text-xs text-brand-gold/80 truncate">{draft.jobTitle}</span>
                        </div>
                    )}
                    {draft.suburb && (
                        <div className="flex items-center gap-2">
                            <MapPin className="w-3.5 h-3.5 text-brand-gold/50 shrink-0" />
                            <span className="text-xs text-brand-gold/80">{draft.suburb}, {draft.state}</span>
                        </div>
                    )}
                </div>

                {/* Progress bar */}
                <div className="mb-4">
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs font-bold text-brand-gold/70">
                            Stopped at step {draft.step}: <span style={{ color: stepColor }}>{stepLabel}</span>
                        </span>
                        <span className="text-xs font-bold" style={{ color: stepColor }}>{progress}%</span>
                    </div>
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <div className="h-full rounded-full transition-all"
                            style={{ width: `${progress}%`, background: `linear-gradient(90deg, ${stepColor}, ${stepColor}bb)` }} />
                    </div>

                    {/* Step pills */}
                    <div className="flex gap-1 mt-2">
                        {STEP_LABELS.slice(1).map((label, i) => {
                            const stepNum = i + 1;
                            const done = stepNum < draft.step;
                            const current = stepNum === draft.step;
                            return (
                                <div key={label} className="flex-1 text-center">
                                    <span className={`text-[9px] font-bold block py-0.5 px-1 rounded-md ${done ? 'bg-emerald-100 text-emerald-700' :
                                            current ? 'text-white' :
                                                'bg-gray-50 text-brand-gold/50'
                                        }`}
                                        style={current ? { background: stepColor } : {}}>
                                        {done ? 'Done' : label}
                                    </span>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Action buttons */}
                <div className="flex gap-2">
                    <button onClick={handleContinue}
                        className="flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl font-bold text-sm text-white transition-all hover:opacity-90 hover:-translate-y-0.5"
                        style={{ background: `linear-gradient(135deg, ${stepColor}, ${stepColor}cc)` }}>
                        Continue booking
                        <ArrowRight className="w-4 h-4" />
                    </button>
                    <button onClick={handleDelete}
                        className="px-4 py-3 rounded-2xl font-bold text-sm bg-gray-100 text-brand-gold/80 hover:bg-gray-200 transition-colors">
                        Discard
                    </button>
                </div>
            </div>
        </div>
    );
}