import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // The built staging site has one public origin; only /api is forwarded to
  // the loopback-only Python service. Never expose the Vite development server.
  preview: {
    allowedHosts: ['.trycloudflare.com'],
    proxy: {
      '/api': {
        target: process.env.XIAOMANG_STAGING_API_TARGET ?? 'http://127.0.0.1:8766',
        changeOrigin: false,
        timeout: 120_000,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
