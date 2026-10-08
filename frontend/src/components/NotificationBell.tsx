import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Bot, KeyRound, MessageCircle, UserPlus } from 'lucide-react'
import { useChatbotReplies } from '@/api/chatbot'
import { useCreateResetLink, usePasswordRequests, usePendingSignups } from '@/api/queries'
import type { PasswordRequest } from '@/api/types'
import { useAuth } from '@/auth/AuthProvider'
import { useToast } from '@/contexts/feedback'
import { since } from '@/lib/charge'
import { formatPhone } from '@/lib/phone'
import { Button, ICON_STROKE, Modal, cx, errorMessage } from './ui'

/** Avisa com um toast quando aparece um item novo (na 1ª carga, só memoriza). */
function useNewItemsToast<T extends { id: number }>(items: T[] | undefined, message: (fresh: T[]) => string) {
  const toast = useToast()
  const known = useRef<Set<number> | null>(null)
  useEffect(() => {
    if (!items) return
    if (known.current) {
      const fresh = items.filter((i) => !known.current?.has(i.id))
      if (fresh.length) toast({ message: message(fresh), tone: 'success' })
    }
    known.current = new Set(items.map((i) => i.id))
  }, [items, toast, message])
}

const signupMessage = (fresh: { name: string }[]) =>
  fresh.length === 1 ? `Novo cadastro: ${fresh[0].name}` : `${fresh.length} novos cadastros aguardando aprovação`
const replyMessage = (fresh: { name: string }[]) =>
  fresh.length === 1 ? `Chatbot: ${fresh[0].name} respondeu a cobrança` : `Chatbot: ${fresh.length} respostas de cobrança`
const resetMessage = (fresh: { name: string }[]) =>
  fresh.length === 1 ? `${fresh[0].name} pediu uma senha nova` : `${fresh.length} pedidos de senha nova`

function ResetRequest({ r }: { r: PasswordRequest }) {
  const create = useCreateResetLink()
  const toast = useToast()
  const { user } = useAuth()

  const send = async () => {
    // abre a aba já no clique (senão o navegador bloqueia) e só depois aponta para o WhatsApp
    const win = r.phone ? window.open('', '_blank') : null
    try {
      const link = await create.mutateAsync(r.id)
      const text =
        `Oi, ${r.name.split(' ')[0]}! Aqui é o ${user?.name.split(' ')[0] ?? 'administrador'}, da pelada de quarta. ` +
        `Para criar sua senha nova, abra este link (vale por 1 hora): ${link.url}`
      if (win && link.phone) {
        win.opener = null
        win.location.href = `https://wa.me/${link.phone.replace(/\D/g, '')}?text=${encodeURIComponent(text)}`
      } else {
        win?.close()
        await navigator.clipboard.writeText(link.url)
        toast({ message: 'Link copiado. Envie para a pessoa (vale por 1 hora).', tone: 'success' })
      }
    } catch (err) {
      win?.close()
      toast({ message: errorMessage(err, 'Não foi possível gerar o link'), tone: 'error' })
    }
  }

  return (
    <li className="flex flex-wrap items-start gap-3 py-3">
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent/15 text-accent-ink" aria-hidden>
        <KeyRound size={17} strokeWidth={ICON_STROKE} />
      </span>
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-medium">{r.name}</p>
        <p className="truncate text-muted">{r.phone ? formatPhone(r.phone) : r.email}</p>
        <p className="text-xs text-muted">
          pediu {since(r.requested_at)}
          {r.link_sent_at && ` · link enviado ${since(r.link_sent_at)}`}
        </p>
      </div>
      <Button size="sm" variant={r.link_sent_at ? 'secondary' : 'primary'} loading={create.isPending} onClick={send}>
        <MessageCircle size={15} strokeWidth={ICON_STROKE} aria-hidden />
        {r.phone ? (r.link_sent_at ? 'Reenviar' : 'Enviar link') : 'Copiar link'}
      </Button>
    </li>
  )
}

/** Sino dos administradores: cadastros novos e pedidos de senha nova (atualiza a cada minuto). */
export function NotificationBell() {
  const { hasRole } = useAuth()
  const admin = hasRole('ADMIN')
  const { data: signups } = usePendingSignups(admin)
  const { data: resets } = usePasswordRequests(admin)
  const { data: botReplies } = useChatbotReplies(admin)
  const [open, setOpen] = useState(false)
  useNewItemsToast(signups, signupMessage)
  useNewItemsToast(resets, resetMessage)
  useNewItemsToast(botReplies, replyMessage)

  if (!admin) return null
  const pending = signups ?? []
  const requests = resets ?? []
  const replies = botReplies ?? []
  const count = pending.length + requests.filter((r) => !r.link_sent_at).length + replies.length
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={count ? `${count} aviso${count > 1 ? 's' : ''} para resolver` : 'Avisos'}
        title="Avisos"
        className="press relative grid h-11 w-11 place-items-center rounded-btn text-muted hover:bg-soft hover:text-ink"
      >
        <Bell size={19} strokeWidth={ICON_STROKE} aria-hidden />
        {count > 0 && (
          <span className="tabular absolute right-1.5 top-1.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-danger px-1 text-[11px] font-bold leading-none text-danger-on">
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title="Avisos">
        {pending.length === 0 && requests.length === 0 && replies.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted">Nada para resolver.</p>
        ) : (
          <div className="space-y-5">
            {replies.length > 0 && (
              <section>
                <h3 className="font-semibold">Respostas do chatbot de cobrança</h3>
                <p className="flex items-center gap-2 py-2 text-sm text-muted">
                  <Bot size={17} strokeWidth={ICON_STROKE} aria-hidden />
                  {replies.length} resposta{replies.length > 1 ? 's' : ''} para conferir (pagamentos, "F" e conversas)
                </p>
                <Link to="/gestao/financeiro" onClick={() => setOpen(false)} className="text-sm font-medium text-primary-ink hover:underline">
                  Abrir no Financeiro
                </Link>
              </section>
            )}
            {requests.length > 0 && (
              <section>
                <h3 className="font-semibold">Pedidos de senha nova</h3>
                <ul className="divide-y divide-line">{requests.map((r) => <ResetRequest key={r.id} r={r} />)}</ul>
              </section>
            )}
            {pending.length > 0 && (
              <section>
                <h3 className="font-semibold">Cadastros novos</h3>
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
                  className={cx('press mt-1 flex min-h-[48px] items-center justify-center rounded-btn bg-primary px-4 font-medium text-primary-on')}
                >
                  Ver e aprovar cadastros
                </Link>
              </section>
            )}
          </div>
        )}
      </Modal>
    </>
  )
}
