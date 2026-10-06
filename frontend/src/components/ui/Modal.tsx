import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { cx, ICON_STROKE } from './cx'

/**
 * Sheet responsivo: bottom sheet no celular (alça + área segura), diálogo centralizado no desktop.
 * Renderizado no <body> via portal; Esc fecha; foco vai para o painel ao abrir e volta ao sair.
 */
export function Modal({ open, onClose, title, children, footer, size = 'md' }: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  size?: 'md' | 'lg'
}) {
  const panel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement | null
    panel.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      previous?.focus?.()
    }
  }, [open, onClose])
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-sheet flex items-end justify-center bg-board/60 md:items-center md:p-4" onClick={onClose}>
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cx(
          'anim-sheet md:anim-modal flex max-h-[92dvh] w-full flex-col rounded-t-[20px] bg-surface shadow-card outline-none md:rounded-card',
          size === 'lg' ? 'md:max-w-2xl' : 'md:max-w-lg',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mx-auto mt-2 h-1.5 w-10 rounded-full bg-line md:hidden" aria-hidden />
        <div className="flex items-center justify-between gap-2 px-5 pb-2 pt-3 md:pt-4">
          <h2 className="font-display text-2xl font-bold leading-tight">{title}</h2>
          <button onClick={onClose} aria-label="Fechar" className="press grid h-11 w-11 shrink-0 place-items-center rounded-btn text-muted hover:bg-soft hover:text-ink">
            <X size={20} strokeWidth={ICON_STROKE} />
          </button>
        </div>
        <div className="overflow-y-auto px-5 pb-5">{children}</div>
        {footer && <div className="pb-safe border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}

/** Alias semântico: mesma peça, nome do brief. */
export const Sheet = Modal
