import { useState } from 'react'
import { Bot, Check, FileText, MessageCircle, X } from 'lucide-react'
import { useChatbotReplies, useResolveReply, type ChargeReply } from '@/api/chatbot'
import { Badge, Button, ICON_STROKE, Modal, PlayerName } from '@/components/ui'
import { useToast } from '@/contexts/feedback'
import { since } from '@/lib/charge'
import { errorMessage } from '@/lib/errors'
import { money, monthAbbr } from '@/lib/labels'

const monthsLabel = (months: string[]) => months.map((m) => monthAbbr[Number(m.slice(5, 7)) - 1]).join(' e ')

const KIND: Record<ChargeReply['kind'], { title: string; approve: string; color: 'green' | 'yellow' | 'blue' }> = {
  PAGO: { title: 'Diz que pagou', approve: 'Confirmar pagamento', color: 'green' },
  FORA: { title: 'Não vai jogar', approve: 'Aprovar "F"', color: 'yellow' },
  FALAR: { title: 'Quer falar com você', approve: 'Resolvido', color: 'blue' },
}

/** Respostas do chatbot que precisam do admin: conferir comprovante, aprovar "F", conversar. */
export function ChatbotReplies() {
  const { data } = useChatbotReplies()
  const resolve = useResolveReply()
  const toast = useToast()
  const [proof, setProof] = useState<ChargeReply | null>(null)
  if (!data?.length) return null

  const act = (r: ChargeReply, approve: boolean) =>
    resolve.mutate({ id: r.id, approve }, {
      onSuccess: () => toast({
        message: approve ? (r.kind === 'PAGO' ? `Pagamento de ${r.name} confirmado` : r.kind === 'FORA' ? `${r.name} fora em ${monthsLabel(r.months)}` : 'Resolvido') : 'Pedido recusado',
        tone: 'success',
      }),
      onError: (err) => toast({ message: errorMessage(err, 'Não foi possível salvar'), tone: 'error' }),
    })

  return (
    <section className="card mb-3 border-l-4 border-l-accent p-3" aria-labelledby="respostas-chatbot">
      <h2 id="respostas-chatbot" className="mb-2 flex items-center gap-2 font-medium">
        <Bot size={18} strokeWidth={ICON_STROKE} aria-hidden /> Respostas do chatbot ({data.length})
      </h2>
      <ul className="divide-y divide-line">
        {data.map((r) => {
          const k = KIND[r.kind]
          return (
            <li key={r.id} className="flex flex-wrap items-center gap-x-3 gap-y-2 py-2 text-sm">
              {r.media_url ? (
                <button type="button" onClick={() => setProof(r)} className="h-12 w-12 shrink-0 overflow-hidden rounded-btn border border-line" aria-label={`Ver comprovante de ${r.name}`}>
                  <img src={r.media_url} alt="" className="h-full w-full object-cover" />
                </button>
              ) : r.has_document ? (
                <span className="grid h-12 w-12 shrink-0 place-items-center rounded-btn border border-line text-muted" title="Mandou PDF: confira no WhatsApp">
                  <FileText size={20} strokeWidth={ICON_STROKE} aria-hidden />
                </span>
              ) : null}
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2">
                  <PlayerName id={r.player_id} name={r.name} className="font-medium" />
                  <Badge color={k.color}>{k.title}</Badge>
                  <span className="text-xs text-muted">{since(r.created_at)}</span>
                </p>
                <p className="text-xs text-muted">
                  {r.kind === 'PAGO' && <>{monthsLabel(r.months)} · <span className="tabular font-semibold text-ink">{money(r.amount)}</span>{!r.media_url && !r.has_document && ' · sem comprovante ainda'}</>}
                  {r.kind === 'FORA' && <>Fica fora em {monthsLabel(r.months)}</>}
                  {r.note && <span className="block italic">“{r.note}”</span>}
                </p>
              </div>
              <div className="flex gap-2">
                {r.kind === 'FALAR' && r.phone && (
                  <a href={`https://wa.me/${r.phone.replace(/\D/g, '')}`} target="_blank" rel="noopener noreferrer" className="press inline-flex min-h-[40px] items-center gap-1.5 rounded-btn border border-primary/40 px-3 font-medium text-primary-ink hover:bg-primary/10">
                    <MessageCircle size={16} strokeWidth={ICON_STROKE} aria-hidden /> Conversar
                  </a>
                )}
                <Button size="sm" loading={resolve.isPending} onClick={() => act(r, true)}>
                  <Check size={16} strokeWidth={ICON_STROKE} aria-hidden /> {k.approve}
                </Button>
                {r.kind !== 'FALAR' && (
                  <Button size="sm" variant="secondary" loading={resolve.isPending} onClick={() => act(r, false)} aria-label={`Recusar pedido de ${r.name}`}>
                    <X size={16} strokeWidth={ICON_STROKE} aria-hidden />
                  </Button>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      <Modal open={!!proof} onClose={() => setProof(null)} title={proof ? `Comprovante de ${proof.name}` : ''}>
        {proof?.media_url && <img src={proof.media_url} alt={`Comprovante de ${proof.name}`} className="mx-auto max-h-[70vh] rounded-btn" />}
        {proof && (
          <div className="mt-3 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => { act(proof, false); setProof(null) }}>Recusar</Button>
            <Button onClick={() => { act(proof, true); setProof(null) }}>Confirmar pagamento de {money(proof.amount)}</Button>
          </div>
        )}
      </Modal>
    </section>
  )
}
