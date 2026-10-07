import * as Sentry from '@sentry/react'

/** Sentry no navegador: só liga com VITE_SENTRY_DSN no build; nunca envia dados pessoais nem o conteúdo das telas. */
export function initMonitoring() {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined
  if (!dsn) return
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0,
    integrations: [],
    beforeSend(event) {
      delete event.user
      if (event.request) {
        delete event.request.cookies
        delete event.request.headers
        // tira o token de redefinição de senha e outros parâmetros da URL
        if (event.request.url) event.request.url = event.request.url.split('?')[0]
        delete event.request.query_string
      }
      return event
    },
    beforeBreadcrumb(crumb) {
      // sem textos digitados nem cliques com conteúdo; só navegação e requisições (sem query)
      if (crumb.category === 'ui.input' || crumb.category === 'ui.click') return null
      if (crumb.data?.url) crumb.data.url = String(crumb.data.url).split('?')[0]
      return crumb
    },
  })
}

export const ErrorBoundary = Sentry.ErrorBoundary
