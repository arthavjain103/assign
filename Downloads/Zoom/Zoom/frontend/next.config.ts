import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Use webpack bundler (Turbopack has native binary issues on some Windows environments)
  turbopack: undefined,
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
      },
    ],
    unoptimized: false,
  },
};

export default nextConfig;
