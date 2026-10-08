import { useMemo, useState } from 'react'
import { Bot, Check, MessageCircle, SkipForward } from 'lucide-react'
import { useChatbotCharge, useChatbotStatus } from '@/api/chatbot'
import { ApiError } from '@/api/client'
import { useChargeMessage, useRegisterCharge, useToCharge } from '@/api/finance'
import { useToast } from '@/contexts/feedback'
import { errorMessage } from '@/lib/errors'
import type { Delinquent } from '@/api/types'
import { useAuth } from '@/auth/AuthProvider'
import { Badge, Button, ErrorState, ICON_STROKE, Modal, PlayerName, Skeleton, cx } from '@/components/ui'
import { chargeValues, chargedRecently, renderChargeMessage, since, whatsappChargeLink, type ChargeContext } from '@/lib/charge'
import { money, monthAbbr } from '@/lib/labels'
import { formatPhone } from '@/lib/phone'

const dueLabel = (months: string[]) => months.map((m) => monthAbbr[Number(m.slice(5, 7)) - 1]).join(' e ')

/** Botão que abre o WhatsApp DO APARELHO de quem clicou (a mensagem sai do número dele) e registra a cobrança. */
function ChargeLink({ d, text, onOpened, children, className }: {
  d: Delinquent
  text: string
  onOpened: () => void
  children: React.ReactNode
  className?: string
}) {
  if (!d.phone) return null
  return (
    <a href={whatsappChargeLink(d.phone, text)} target="_blank" rel="noopener noreferrer" onClick={onOpened} className={className}>
      {children}
    </a>
  )
}

type Scope = 'todos' | 'dois' | 'um'

/** "2 meses" (inadimplente) ou "1 mês" em aberto. */
function OwedChip({ d }: { d: Delinquent }) {
  return d.delinquent ? (
    <span className="rounded-full bg-danger/15 px-1.5 py-0.5 text-[11px] font-semibold text-danger-ink">2 meses</span>
  ) : (
    <span className="rounded-full bg-soft px-1.5 py-0.5 text-[11px] font-semibold text-ink">1 mês</span>
  )
}

function ChargedInfo({ d }: { d: Delinquent }) {
  if (!d.last_charged_at) return null
  return (
    <span className={cx('flex items-center gap-1 text-xs', chargedRecently(d.last_charged_at) ? 'text-primary-ink' : 'text-muted')}>
      <Check size={12} strokeWidth={2.5} aria-hidden />
      Cobrado{d.last_charged_by ? ` por ${d.last_charged_by}` : ''} {since(d.last_charged_at)}
    </span>
  )
}

/** "Cobrar todos": uma conversa por vez (o navegador bloqueia abrir várias abas de uma vez). */
function ChargeAll({ list, ctx, template, onClose }: { list: Delinquent[]; ctx: ChargeContext; template: string; onClose: () => void }) {
  const [includeRecent, setIncludeRecent] = useState(false)
  const queue = useMemo(
    () => list.filter((d) => d.phone && (includeRecent || !chargedRecently(d.last_charged_at))),
    [list, includeRecent],
  )
  const [index, setIndex] = useState(0)
  const [opened, setOpened] = useState(0)
  const register = useRegisterCharge()
  const current = queue[index]
  const done = index >= queue.length

  const text = current ? renderChargeMessage(template, chargeValues(current, ctx)) : ''
  const skipped = list.length - list.filter((d) => d.phone).length

  return (
    <Modal open onClose={onClose} title="Cobrar todos" footer={<div className="flex justify-end"><Button variant="secondary" onClick={onClose}>{done ? 'Fechar' : 'Encerrar'}</Button></div>}>
      {index === 0 && opened === 0 && (
        <label className="mb-3 flex min-h-[44px] items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-primary" checked={includeRecent} onChange={(e) => setIncludeRecent(e.target.checked)} />
          Incluir quem já foi cobrado nos últimos 3 dias
        </label>
      )}
      {done ? (
        <div className="py-6 text-center">
          <p className="font-display text-2xl font-bold">{opened ? `${opened} cobrança${opened > 1 ? 's' : ''} aberta${opened > 1 ? 's' : ''}` : 'Ninguém para cobrar agora'}</p>
          {skipped > 0 && <p className="mt-1 text-sm text-muted">{skipped} sem WhatsApp no cadastro</p>}
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted">
            {index + 1} de {queue.length}
          </p>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <PlayerName id={current.player_id} name={current.name} className="font-display text-2xl font-bold" />
            <p className="tabular font-semibold">{money(current.amount_due)}</p>
          </div>
          <ChargedInfo d={current} />
          <p className="whitespace-pre-wrap rounded-btn bg-soft p-3 text-sm">{text}</p>
          <div className="flex flex-wrap gap-2">
            <ChargeLink
              d={current}
              text={text}
              onOpened={() => {
                register.mutate(current.player_id)
                setOpened((n) => n + 1)
                setIndex((i) => i + 1)
              }}
              className="press inline-flex min-h-[48px] flex-1 items-center justify-center gap-2 rounded-btn bg-primary px-4 font-medium text-primary-on"
            >
              <MessageCircle size={18} strokeWidth={ICON_STROKE} aria-hidden /> Abrir WhatsApp de {current.name}
            </ChargeLink>
            <Button variant="secondary" size="lg" onClick={() => setIndex((i) => i + 1)}>
              <SkipForward size={16} strokeWidth={ICON_STROKE} aria-hidden /> Pular
            </Button>
          </div>
          <p className="text-xs text-muted">Envie a mensagem no WhatsApp e volte para esta tela para o próximo.</p>
        </div>
      )}
    </Modal>
  )
}

