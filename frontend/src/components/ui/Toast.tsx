import { isValidElement, useCallback, useState, type ReactNode } from 'react'
import { CheckCircle2, AlertTriangle } from 'lucide-react'
import { ToastContext, type ToastOptions } from '@/contexts/feedback'
import { cx, ICON_STROKE } from './cx'

interface Item extends ToastOptions {
  id: number
}

const isOptions = (v: unknown): v is ToastOptions => typeof v === 'object' && v !== null && !isValidElement(v) && 'message' in v

/** Toasts empilhados acima da barra inferior; anunciados para leitores de tela. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Item[]>([])
  const dismiss = useCallback((id: number) => setItems((list) => list.filter((t) => t.id !== id)), [])
  const show = useCallback(
    (input: ReactNode | ToastOptions) => {
      const opts: ToastOptions = isOptions(input) ? input : { message: input }
      const id = Date.now() + Math.random()
      setItems((list) => [...list.slice(-2), { ...opts, id }])
      window.setTimeout(() => dismiss(id), opts.duration ?? (opts.action ? 6000 : 2600))
    },
    [dismiss],
  )
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-20 z-toast flex flex-col items-center gap-2 px-4 lg:bottom-6">
        {items.map((t) => (
          <div key={t.id} className="anim-toast pointer-events-auto flex min-h-[48px] max-w-md items-center gap-3 rounded-btn bg-board py-2 pl-4 pr-2 text-sm font-medium text-board-ink shadow-card">
            {t.tone === 'success' && <CheckCircle2 size={18} strokeWidth={ICON_STROKE} className="text-primary" aria-hidden />}
            {t.tone === 'error' && <AlertTriangle size={18} strokeWidth={ICON_STROKE} className="text-[#f06aa8]" aria-hidden />}
            <span className={cx('flex-1', !t.action && 'pr-2')}>{t.message}</span>
            {t.action && (
              <button
                onClick={() => {
                  t.action?.onClick()
                  dismiss(t.id)
                }}
                className="press min-h-[40px] rounded-btn px-3 font-display text-base font-bold uppercase tracking-wide text-[#8cc0ff] hover:bg-board-ink/10"
              >
                {t.action.label}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
