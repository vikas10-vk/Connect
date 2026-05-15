import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

const FASTAPI_BASE =
    process.env.INTERNAL_API_URL ||
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
    const path = pathSegments.join("/");
    const search = request.nextUrl.search || "";
    const targetUrl = `${FASTAPI_BASE}/api/v1/${path}${search}`;

    // Auth token — cookie first, then Authorization header
    const cookieStore = await cookies();
    const token = cookieStore.get("access_token")?.value;
    const incomingAuth = request.headers.get("Authorization");

    // ── Headers ────────────────────────────────────────────────────────────────
    // CRITICAL: Do NOT set Content-Type for multipart/form-data requests.
    // When Content-Type is hardcoded to application/json, the multipart boundary
    // is lost and FastAPI cannot parse the uploaded file — it returns 422.
    // Instead, detect the incoming content type and forward it as-is.
    // For JSON requests (no content type set), default to application/json.
    const headers: Record<string, string> = {};

    const incomingContentType = request.headers.get("content-type");

    if (incomingContentType) {
        // Forward the exact content-type including multipart boundary.
        // e.g. "multipart/form-data; boundary=----WebKitFormBoundaryXYZ"
        headers["Content-Type"] = incomingContentType;
    } else if (["POST", "PUT", "PATCH"].includes(method)) {
        // Default to JSON for mutation requests that don't specify content type
        headers["Content-Type"] = "application/json";
    }

    // Attach auth token
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    } else if (incomingAuth) {
        headers["Authorization"] = incomingAuth;
    }

    // ── Body ───────────────────────────────────────────────────────────────────
    // For file uploads (multipart/form-data): forward raw bytes via arrayBuffer.
    // For JSON requests: forward as text.
    // GET/DELETE: no body.
    let body: BodyInit | undefined;

    if (["POST", "PUT", "PATCH"].includes(method)) {
        if (incomingContentType?.includes("multipart/form-data")) {
            // Forward raw binary — required for file uploads.
            // Using text() here would corrupt binary file data.
            try {
                body = await request.arrayBuffer();
            } catch { /* no body */ }
        } else {
            try {
                const text = await request.text();
                if (text) body = text;
            } catch { /* no body */ }
        }
    }

    // ── Proxy the request ──────────────────────────────────────────────────────
    try {
        const response = await fetch(targetUrl, {
            method,
            headers,
            body,
            redirect: "follow",
        });

        // 204 No Content — return immediately, no body to read
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