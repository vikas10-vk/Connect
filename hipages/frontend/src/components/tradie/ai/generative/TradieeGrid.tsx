"use client";

import { MapPin, Star, CheckCircle2, ArrowRight } from "lucide-react";

interface Tradie {
    id: string;
    business_name: string;
    suburb: string;
    state: string;
    radius_km?: number;
    is_available: boolean;
    rating?: number;
    review_count?: number;
}

interface TradieeGridProps {
    data: {
        tradies: Tradie[];
    };
    props?: {
        show_map?: boolean;
        show_action?: boolean;
        variant?: string;
    };
}

export default function TradieeGrid({ data, props }: TradieeGridProps) {
    const { tradies } = data;

    if (!tradies || tradies.length === 0) {
        return (
            <div className="mt-3 p-4 rounded-2xl bg-brand-ivory border border-brand-terracotta/10 text-sm text-gray-500 text-center">
                No tradies found in that area yet. Try a nearby suburb.
            </div>
        );
    }

    return (
        <div className="mt-3 space-y-2">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-1">
                {tradies.length} tradie{tradies.length !== 1 ? "s" : ""} found
            </p>
            {tradies.map((tradie) => (
                <div
                    key={tradie.id}
                    className="bg-white border border-gray-100 rounded-2xl p-4 hover:border-brand-terracotta/20 hover:shadow-md transition-all duration-200 group"
                >
                    <div className="flex items-start justify-between gap-3">
                        {/* Avatar placeholder */}
                        <div className="w-10 h-10 rounded-xl bg-brand-terracotta/10 flex items-center justify-center shrink-0">
                            <span className="text-brand-terracotta font-bold text-sm">
                                {(tradie.business_name || "?")[0].toUpperCase()}
                            </span>
                        </div>

                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                                <p className="font-bold text-gray-900 text-sm truncate">
                                    {tradie.business_name}
                                </p>
                                {tradie.is_available && (
                                    <span className="inline-flex items-center gap-1 text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full font-medium">
                                        <CheckCircle2 className="w-3 h-3" />
                                        Available
                                    </span>
                                )}
                            </div>

                            <div className="flex items-center gap-3 mt-1 flex-wrap">
                                <span className="flex items-center gap-1 text-xs text-gray-500">
                                    <MapPin className="w-3 h-3" />
                                    {tradie.suburb}, {tradie.state}
                                </span>
                                {tradie.radius_km && (
                                    <span className="text-xs text-gray-400">
                                        · serves {tradie.radius_km}km radius
                                    </span>
                                )}
                                {tradie.rating && (
                                    <span className="flex items-center gap-1 text-xs text-gray-500">
                                        <Star className="w-3 h-3 text-yellow-400 fill-yellow-400" />
                                        {tradie.rating.toFixed(1)}
                                        {tradie.review_count && (
                                            <span className="text-gray-400">({tradie.review_count})</span>
                                        )}
                                    </span>
                                )}
                            </div>
                        </div>

                        {props?.show_action && (
                            <button className="shrink-0 flex items-center gap-1 text-xs font-bold text-brand-terracotta bg-brand-terracotta/5 hover:bg-brand-terracotta hover:text-white px-3 py-1.5 rounded-xl transition-all duration-200">
                                Quote
                                <ArrowRight className="w-3 h-3" />
                            </button>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
