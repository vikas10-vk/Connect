/** @type {import('next').NextConfig} */
const nextConfig = {
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
