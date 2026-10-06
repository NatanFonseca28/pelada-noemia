import type { TokenResponse } from './types'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
    public errors?: { field: string; message: string }[],
  ) {
    super(message)
  }
}

let accessToken: string | null = null
let onSessionLost: (() => void) | null = null
let refreshing: Promise<TokenResponse | null> | null = null

export const tokenStore = {
  get: () => accessToken,
  set: (t: string | null) => {
    accessToken = t
  },
  onSessionLost: (cb: () => void) => {
    onSessionLost = cb
  },
}

/** Tenta renovar o access token usando o cookie httpOnly de refresh (single-flight). */
export function refreshSession(): Promise<TokenResponse | null> {
  refreshing ??= fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })
    .then(async (r) => {
      if (!r.ok) return null
      const data = (await r.json()) as TokenResponse
      accessToken = data.access_token
      return data
    })
    .catch(() => null)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

async function parseError(r: Response): Promise<ApiError> {
  let body: { detail?: unknown; code?: string; errors?: { field: string; message: string }[] } = {}
  try {
    body = await r.json()
  } catch {
    /* corpo vazio */
  }
  const message = typeof body.detail === 'string' ? body.detail : `Erro ${r.status}`
  return new ApiError(r.status, message, body.code, body.errors)
}

export async function api<T = unknown>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)

  const r = await fetch(`/api${path}`, { ...init, headers, credentials: 'include' })

  if (r.status === 401 && retry && !path.startsWith('/auth/')) {
    const refreshed = await refreshSession()
    if (refreshed) return api<T>(path, init, false)
    accessToken = null
    onSessionLost?.()
  }
  if (!r.ok) throw await parseError(r)
  if (r.status === 204) return undefined as T
  return (await r.json()) as T
}

export const json = (body: unknown) => JSON.stringify(body)

/** Baixa um arquivo autenticado (ex.: exportação .xlsx) e dispara o download no navegador. */
export async function downloadFile(path: string, fallbackName: string, retry = true): Promise<void> {
  const headers = new Headers()
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  const r = await fetch(`/api${path}`, { headers, credentials: 'include' })
  if (r.status === 401 && retry && (await refreshSession())) return downloadFile(path, fallbackName, false)
  if (!r.ok) throw await parseError(r)
  const name = /filename="([^"]+)"/.exec(r.headers.get('Content-Disposition') ?? '')?.[1] ?? fallbackName
  const url = URL.createObjectURL(await r.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
