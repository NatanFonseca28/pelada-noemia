import { shieldShape, teamColor, teamInk } from '@/lib/teamColors'

// 4 formas geométricas simples (viewBox 40×44): escudo clássico, círculo, hexágono, losango
const SHAPES = [
  'M20 2 L37 8 V22 C37 32 29.5 39 20 42 C10.5 39 3 32 3 22 V8 Z',
  'M20 3 A19 19 0 1 1 19.99 3 Z',
  'M20 2 L37 12 V32 L20 42 L3 32 V12 Z',
  'M20 2 L38 22 L20 42 L2 22 Z',
]

/** Escudo gerado do time: forma estável pelo nome + inicial. Nunca usa marcas reais. */
export function TeamShield({ name, color, size = 32, title }: { name: string; color?: string | null; size?: number; title?: string }) {
  const fill = teamColor(name, color)
  const ink = teamInk(fill)
  const shape = SHAPES[shieldShape(name)]
  return (
    <svg width={size} height={size * 1.1} viewBox="0 0 40 44" role="img" aria-label={title ?? `Escudo do time ${name}`} className="shrink-0">
      <path d={shape} fill={fill} stroke="rgb(0 0 0 / 0.25)" strokeWidth="1.5" />
      <path d={shape} fill="none" stroke="rgb(255 255 255 / 0.35)" strokeWidth="1" transform="translate(20 22) scale(0.82) translate(-20 -22)" />
      <text x="20" y="23" textAnchor="middle" dominantBaseline="central" fill={ink} fontFamily="Barlow Condensed, Inter, sans-serif" fontWeight={800} fontSize="20">
        {name.charAt(0).toUpperCase()}
      </text>
    </svg>
  )
}
