"use client";

import TradieeGrid from "@/src/components/tradie/ai/generative/TradieeGrid";
import JobConfirmCard from "@/src/components/tradie/ai/generative/JobConfirmCard";
import PhotoAnalysisCard from "@/src/components/tradie/ai/generative/PhotoAnalysisCard";

export interface UIComponent {
    type: string;
    data: Record<string, any>;
    props?: Record<string, any>;
}

interface MessageRendererProps {
    component: UIComponent;
}

/**
 * MessageRenderer
 * ---------------
 * Reads the ui_component spec returned by the AI backend
 * and renders the correct Tailwind component inline inside
 * the chat message thread.
 *
 * To add a new component:
 *   1. Create it in ./generative/YourComponent.tsx
 *   2. Import it here
 *   3. Add a case to the switch below
 */
export default function MessageRenderer({ component }: MessageRendererProps) {
    if (!component?.type) return null;

    const { type, data, props } = component;

    switch (type) {
        case "TradieeGrid":
            return <TradieeGrid data={data as any} props={props} />;

        case "JobConfirmCard":
            return <JobConfirmCard data={data as any} props={props} />;

        case "PhotoAnalysisCard":
            return <PhotoAnalysisCard data={data as any} props={props} />;

        // ── Stubs for future components ──────────────────────────────────────
        case "QuoteComparison":
            return (
                <div className="mt-3 p-4 bg-brand-ivory rounded-2xl text-sm text-gray-500 border border-gray-100">
                    📋 Quote comparison coming soon
                </div>
            );

        case "HomeHealthChart":
            return (
                <div className="mt-3 p-4 bg-brand-ivory rounded-2xl text-sm text-gray-500 border border-gray-100">
                    🏠 Home health chart coming soon
                </div>
            );

        case "EarningsSummary":
            return (
                <div className="mt-3 p-4 bg-brand-ivory rounded-2xl text-sm text-gray-500 border border-gray-100">
                    💰 Earnings summary coming soon
                </div>
            );

        case "LeadGrid":
            return (
                <div className="mt-3 p-4 bg-brand-ivory rounded-2xl text-sm text-gray-500 border border-gray-100">
                    📬 Lead cards coming soon
                </div>
            );

        default:
            // Unknown component — fail silently, don't break chat
            console.warn(`[MessageRenderer] Unknown component type: ${type}`);
            return null;
    }
}
