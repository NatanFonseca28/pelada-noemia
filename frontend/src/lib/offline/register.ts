/**
 * Modo offline: registra o service worker (app shell) e pede armazenamento durável.
 * Só em produção: em dev o service worker atrapalharia o hot reload.
 */
export function registerOffline() {
  if (!import.meta.env.PROD || !('serviceWorker' in navigator)) return
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => undefined)
  })
  // evita que o navegador limpe a fila e o cache do app quando faltar espaço
  void navigator.storage?.persist?.().catch(() => undefined)
}
