import { useCallback, useRef, useState, type ReactNode } from 'react'
import { ConfirmContext, type ConfirmOptions } from '@/contexts/feedback'
import { Button } from './Button'
import { Modal } from './Modal'

/** Provider do `useConfirm` — diálogo de confirmação no lugar do window.confirm. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [opts, setOpts] = useState<ConfirmOptions | null>(null)
  const resolver = useRef<(v: boolean) => void>()
  const confirm = useCallback((o: ConfirmOptions) => {
    setOpts(o)
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve
    })
  }, [])
  const close = (value: boolean) => {
    resolver.current?.(value)
    setOpts(null)
  }
  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Modal
        open={!!opts}
        onClose={() => close(false)}
        title={opts?.title ?? ''}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => close(false)}>{opts?.cancelLabel ?? 'Cancelar'}</Button>
            <Button variant={opts?.danger ? 'danger' : 'primary'} onClick={() => close(true)}>{opts?.confirmLabel ?? 'Confirmar'}</Button>
          </div>
        }
      >
        {opts?.description && <div className="text-sm text-muted">{opts.description}</div>}
      </Modal>
    </ConfirmContext.Provider>
  )
}