export function ChargePanel({ count, monthlyFee }: { count: number; monthlyFee: string }) {
  const [open, setOpen] = useState(false)
  const [all, setAll] = useState(false)
  const [scope, setScope] = useState<Scope>('todos')
  const { data: everyone, isLoading, error, refetch } = useToCharge(open && count > 0)
  const data = everyone?.filter((d) => scope === 'todos' || (scope === 'dois' ? d.delinquent : !d.delinquent))
  const twoCount = everyone?.filter((d) => d.delinquent).length ?? 0
  const scopes: { id: Scope; label: string }[] = [
    { id: 'todos', label: `Todos (${everyone?.length ?? 0})` },
    { id: 'dois', label: `Devem 2 meses (${twoCount})` },
    { id: 'um', label: `Devem 1 mês (${(everyone?.length ?? 0) - twoCount})` },
  ]
  const { data: msg } = useChargeMessage()
  const { user } = useAuth()
  const register = useRegisterCharge()
  const { data: botStatus } = useChatbotStatus(open && count > 0)
  const botCharge = useChatbotCharge()
  const toast = useToast()
  if (count === 0) return null
  // chatbot ligado e conectado: as cobranças saem pelo WhatsApp do dono do número, com fila e respostas automáticas
  const bot = !!botStatus?.enabled && botStatus.state === 'open'
  const botReady = data?.filter((d) => d.phone && d.whatsapp_opt_in).length ?? 0

  const chargeAllByBot = () => {
    const minutes = Math.max(1, Math.round((botReady * 45) / 60))
    if (!confirm(`Cobrar ${botReady} pelo chatbot? As mensagens saem uma a uma, com intervalo (cerca de ${minutes} min).`)) return
    botCharge.mutate({}, {
      onSuccess: (r) => toast({
        message: `${r.queued.length} cobrança(s) na fila${r.skipped.length ? `; ${r.skipped.length} pulada(s): ${r.skipped.map((s) => `${s.name} (${s.reason})`).join(', ')}` : ''}`,
        tone: 'success',
      }),
      onError: (err) => toast({ message: errorMessage(err, 'Não foi possível cobrar'), tone: 'error' }),
    })
  }
  const chargeOneByBot = (d: Delinquent, force = false) =>
    botCharge.mutate({ playerId: d.player_id, force }, {
      onSuccess: () => toast({ message: `Cobrança de ${d.name} na fila do chatbot`, tone: 'success' }),
      onError: (err) => {
        if (err instanceof ApiError && err.status === 409 && !force) {
          if (confirm(`${err.message} Cobrar mesmo assim?`)) chargeOneByBot(d, true)
        } else toast({ message: errorMessage(err, 'Não foi possível cobrar'), tone: 'error' })
      },
    })

  const ctx: ChargeContext = { pixKey: msg?.pix_key ?? null, monthlyFee, gestor: user?.name.split(' ')[0] ?? '' }
  const template = msg?.message ?? ''
  const withPhone = data?.filter((d) => d.phone).length ?? 0

  return (
    <details className="card mb-3" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="press flex min-h-[48px] cursor-pointer list-none items-center gap-2 px-4 font-medium">
        <MessageCircle size={18} strokeWidth={ICON_STROKE} className="text-danger-ink" aria-hidden />
        Para cobrar ({count})
      </summary>
      <div className="border-t border-line p-2">
        {isLoading || !msg ? (
          <Skeleton className="my-3 h-24 w-full" />
        ) : error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 px-2 py-1">
              <div className="flex flex-wrap gap-1.5" role="group" aria-label="Quem cobrar">
                {scopes.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    aria-pressed={scope === s.id}
                    onClick={() => setScope(s.id)}
                    className={cx('press min-h-[36px] rounded-full border px-3 text-sm', scope === s.id ? 'border-primary bg-primary/10 font-medium text-primary-ink' : 'border-line text-muted hover:bg-soft')}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
              {bot ? (
                <Button size="sm" onClick={chargeAllByBot} disabled={!botReady} loading={botCharge.isPending}>
                  <Bot size={16} strokeWidth={ICON_STROKE} aria-hidden /> Cobrar todos pelo chatbot ({botReady})
                </Button>
              ) : (
                <Button size="sm" onClick={() => setAll(true)} disabled={!withPhone}>
                  <MessageCircle size={16} strokeWidth={ICON_STROKE} aria-hidden /> Cobrar todos ({withPhone})
                </Button>
              )}
            </div>
            {bot ? (
              <p className="px-2 pb-1 text-xs text-muted">
                O chatbot envia do WhatsApp de {botStatus?.owner_name?.split(' ')[0] ?? 'gestor'}, uma mensagem por vez, e cuida das respostas.
                {(botStatus?.pending ?? 0) > 0 && <strong className="ml-1 text-ink">{botStatus?.pending} mensagem(ns) na fila…</strong>}
              </p>
            ) : (
              <p className="px-2 pb-1 text-xs text-muted">
                A mensagem sai do WhatsApp deste aparelho, com a sua assinatura.
                {botStatus?.enabled && <span className="ml-1 text-danger-ink">O chatbot está ligado, mas o WhatsApp dele está desconectado.</span>}
              </p>
            )}
            <ul>
              {data?.map((d) => {
                const text = renderChargeMessage(template, chargeValues(d, ctx))
                return (
                  <li key={d.player_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line px-2 py-2 text-sm first:border-0">
                    <div className="min-w-0 flex-1">
                      <PlayerName id={d.player_id} name={d.name} className="font-medium" />
                      <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
                        <OwedChip d={d} />
                        <span>{dueLabel(d.months_due)}</span>
                        <span className="tabular font-semibold text-ink">{money(d.amount_due)}</span>
                        {d.phone ? <span className="tabular">{formatPhone(d.phone)}</span> : <Badge color="yellow">sem WhatsApp</Badge>}
                        {d.phone && !d.whatsapp_opt_in && <Badge color="yellow">sem consentimento</Badge>}
                      </p>
                      <ChargedInfo d={d} />
                    </div>
                    {bot && d.phone && d.whatsapp_opt_in && (
                      <Button size="sm" onClick={() => chargeOneByBot(d)} loading={botCharge.isPending}>
                        <Bot size={16} strokeWidth={ICON_STROKE} aria-hidden /> Cobrar
                      </Button>
                    )}
                    <ChargeLink
                      d={d}
                      text={text}
                      onOpened={() => register.mutate(d.player_id)}
                      className="press inline-flex min-h-[44px] items-center gap-1.5 rounded-btn border border-primary/40 px-3 font-medium text-primary-ink hover:bg-primary/10"
                    >
                      <MessageCircle size={16} strokeWidth={ICON_STROKE} aria-hidden /> {bot ? 'Meu WhatsApp' : 'Cobrar'}
                    </ChargeLink>
                  </li>
                )
              })}
            </ul>
          </>
        )}
      </div>
      {all && data && <ChargeAll list={data} ctx={ctx} template={template} onClose={() => setAll(false)} />}
    </details>
  )
}
