import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

// INTERNAL_API_URL must be used for server-side fetches inside Docker
// (e.g. http://fastapi:8000). NEXT_PUBLIC_API_URL is browser-facing and
// resolves to localhost, which is NOT reachable from inside the Next container.
// Falling back to localhost:8000 is only safe for local dev without Docker.
const FASTAPI_BASE =
  process.env.INTERNAL_API_URL ||
  (process.env.NODE_ENV === 'development' ? 'http://fastapi:8000' : process.env.NEXT_PUBLIC_API_URL) ||
  'http://localhost:8000';

const MAX_UPLOAD_BYTES = 10_000_000; // 10 MB

/**
 * Sniff the real file type from its magic bytes instead of trusting the
 * client-supplied MIME type (file.type), which is trivially forged.
 * Returns the detected image MIME type, or null if not a supported image.
 */
function sniffImageType(bytes: Uint8Array): string | null {
  // JPEG - FF D8 FF
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return 'image/jpeg';
  }
  // PNG - 89 50 4E 47 0D 0A 1A 0A
  if (
    bytes.length >= 8 &&
    bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47 &&
    bytes[4] === 0x0d && bytes[5] === 0x0a && bytes[6] === 0x1a && bytes[7] === 0x0a
  ) {
    return 'image/png';
  }
  // WebP - "RIFF" .... "WEBP"
  if (
    bytes.length >= 12 &&
    bytes[0] === 0x52 && bytes[1] === 0x49 && bytes[2] === 0x46 && bytes[3] === 0x46 &&
    bytes[8] === 0x57 && bytes[9] === 0x45 && bytes[10] === 0x42 && bytes[11] === 0x50
  ) {
    return 'image/webp';
  }
  // HEIC / HEIF - ISO base media format: bytes 4-7 are "ftyp", brand at 8-11
  if (
    bytes.length >= 12 &&
    bytes[4] === 0x66 && bytes[5] === 0x74 && bytes[6] === 0x79 && bytes[7] === 0x70
  ) {
    const brand = String.fromCharCode(bytes[8], bytes[9], bytes[10], bytes[11]);
    if (['heic', 'heix', 'heif', 'hevc', 'mif1', 'msf1'].includes(brand)) {
      return 'image/heic';
    }
  }
  return null;
}

/**
 * POST /api/upload-photo
 * Accepts a multipart FormData with a single `file` field.
 *
 * Flow:
 *  1. Validate the file by its magic bytes (NOT the client-supplied MIME type)
 *  2. Call FastAPI /uploads/presign to get a presigned R2 URL  (server to server)
 *  3. PUT the raw file bytes directly to R2                     (server to R2)
 *  4. Return { key, public_url } to the browser
 *
 * If R2 is unavailable the request fails with 502. Uploads are NEVER written
 * into the Next.js public/ directory - doing so would serve unvalidated user
 * files as world-readable static assets straight from the frontend container.
 */
export async function POST(request: NextRequest) {
  try {
    // 1. Parse the uploaded file
    const formData = await request.formData();
    const file = formData.get('file') as File | null;

    if (!file) {
      return NextResponse.json({ detail: 'No file provided' }, { status: 400 });
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      return NextResponse.json({ detail: 'File must be under 10MB' }, { status: 400 });
    }

    // 2. Validate by magic bytes - do NOT trust file.type
    const fileBuffer = await file.arrayBuffer();
    const detectedType = sniffImageType(new Uint8Array(fileBuffer.slice(0, 16)));
    if (!detectedType) {
      return NextResponse.json(
        { detail: 'Unsupported file. Only JPEG, PNG, WebP and HEIC images are allowed.' },
        { status: 400 }
      );
    }

    // 3. Auth token (optional - the booking wizard runs before signup)
    const cookieStore = await cookies();
    const token = cookieStore.get('access_token')?.value;

    const authHeaders: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (token) authHeaders['Authorization'] = `Bearer ${token}`;

    // 4. Ask FastAPI for a presigned URL
    const presignRes = await fetch(`${FASTAPI_BASE}/api/v1/uploads/presign/`, {
      method: 'POST',
      headers: authHeaders,
      body: JSON.stringify({
        filename: file.name,
        content_type: detectedType,
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

    // 5. Upload file server -> R2
    let r2Ok = false;
    try {
      const r2Res = await fetch(upload_url, {
        method: 'PUT',
        body: fileBuffer,
        headers: { 'Content-Type': detectedType },
      });
      r2Ok = r2Res.ok;
      if (!r2Ok) {
        console.error('[upload-photo] R2 PUT failed:', r2Res.status, await r2Res.text());
      }
    } catch (err: any) {
      console.error('[upload-photo] R2 PUT error:', err?.message);
    }

    // If object storage is unavailable, fail loudly. We deliberately do NOT
    // fall back to writing the file into public/ - see the file header.
    if (!r2Ok) {
      return NextResponse.json(
        { detail: 'Upload storage is temporarily unavailable. Please try again.' },
        { status: 502 }
      );
    }

    // 6. Success
    return NextResponse.json({ key, public_url });

  } catch (err: any) {
    console.error('[upload-photo] Unexpected error:', err);
    return NextResponse.json(
      { detail: 'Upload failed. Please try again.' },
      { status: 500 }
    );
  }
}
