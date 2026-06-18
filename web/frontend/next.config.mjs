/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  reactStrictMode: true,
  // Proxy API calls to the FastAPI backend so the frontend always talks to a
  // same-origin /api (no CORS, cookies work). In production nginx may handle
  // /api directly; this rewrite is the fallback / dev convenience.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
