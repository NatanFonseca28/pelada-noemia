/** A pelada começou em 2026: não há dados antes. */
export const FIRST_YEAR = 2026

/** Anos para os filtros: do ano atual até 2026, do mais novo para o mais antigo (em 2026: só [2026]; em 2027: [2027, 2026]). */
export function yearOptions(now: number = new Date().getFullYear()): number[] {
  const last = Math.max(now, FIRST_YEAR)
  return Array.from({ length: last - FIRST_YEAR + 1 }, (_, i) => last - i)
}

/** Ano já terminou (somente leitura para o admin; só o superadmin corrige). */
export const isClosedYear = (year: number, now: number = new Date().getFullYear()) => year < now
