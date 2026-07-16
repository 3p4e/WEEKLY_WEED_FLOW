import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// During dev, proxy API calls to the FastAPI backend so the SPA is same-origin.
// The backend mounts these prefixes: /auth /samples /specifications /coa /oos
// /audit /health /ai. In production the built assets are served by FastAPI's
// StaticFiles mount, so no proxy is needed there.
const BACKEND = process.env.VITE_BACKEND_URL || 'http://localhost:8000';
const apiPrefixes = ['/auth', '/samples', '/specifications', '/coa', '/oos', '/audit', '/health', '/ai'];

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: Object.fromEntries(
      apiPrefixes.map((p) => [p, { target: BACKEND, changeOrigin: true }])
    ),
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
