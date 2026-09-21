/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [],
  },
  // The dev server refuses /_next/* asset requests from clients that don't
  // match its origin (browsers on the LAN hitting the machine's IP/hostname
  // get an unstyled, non-hydrated page). Allow the typical dev-machine
  // access patterns; production (`next start`/standalone) is unaffected.
  allowedDevOrigins: [
    "localhost",
    "127.0.0.1",
    "*.local",
    "172.23.*.*",
    "192.168.*.*",
    "10.*.*.*",
  ],
  // Same-origin API proxy: the browser always talks to the origin that
  // served the page (works via localhost, LAN IP, SSH tunnel, any port),
  // and the Next server forwards to the backend over the compose network.
  // BACKEND_INTERNAL_URL defaults to the host-dev backend.
  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backend}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
