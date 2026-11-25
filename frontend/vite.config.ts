/// <reference types="vitest/config" />
import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Backend address used by the dev server proxy. Override with NETSCOPE_API_URL.
const apiTarget = process.env.NETSCOPE_API_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  build: {
    // One bundle of about 750 kB (230 kB gzipped): fine on a home network, and the hashed
    // file is cached for a year (decision M4). Split by page if it grows much further.
    chunkSizeWarningLimit: 1000,
  },
  server: {
    proxy: {
      '/api': { target: apiTarget, changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
