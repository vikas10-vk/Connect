import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

const FASTAPI_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * POST /api/upload-photo
 * Accepts a multipart FormData with a single `file` field.
 *
 * Flow:
 *  1. Call FastAPI /uploads/presign to get a presigned R2 URL  (server→server, no CORS)
 *  2. PUT the raw file bytes directly to R2                     (server→R2, no CORS)
 *  3. Return { key, public_url } to the browser
 *
 * This avoids the browser CORS issue with direct-to-R2 uploads.
 */
export async function POST(request: NextRequest) {
  try {
    // ── 1. Parse the uploaded file ──────────────────────────────────────────
    const formData = await request.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return NextResponse.json({ detail: 'No file provided' }, { status: 400 });
    }

    if (file.size > 10_000_000) {
      return NextResponse.json({ detail: 'File must be under 10MB' }, { status: 400 });
    }

    if (!file.type.startsWith('image/')) {
      return NextResponse.json({ detail: 'Only image files are allowed' }, { status: 400 });
    }

    // ── 2. Get auth token ────────────────────────────────────────────────────
    const cookieStore = await cookies();
    const token = cookieStore.get('access_token')?.value;

    const authHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) authHeaders['Authorization'] = `Bearer ${token}`;

    // ── 3. Ask FastAPI for a presigned URL ───────────────────────────────────
    const presignRes = await fetch(`${FASTAPI_BASE}/api/v1/uploads/presign/`, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify({
        filename: file.name,
        content_type: file.type,
        context: 'job_photo',
      }),
    });

    if (!presignRes.ok) {
      const err = await presignRes.text();
      console.error('[upload-photo] presign failed:', err);
      return NextResponse.json(
        { detail: 'Failed to prepare upload. Please try again.' },
        { status: presignRes.status }
      );
    }

    const { upload_url, key, public_url } = await presignRes.json();

    // ── 4. Upload file server→R2 (no browser CORS involved) ─────────────────
    const fileBuffer = await file.arrayBuffer();

    let final_public_url = public_url;
    let r2Success = false;

    try {
      const r2Res = await fetch(upload_url, {
        method: 'PUT',
        body: fileBuffer,
        headers: { 'Content-Type': file.type },
      });

      if (r2Res.ok) {
        r2Success = true;
      } else {
        console.warn('[upload-photo] R2 PUT failed:', r2Res.status, await r2Res.text());
      }
    } catch (err: any) {
      console.warn('[upload-photo] R2 PUT error:', err.message);
    }

    // Fallback to local storage if R2 fails
    if (!r2Success) {
      const fs = require('fs/promises');
      const path = require('path');
      const localPath = path.join(process.cwd(), 'public', key);
      await fs.mkdir(path.dirname(localPath), { recursive: true });
      await fs.writeFile(localPath, Buffer.from(fileBuffer));
      final_public_url = `/${key}`;
    }

    // ── 5. Success — return the key and public URL ───────────────────────────
    return NextResponse.json({ key, public_url: final_public_url });

  } catch (err: any) {
    console.error('[upload-photo] Unexpected error:', err);
    return NextResponse.json(
      { detail: 'Upload failed. Please try again.' },
      { status: 500 }
    );
  }
}
