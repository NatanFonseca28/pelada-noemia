import type { ReactNode } from 'react'
import { cx } from './cx'

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx('card', className)}>{children}</div>
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h1 className="font-display text-3xl font-bold leading-tight md:text-4xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  )
}
