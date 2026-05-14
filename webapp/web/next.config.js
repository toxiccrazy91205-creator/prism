/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // Proxy API requests to FastAPI backend.
  // Set NEXT_PUBLIC_API_URL in Vercel env vars to point to your deployed backend.
  // Locally defaults to http://localhost:8000
  async rewrites() {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    return [
      {
        source: '/api/:path*',
        destination: `${apiBase}/api/:path*`,
      },
    ]
  },
}

module.exports = nextConfig
