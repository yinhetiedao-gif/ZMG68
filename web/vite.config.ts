import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { execFileSync } from 'node:child_process'

function buildCommit(): string {
  const deployedCommit = process.env.RENDER_GIT_COMMIT
  if (/^[a-f0-9]{40}$/i.test(deployedCommit ?? '')) return deployedCommit!.toLowerCase()
  try {
    // A dirty local build cannot truthfully claim to be the committed version.
    if (execFileSync('git', ['status', '--porcelain'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()) return 'UNKNOWN'
    const commit = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
    return /^[a-f0-9]{40}$/i.test(commit) ? commit : 'UNKNOWN'
  } catch { return 'UNKNOWN' }
}

export default defineConfig({
  define: { 'import.meta.env.VITE_BUILD_COMMIT': JSON.stringify(buildCommit()) },
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
