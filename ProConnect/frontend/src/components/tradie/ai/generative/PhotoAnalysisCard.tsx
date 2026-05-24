"use client";

import { AlertTriangle, Wrench, Clock, Shield } from "lucide-react";

interface PhotoAnalysisCardProps {
    data: {
        problem_title: string;
        problem_description: string;
        trade_required: string;
        urgency: string;
        urgency_reason: string;
        estimated_job_type: string;
        visible_damage: string[];
        safety_risk: boolean;
        safety_note: string | null;
        confidence: string;
    };
    props?: {
        show_post_job_btn?: boolean;
        urgency_banner?: boolean;
    };
}

const urgencyConfig: Record<string, { label: string; color: string; bg: string }> = {
    emergency: { label: "Emergency", color: "text-red-700", bg: "bg-red-50 border-red-200" },
    asap: { label: "ASAP", color: "text-orange-700", bg: "bg-orange-50 border-orange-200" },
    next_few_days: { label: "This week", color: "text-yellow-700", bg: "bg-yellow-50 border-yellow-200" },
    flexible: { label: "Flexible", color: "text-green-700", bg: "bg-green-50 border-green-200" },
};

export default function PhotoAnalysisCard({ data, props }: PhotoAnalysisCardProps) {
    const urgency = urgencyConfig[data.urgency] || urgencyConfig.flexible;

    return (
        <div className="mt-3 bg-white border border-gray-100 rounded-2xl overflow-hidden shadow-sm">
            {/* Safety banner */}
            {data.safety_risk && (
                <div className="bg-red-500 text-white px-4 py-2 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0" />
                    <p className="text-xs font-bold">{data.safety_note || "Safety risk detected  -  act promptly"}</p>
                </div>
            )}

            {/* Urgency banner */}
            {props?.urgency_banner && !data.safety_risk && (
                <div className={`border-b px-4 py-2 flex items-center gap-2 ${urgency.bg}`}>
                    <Clock className={`w-4 h-4 shrink-0 ${urgency.color}`} />
                    <p className={`text-xs font-bold ${urgency.color}`}>
                        {urgency.label}  -  {data.urgency_reason}
                    </p>
                </div>
            )}

            <div className="p-4 space-y-3">
                {/* Header */}
                <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-xl bg-brand-terracotta/10 flex items-center justify-center shrink-0">
                        <Wrench className="w-4 h-4 text-brand-terracotta" />
                    </div>
                    <div>
                        <p className="font-bold text-gray-900 text-sm leading-tight">{data.problem_title}</p>
                        <span className="text-xs text-gray-500">{data.trade_required}  |  {data.estimated_job_type}</span>
                    </div>
                </div>

                {/* Description */}
                <p className="text-sm text-gray-600 leading-relaxed">{data.problem_description}</p>

                {/* Damage list */}
                {data.visible_damage && data.visible_damage.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                        {data.visible_damage.map((item, i) => (
                            <span key={i} className="text-xs bg-brand-ivory text-gray-600 px-2.5 py-1 rounded-full">
                                {item}
                            </span>
                        ))}
                    </div>
                )}

                {/* Urgency + confidence row */}
                <div className="flex items-center justify-between pt-1">
                    <span className={`text-xs font-semibold px-3 py-1 rounded-full border ${urgency.bg} ${urgency.color}`}>
                        {urgency.label}
                    </span>
                    <span className="flex items-center gap-1 text-xs text-gray-400">
                        <Shield className="w-3 h-3" />
                        {data.confidence} confidence
                    </span>
                </div>
            </div>
        </div>
    );
}
