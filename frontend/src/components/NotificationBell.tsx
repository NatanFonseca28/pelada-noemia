import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, UserPlus } from 'lucide-react'
import { usePendingSignups } from '@/api/queries'
import { useAuth } from '@/auth/AuthProvider'
import { useToast } from '@/contexts/feedback'
import { formatPhone } from '@/lib/phone'
import { ICON_STROKE, Modal, cx } from './ui'
import { since } from '@/lib/charge'

/** Sino dos administradores: cadastros novos aguardando aprovação (atualiza a cada minuto). */
export function NotificationBell() {
  const { hasRole } = useAuth()
  const admin = hasRole('ADMIN')
  const { data } = usePendingSignups(admin)
  const [open, setOpen] = useState(false)
  const toast = useToast()
  const known = useRef<Set<number> | null>(null)
  const pending = data ?? []

  // Cadastro novo enquanto o app está aberto: avisa com um toast (na 1ª carga, só memoriza)
  useEffect(() => {
    if (!data) return
    const ids = new Set(data.map((u) => u.id))
    if (known.current) {
      const fresh = data.filter((u) => !known.current?.has(u.id))
      if (fresh.length === 1) toast({ message: `Novo cadastro: ${fresh[0].name}`, tone: 'success' })
      else if (fresh.length > 1) toast({ message: `${fresh.length} novos cadastros aguardando aprovação`, tone: 'success' })
    }
    known.current = ids
  }, [data, toast])

  if (!admin) return null
  const count = pending.length
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={count ? `${count} cadastro${count > 1 ? 's' : ''} aguardando aprovação` : 'Notificações'}
        title="Cadastros novos"
        className="press relative grid h-11 w-11 place-items-center rounded-btn text-muted hover:bg-soft hover:text-ink"
      >
        <Bell size={19} strokeWidth={ICON_STROKE} aria-hidden />
        {count > 0 && (
          <span className="tabular absolute right-1.5 top-1.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-danger px-1 text-[11px] font-bold leading-none text-danger-on">
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title="Cadastros novos">
        {count === 0 ? (
          <p className="py-6 text-center text-sm text-muted">Nenhum cadastro aguardando aprovação.</p>
        ) : (
          <>
            <ul className="divide-y divide-line">
              {pending.map((u) => (
                <li key={u.id} className="flex items-start gap-3 py-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent/15 text-accent-ink" aria-hidden>
                    <UserPlus size={17} strokeWidth={ICON_STROKE} />
                  </span>
                  <div className="min-w-0 flex-1 text-sm">
                    <p className="font-medium">{u.name}</p>
                    <p className="truncate text-muted">{u.email}</p>
                    {u.phone && <p className="tabular text-muted">{formatPhone(u.phone)}</p>}
                  </div>
                  <span className="shrink-0 text-xs text-muted">{since(u.created_at)}</span>
                </li>
              ))}
            </ul>
            <Link
              to="/gestao/usuarios?aba=pendentes"
              onClick={() => setOpen(false)}
              className={cx('press mt-3 flex min-h-[48px] items-center justify-center rounded-btn bg-primary px-4 font-medium text-primary-on')}
            >
              Ver e aprovar
            </Link>
          </>
        )}
      </Modal>
    </>
  )
}
