import { createContext, useContext, type ReactNode } from 'react'

export interface ToastOptions {
  message: ReactNode
  tone?: 'default' | 'success' | 'error'
  /** ex.: { label: 'Desfazer', onClick } — fica visível enquanto o toast existir */
  action?: { label: string; onClick: () => void }
  duration?: number
}
export type ShowToast = (message: ReactNode | ToastOptions) => void
export const ToastContext = createContext<ShowToast>(() => {})
export const useToast = () => useContext(ToastContext)

export interface ConfirmOptions {
  title: string
  description?: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
}
export type Confirm = (options: ConfirmOptions) => Promise<boolean>
export const ConfirmContext = createContext<Confirm>(async () => false)
/** Substitui o window.confirm: `if (await confirm({ title: 'Excluir rodada?', danger: true })) …` */
export const useConfirm = () => useContext(ConfirmContext)
