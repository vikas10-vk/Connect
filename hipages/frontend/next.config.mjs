/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",
    typescript: {
        ignoreBuildErrors: true,
    },
    eslint: {
        ignoreDuringBuilds: true,
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
