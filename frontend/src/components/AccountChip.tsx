import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound } from 'lucide-react'
import { useAuth } from '@/auth/AuthProvider'
import { roleLabel } from '@/lib/labels'
import { ICON_STROKE, cx } from './ui'

/**
 * Avatar do usuário logado no rodapé da barra lateral. Sem texto (não cabe ao lado do sino, tema e sair):
 * o nome aparece ao passar o mouse ou focar; ao clicar abre um menu com os dados e o link para Minha conta.
 */
export function AccountChip() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !box.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  if (!user) return null
  const role = user.is_superadmin ? 'Superadmin' : roleLabel[user.role]
  return (
    <div ref={box} className="group relative mr-auto">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label={`${user.name}, ${role}. Abrir menu da conta`}
        className="press grid h-11 w-11 place-items-center rounded-btn hover:bg-soft"
      >
        <span className="grid h-8 w-8 place-items-center rounded-full bg-primary/15 font-display font-bold text-primary-ink" aria-hidden>
          {user.name.charAt(0).toUpperCase()}
        </span>
      </button>

      {/* Dica ao passar o mouse/focar (some quando o menu está aberto) */}
      {!open && (
        <span
          role="tooltip"
          className="pointer-events-none absolute bottom-full left-0 z-toast mb-2 hidden whitespace-nowrap rounded-btn bg-ink px-2.5 py-1.5 text-xs text-bg shadow-card group-focus-within:block group-hover:block"
        >
          <span className="block font-semibold">{user.name}</span>
          <span className="block opacity-80">{role}</span>
        </span>
      )}

      {open && (
        <div role="menu" className="absolute bottom-full left-0 z-toast mb-2 w-60 rounded-card border border-line bg-surface p-3 shadow-card">
          <p className="truncate font-semibold">{user.name}</p>
          <p className="truncate text-sm text-muted">{user.email}</p>
          <p className="mt-1 text-xs font-medium text-accent-ink">{role}</p>
          <Link
            role="menuitem"
            to="/conta"
            onClick={() => setOpen(false)}
            className={cx('press mt-3 flex min-h-[44px] items-center gap-2 rounded-btn px-2 text-sm font-medium hover:bg-soft')}
          >
            <KeyRound size={16} strokeWidth={ICON_STROKE} aria-hidden /> Minha conta
          </Link>
        </div>
      )}
    </div>
  )
}
