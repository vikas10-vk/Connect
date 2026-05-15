/**
 * app/api/suburbs/route.ts
 *
 * Proxy to backend GET /api/v1/suburbs/search
 * Replaces previous Mapbox-based suburb autocomplete.
 *
 * NOTE: The backend suburbs router is mounted under /api/v1 (main.py line ~199)
 * so the full path is /api/v1/suburbs/search — consistent with all other routers.
 *
 * Query params forwarded: q, limit, state
 */
import { NextRequest, NextResponse } from "next/server";

// INTERNAL_API_URL is used for server-side fetches inside Docker (http://fastapi:8000).
// NEXT_PUBLIC_API_URL is browser-facing and resolves to localhost — not reachable from
// inside the Next.js container, so it must only be the fallback for local dev (no Docker).
const BACKEND_URL =
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";

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

        const res = await fetch(`${BACKEND_URL}/api/v1/suburbs/search?${params.toString()}`, {
            // No auth needed — public endpoint
            headers: { "Content-Type": "application/json" },
            next: { revalidate: 86400 }, // Cache suburb results for 24 hours (static data)
            cache: "force-cache",
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