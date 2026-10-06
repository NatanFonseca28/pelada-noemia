import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cx } from './cx'
import { Spinner } from './Feedback'

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost' | 'accent'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'xl'

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-primary-on disabled:bg-primary/50',
  accent: 'bg-accent text-accent-on disabled:bg-accent/50',
  secondary: 'border border-line bg-surface text-ink hover:bg-soft',
  danger: 'bg-danger text-danger-on disabled:bg-danger/50',
  ghost: 'text-muted hover:bg-soft hover:text-ink',
}

const sizes: Record<ButtonSize, string> = {
  sm: 'min-h-[44px] min-w-[44px] px-2.5 text-xs',
  md: 'min-h-[44px] px-4 text-sm',
  lg: 'min-h-[48px] px-5 text-base',
  // mesa da partida: alvo grande, uso com uma mão
  xl: 'min-h-[56px] px-6 font-display text-xl font-bold tracking-wide',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant; size?: ButtonSize; loading?: boolean }) {
  return (
    <button
      className={cx('press inline-flex items-center justify-center gap-2 rounded-btn font-medium disabled:cursor-not-allowed', sizes[size], variants[variant], className)}
      disabled={loading || props.disabled}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <Spinner small />}
      {children}
    </button>
  )
}

/** Botão só com ícone: exige rótulo acessível. */
export function IconButton({ label, children, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return (
    <button
      aria-label={label}
      title={label}
      className={cx('press grid h-11 w-11 place-items-center rounded-btn text-muted hover:bg-soft hover:text-ink', className)}
      {...props}
    >
      {children}
    </button>
  )
}
