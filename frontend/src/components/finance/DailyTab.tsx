import { useState } from 'react'
import { ChevronLeft, ChevronRight, MessageCircle } from 'lucide-react'
import { useChargeMessage, useDailyOverview, usePayDaily } from '@/api/finance'
import { useAuth } from '@/auth/AuthProvider'
import { Alert, Badge, Card, EmptyState, ICON_STROKE, IconButton, Spinner, cx } from '@/components/ui'
import { whatsappChargeLink } from '@/lib/charge'
import { formatDate, money, monthLong } from '@/lib/labels'
import { formatPhone } from '@/lib/phone'

const shift = (month: string, delta: number) => {
  const d = new Date(`${month}-01T12:00:00`)
  d.setMonth(d.getMonth() + delta)
  return d.toISOString().slice(0, 7)
}

/** Diaristas: pagam a diária ANTES do jogo, por rodada (mensalistas ficam na grade mensal). */
export function DailyTab({ dailyFee, onEditFee }: { dailyFee?: string | null; onEditFee?: () => void }) {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7))
  const { data, isLoading, error } = useDailyOverview(month)
  const pay = usePayDaily()
  const pix = useChargeMessage().data?.pix_key
  const { user } = useAuth()
  const gestor = (user?.name ?? '').split(' ')[0]

  const message = (name: string, date: string, amount: string) =>
    `Oi ${name.split(' ')[0]}, tudo bem? A diária da pelada de ${formatDate(date)} é ${money(amount)}, paga antes do jogo.` +
    `${pix ? ` Pix: ${pix}.` : ''} Qualquer coisa me chama. ${gestor}`.trimEnd()

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <IconButton label="Mês anterior" onClick={() => setMonth(shift(month, -1))}><ChevronLeft size={18} strokeWidth={ICON_STROKE} aria-hidden /></IconButton>
          <span className="w-40 text-center font-display font-semibold capitalize">{monthLong(`${month}-01`)}</span>
          <IconButton label="Próximo mês" onClick={() => setMonth(shift(month, 1))}><ChevronRight size={18} strokeWidth={ICON_STROKE} aria-hidden /></IconButton>
        </div>
        {data && (
          <div className="flex flex-wrap gap-2 text-sm">
            <Badge>Previsto {money(data.expected)}</Badge>
            <Badge color="green">Recebido {money(data.received)}</Badge>
            <Badge color={Number(data.pending) > 0 ? 'red' : 'gray'}>Pendente {money(data.pending)}</Badge>
          </div>
        )}
      </div>
      {dailyFee != null && (
        <p className="mb-2 text-sm">
          Diária atual: <strong>{money(dailyFee)}</strong>
          {onEditFee && (
            <> · <button type="button" onClick={onEditFee} className="font-medium text-primary-ink underline">alterar</button></>
          )}
        </p>
      )}
      <p className="mb-3 text-xs text-muted">
        Só diarista que joga na linha paga. Quem avisou que vai só agarrar não paga. As diárias pagas entram no caixa automaticamente.
      </p>
      {pay.error && <div className="mb-3"><Alert>Não foi possível atualizar o pagamento.</Alert></div>}
      {isLoading ? (
        <Spinner />
      ) : error || !data ? (
        <Alert>Erro ao carregar as diárias.</Alert>
      ) : data.rounds.length === 0 ? (
        <EmptyState>Nenhum diarista confirmado em rodadas deste mês.</EmptyState>
      ) : (
        <div className="space-y-4">
          {data.rounds.map((r) => (
            <Card key={r.round_id} className="p-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold capitalize">{formatDate(r.date)}</h3>
                <span className="text-sm text-muted">{money(r.received)} de {money(r.expected)}</span>
              </div>
              {r.items.length === 0 ? (
                <p className="text-sm text-muted">Nenhuma diária a receber nesta rodada.</p>
              ) : (
                <ul className="divide-y divide-line">
                  {r.items.map((i) => (
                    <li key={i.player_id} className="flex flex-wrap items-center gap-2 py-2">
                      <span className="min-w-0 flex-1 truncate font-medium">{i.name}</span>
                      <span className="tabular text-sm">{money(i.amount)}</span>
                      {!i.paid && i.phone && i.whatsapp_opt_in && (
                        <a
                          href={whatsappChargeLink(i.phone, message(i.name, r.date, i.amount))}
                          target="_blank"
                          rel="noopener noreferrer"
                          title={`Cobrar ${formatPhone(i.phone)}`}
                          className="press inline-flex min-h-[36px] items-center gap-1 rounded-btn border border-line px-2 text-xs font-medium hover:bg-soft"
                        >
                          <MessageCircle size={14} strokeWidth={ICON_STROKE} aria-hidden /> Cobrar
                        </a>
                      )}
                      <button
                        type="button"
                        disabled={pay.isPending}
                        aria-pressed={i.paid}
                        onClick={() => pay.mutate({ roundId: r.round_id, playerId: i.player_id, paid: !i.paid })}
                        className={cx('min-h-[36px] rounded-btn border px-3 text-xs font-medium disabled:opacity-60', i.paid ? 'border-primary bg-primary/10 text-primary-ink' : 'border-danger/40 text-danger-ink')}
                      >
                        {i.paid ? 'Pago' : 'Pendente'}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
              {r.free_goalkeepers.length > 0 && (
                <p className="mt-2 text-xs text-muted">Só agarram (não pagam): {r.free_goalkeepers.join(', ')}</p>
              )}
            </Card>
          ))}
        </div>
      )}
    </>
  )
}
