import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const FASTAPI_BASE = process.env.INTERNAL_API_URL ||
    (process.env.NODE_ENV === "development" ? "http://fastapi:8000" : process.env.NEXT_PUBLIC_API_URL) ||
    "http://localhost:8000";

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
    const { path } = await params;
    return proxyRequest(request, path, "GET");
}
export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
    const { path } = await params;
    return proxyRequest(request, path, "POST");
}
export async function PUT(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
    const { path } = await params;
    return proxyRequest(request, path, "PUT");
}
export async function PATCH(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
    const { path } = await params;
    return proxyRequest(request, path, "PATCH");
}
export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
    const { path } = await params;
    return proxyRequest(request, path, "DELETE");
}

async function proxyRequest(request: NextRequest, pathSegments: string[], method: string) {
    // Build FastAPI URL verbatim
    const path = pathSegments.join("/");
    const search = request.nextUrl.search || "";
    const targetUrl = `${FASTAPI_BASE}/api/v1/${path}${search}`;

    // Read access_token cookie → forward as Bearer header
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;

    // Fallback: read Authorization header forwarded by the client (e.g. axios)
    const incomingAuth = request.headers.get("Authorization");

    const headers: Record<string, string> = {
        "Content-Type": "application/json",
    };
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    } else if (incomingAuth) {
        headers["Authorization"] = incomingAuth;
    }

    // Forward body for mutating methods
    let body: string | undefined;
    if (["POST", "PUT", "PATCH"].includes(method)) {
        try {
            const text = await request.text();
            if (text) body = text;
        } catch { /* no body */ }
    }

    try {
        const response = await fetch(targetUrl, {
            method,
            headers,
            body,
            redirect: "follow",
        });

        // ── FIX: 204 has no body — return immediately ──────────────────────────
        if (response.status === 204) {
            return new NextResponse(null, { status: 204 });
        }

        const responseText = await response.text();

        return new NextResponse(responseText, {
            status: response.status,
            headers: {
                "Content-Type": response.headers.get("Content-Type") || "application/json",
            },
        });
    } catch (error) {
        console.error(`[PROXY] ${method} ${targetUrl} failed:`, error);
        return NextResponse.json(
            { detail: "Upstream service unavailable" },
            { status: 503 }
        );
    }
}