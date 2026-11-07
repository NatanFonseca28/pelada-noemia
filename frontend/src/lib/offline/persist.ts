/**
 * Cache dos dados da pelada no IndexedDB, para o app abrir e funcionar sem internet depois de recarregar.
 * Só entram dados de jogo (campeonato, partidas, súmula, rodadas). Nada de financeiro, usuários ou telefones.
 */
import { del, get, set } from 'idb-keyval'
import type { Query } from '@tanstack/react-query'
import type { PersistedClient, Persister } from '@tanstack/react-query-persist-client'

const KEY = 'pelada-query-cache'

/** Raízes de chave de consulta que podem ser guardadas no celular. */
const ALLOWED = new Set(['tournament', 'sheet', 'rounds', 'formats'])

export const shouldPersist = (query: Query) =>
  query.state.status === 'success' && typeof query.queryKey[0] === 'string' && ALLOWED.has(query.queryKey[0])

export const persister: Persister = {
  persistClient: (client: PersistedClient) => set(KEY, client),
  restoreClient: () => get<PersistedClient>(KEY),
  removeClient: () => del(KEY),
}

/** Dados guardados por até 7 dias. */
export const MAX_AGE = 1000 * 60 * 60 * 24 * 7

/** Versão do formato: mude para descartar caches antigos depois de uma alteração incompatível. */
export const BUSTER = 'v1'
