"use client";

import { CheckCircle2, MapPin, Zap, ArrowRight } from "lucide-react";
import Link from "next/link";

interface JobConfirmCardProps {
    data: {
        job_id: string;
        title: string;
        category: string;
        suburb: string;
        state: string;
        urgency: string;
        status: string;
    };
    props?: {
        show_next_steps?: boolean;
    };
}

const urgencyLabel: Record<string, string> = {
    emergency: "Emergency",
    asap: "ASAP",
    today: "Today",
    next_few_days: "Next few days",
    next_few_weeks: "Next few weeks",
    next_few_months: "Next few months",
    flexible: "Flexible",
};

const urgencyColor: Record<string, string> = {
    emergency: "bg-red-50 text-red-700",
    asap: "bg-orange-50 text-orange-700",
    today: "bg-yellow-50 text-yellow-700",
    flexible: "bg-green-50 text-green-700",
};

export default function JobConfirmCard({ data, props }: JobConfirmCardProps) {
    const urgencyClass =
        urgencyColor[data.urgency] || "bg-gray-50 text-gray-700";

    return (
        <div className="mt-3 bg-white border-2 border-brand-terracotta/20 rounded-2xl overflow-hidden">
            {/* Header */}
            <div className="bg-brand-terracotta/5 px-4 py-3 flex items-center gap-2 border-b border-brand-terracotta/10">
                <CheckCircle2 className="w-5 h-5 text-brand-terracotta shrink-0" />
                <p className="font-bold text-brand-terracotta text-sm">Job Posted Successfully</p>
            </div>

            {/* Body */}
            <div className="p-4 space-y-3">
                <p className="font-bold text-gray-900">{data.title}</p>

                <div className="flex flex-wrap gap-2">
                    <span className="inline-flex items-center gap-1 text-xs bg-brand-ivory text-gray-600 px-3 py-1 rounded-full">
                        <Zap className="w-3 h-3 text-brand-terracotta" />
                        {data.category}
                    </span>
                    <span className="inline-flex items-center gap-1 text-xs bg-brand-ivory text-gray-600 px-3 py-1 rounded-full">
                        <MapPin className="w-3 h-3" />
                        {data.suburb}, {data.state}
                    </span>
                    <span className={`text-xs px-3 py-1 rounded-full font-medium ${urgencyClass}`}>
                        {urgencyLabel[data.urgency] || data.urgency}
                    </span>
                </div>

                {props?.show_next_steps && (
                    <p className="text-xs text-gray-500">
                        Tradies in your area are being notified. You'll receive quotes shortly.
                    </p>
                )}

                <Link
                    href="/dashboard"
                    className="inline-flex items-center gap-2 text-xs font-bold text-brand-terracotta hover:opacity-80 transition-opacity"
                >
                    View in Dashboard
                    <ArrowRight className="w-3 h-3" />
                </Link>
            </div>
        </div>
    );
}
