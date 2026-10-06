import { cx } from './cx'

export function Avatar({ name, url, size = 40, className }: { name: string; url?: string | null; size?: number; className?: string }) {
  const initials = name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
  return url ? (
    <img src={url} alt={name} width={size} height={size} loading="lazy" decoding="async" className={cx('shrink-0 rounded-full object-cover', className)} style={{ width: size, height: size }} />
  ) : (
    <span
      className={cx('grid shrink-0 place-items-center rounded-full bg-primary/15 font-display font-bold text-primary-ink', className)}
      style={{ width: size, height: size, fontSize: size * 0.42 }}
      aria-hidden
    >
      {initials}
    </span>
  )
}
