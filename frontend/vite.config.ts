import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

const target = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: 5173,
    // Em /mnt/* do WSL e em volumes do Docker no Windows o watcher nativo não recebe eventos
    watch: process.env.VITE_USE_POLLING === 'true' ? { usePolling: true, interval: 300 } : undefined,
    proxy: {
      '/api': { target, changeOrigin: true },
      '/ws': { target: target.replace(/^http/, 'ws'), ws: true },
    },
  },
})
