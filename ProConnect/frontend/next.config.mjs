/** @type {import('next').NextConfig} */
const nextConfig = {
    // Standalone output traces only the files actually used at runtime.
    // This produces a minimal Docker image (~80MB vs ~500MB).
    // Required by ProConnect/frontend/Dockerfile — do not remove.
    output: "standalone",

    // Build checks are release blockers — do NOT re-enable these ignores.
    // TypeScript errors fail the build. ESLint errors fail the build.
    typescript: {
        ignoreBuildErrors: false,
    },
    eslint: {
        ignoreDuringBuilds: false,
    },

    images: {
        remotePatterns: [
            // Cloudflare R2 public bucket — profile photos, job attachments, SWMS docs
            {
                protocol: "https",
                hostname: "pub-*.r2.dev",
            },
            // CloudFront CDN (if AWS S3 + CloudFront is used as a fallback)
            {
                protocol: "https",
                hostname: "**.cloudfront.net",
            },
            // Allow any HTTPS image during development / for user-submitted URLs
            // Remove this in production if you want strict image source control
            {
                protocol: "https",
                hostname: "**",
            },
        ],
    },
};

export default nextConfig;
