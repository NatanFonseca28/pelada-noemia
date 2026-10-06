/** Junta classes condicionais. */
export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ')

/** Traço padrão de todos os ícones lucide. */
export const ICON_STROKE = 1.75
