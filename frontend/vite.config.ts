import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { nodePolyfills } from 'vite-plugin-node-polyfills'

// The API is proxied so the browser sees a single origin. That keeps cookies and
// CORS out of the picture entirely.
// The proxy follows VITE_API_TARGET so a machine whose :8000 is already taken can
// run the API elsewhere (`VITE_API_TARGET=http://127.0.0.1:8001 mise run dev:web`).
const apiTarget = process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [
    react(),
    // Circle's wallet frame SDK (#29) carries Node built-ins through jsonwebtoken. Only
    // those it reaches are polyfilled, and only the chunk loaded on "Set up your
    // wallet" pulls them in; no other page pays for them.
    nodePolyfills({ include: ['buffer', 'crypto', 'stream', 'util', 'vm'] }),
  ],
  server: {
    port: 5173,
    // Bind every interface. Without this Vite listens on ::1 only, so
    // 127.0.0.1:5173 refuses the connection while localhost:5173 works.
    // It also makes the demo reachable from a phone on the same network.
    host: true,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
      },
      // So the API reference is reachable from the app's own origin.
      '/docs': { target: apiTarget, changeOrigin: true },
      '/openapi.json': { target: apiTarget, changeOrigin: true },
    },
  },
})
