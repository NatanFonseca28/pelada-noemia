import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { fileURLToPath, URL } from 'node:url'

const target = process.env.API_PROXY_TARGET ?? 'http://localhost:8000'

export default defineConfig({
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
  plugins: [
    react(),
    // App shell offline: o app abre sem internet (os dados ficam no cache do React Query, ver lib/offline/persist.ts).
    // O service worker NÃO guarda /api: dados e fila de ações são responsabilidade do app.
    VitePWA({
      registerType: 'autoUpdate',
      manifest: false, // usa public/site.webmanifest
      injectRegister: false, // registro em src/lib/offline/register.ts (só em produção)
      workbox: {
        globPatterns: ['**/*.{js,css,html,woff2,png,webp,ico,svg,webmanifest}'],
        globIgnores: ['**/Emblema*', '**/favicon_io.zip'],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api/, /^\/ws/],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        runtimeCaching: [
          // escudos e fotos (públicos): aparecem offline depois de vistos uma vez
          { urlPattern: /\/api\/media\//, handler: 'StaleWhileRevalidate', options: { cacheName: 'pelada-media', expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 } } },
        ],
      },
    }),
  ],
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
