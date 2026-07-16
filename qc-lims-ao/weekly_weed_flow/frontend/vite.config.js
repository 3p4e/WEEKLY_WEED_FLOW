import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev proxy mirrors the nginx prod proxy: API path-prefixes → backend.
const API = ['/auth', '/tasks', '/weeks', '/departments', '/ai', '/health'];

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      API.map((p) => [p, { target: 'http://localhost:8000', changeOrigin: true }])
    ),
  },
});
