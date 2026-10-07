import type { PlayerType } from '@/api/types'
import { cx } from './cx'

/** `type`: contorno do tipo de jogador (contínuo azul = mensalista, tracejado laranja = diarista). */
export function Avatar({ name, url, size = 40, className, type }: { name: string; url?: string | null; size?: number; className?: string; type?: PlayerType | null }) {
  const ring = type === 'MENSALISTA' ? 'outline outline-2 outline-offset-1 outline-mensalista' : type === 'DIARISTA' ? 'outline-dashed outline-2 outline-offset-1 outline-diarista' : ''
  const initials = name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
  return url ? (
    <img src={url} alt={name} width={size} height={size} loading="lazy" decoding="async" className={cx('shrink-0 rounded-full object-cover', ring, className)} style={{ width: size, height: size }} />
  ) : (
    <span
      className={cx('grid shrink-0 place-items-center rounded-full bg-primary/15 font-display font-bold text-primary-ink', ring, className)}
      style={{ width: size, height: size, fontSize: size * 0.42 }}
      aria-hidden
    >
      {initials}
    </span>
  )
}
