/**
 * app/api/suburbs/route.ts
 *
 * Proxy to backend GET /suburbs/search
 * Replaces previous Mapbox-based suburb autocomplete.
 *
 * Query params forwarded: q, limit, state
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET(req: NextRequest) {
    const { searchParams } = new URL(req.url);

    const q = searchParams.get("q") || "";
    const limit = searchParams.get("limit") || "8";
    const state = searchParams.get("state") || "";

    if (q.length < 2) {
        return NextResponse.json([]);
    }

    try {
        const params = new URLSearchParams({ q, limit });
        if (state) params.set("state", state);

        const res = await fetch(`${BACKEND_URL}/suburbs/search?${params.toString()}`, {
            // No auth needed — public endpoint
            headers: { "Content-Type": "application/json" },
            next: { revalidate: 3600 }, // Cache suburb results for 1 hour
        });

        if (!res.ok) {
            console.error("[suburbs] Backend error:", res.status);
            return NextResponse.json([], { status: 200 }); // Graceful empty fallback
        }

        const data = await res.json();
        return NextResponse.json(data);

    } catch (err) {
        console.error("[suburbs] Fetch error:", err);
        return NextResponse.json([], { status: 200 });
    }
}