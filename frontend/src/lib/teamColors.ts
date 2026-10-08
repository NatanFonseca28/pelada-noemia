/** Cores dos times. A cor vem da API; esta tabela é o fallback (tema futebol). */
export const TEAM_COLORS: Record<string, string> = {
  Verde: '#1f9d55',
  Azul: '#2f6fdb',
  Vermelho: '#e0443a',
  Amarelo: '#f4c20d',
}

export const TEAM_INK = '#0e1a12'

export function teamColor(name: string, apiColor?: string | null): string {
  return apiColor || TEAM_COLORS[name] || '#5d6b5f'
}

function luminance(hex: string): number {
  const n = parseInt(hex.replace('#', '').slice(0, 6), 16)
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
    const c = v / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

/**
 * Texto sobre a cor do time: sempre a tinta escura #0e1a12 (as 4 cores oficiais passam AA como
 * texto grande, ≥ 3:1). Para cores extras vindas da API que não passam (ex.: Preto, Roxo), usa branco.
 */
export function teamInk(color: string): string {
  return contrast(TEAM_INK, color) >= 3 ? TEAM_INK : '#ffffff'
}

const ABBR: Record<string, string> = {
  Verde: 'VRD',
  Azul: 'AZL',
  Vermelho: 'VRM',
  Amarelo: 'AMA',
  Preto: 'PRT',
  Branco: 'BRC',
  Laranja: 'LRJ',
  Roxo: 'RXO',
}

/** Sigla de 3 letras para tarjas de placar (Verde → VRD, Vermelho → VRM). */
export function teamAbbr(name: string, abbr?: string | null): string {
  if (abbr) return abbr
  if (ABBR[name]) return ABBR[name]
  const clean = name.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toUpperCase().replace(/[^A-Z]/g, '')
  const consonants = clean[0] + clean.slice(1).replace(/[AEIOU]/g, '')
  return (consonants.length >= 3 ? consonants : clean).slice(0, 3)
}

/** Forma do escudo, estável por nome (mesmo time = mesmo escudo em todas as telas). */
export function shieldShape(name: string): 0 | 1 | 2 | 3 {
  let h = 0
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return (h % 4) as 0 | 1 | 2 | 3
}
