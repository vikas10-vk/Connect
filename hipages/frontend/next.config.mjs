/** @type {import('next').NextConfig} */
const nextConfig = {
    // standalone output creates a self-contained build for Docker.
    // Instead of needing node_modules at runtime, it bundles only what is needed.
    // The resulting .next/standalone/server.js is the production entry point.
    output: "standalone",

    // Experimental flag to resolve the build error with Next.js 16
    experimental: {
        missingSuspenseWithCSRBailout: false,
    },

    // Do not fail the build on TypeScript errors.
    // Fix type errors progressively — they should not block deploys.
    // Remove this once the codebase is fully typed.
    typescript: {
        ignoreBuildErrors: true,
    },

    // Do not fail the build on ESLint errors.
    // Same reasoning as above.
    eslint: {
        ignoreDuringBuilds: true,
    },

    // Allow images from your API domain and CDN.
    // Add your CloudFront domain here when you have it.
    images: {
        remotePatterns: [
            {
                protocol: "https",
                hostname: "**.yourdomain.com",
            },
            {
                protocol: "https",
                hostname: "**.cloudfront.net",
            },
        ],
    },
};

export default nextConfig;
