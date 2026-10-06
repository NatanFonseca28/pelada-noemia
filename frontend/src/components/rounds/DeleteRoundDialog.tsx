import { useState } from 'react'
import { useDeleteRound } from '@/api/rounds'
import type { RoundSummary } from '@/api/types'
import { useToast } from '@/contexts/feedback'
import { Button, Field, Modal, errorMessage } from '@/components/ui'

const dayMonth = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

/** Exclusão de rodada (só gestão). Rodada já jogada apaga tudo dela e exige digitar a data para confirmar. */
export function DeleteRoundDialog({ round, onClose, onDeleted }: { round: RoundSummary | null; onClose: () => void; onDeleted?: () => void }) {
  const del = useDeleteRound()
  const toast = useToast()
  const [typed, setTyped] = useState('')
  if (!round) return null
  const played = round.status === 'TIMES_TRAVADOS' || round.status === 'ENCERRADA'
  const day = dayMonth(round.date)
  const ok = !played || typed.trim() === day

  const close = () => {
    setTyped('')
    onClose()
  }
  const run = () =>
    del.mutate(
      { id: round.id, force: played },
      {
        onSuccess: () => {
          toast({ message: `Rodada de ${day} excluída`, tone: 'success' })
          close()
          onDeleted?.()
        },
        onError: (err) => toast({ message: errorMessage(err, 'Não foi possível excluir a rodada'), tone: 'error' }),
      },
    )

  return (
    <Modal
      open
      onClose={close}
      title={`Excluir a rodada de ${day}?`}
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={close}>Cancelar</Button>
          <Button variant="danger" disabled={!ok} loading={del.isPending} onClick={run}>Excluir rodada</Button>
        </div>
      }
    >
      <div className="space-y-3 text-sm">
        {played ? (
          <>
            <p>
              Somem junto: {round.confirmed_count} presenças, os times
              {round.tournament_id ? ', o campeonato, as partidas e a súmula' : ''}. Gols, títulos e presenças dessa
              rodada saem das estatísticas. Mensalidades e caixa não mudam.
            </p>
            <Field label={`Digite ${day} para confirmar`}>
              <input className="input" inputMode="numeric" autoFocus value={typed} onChange={(e) => setTyped(e.target.value)} placeholder={day} />
            </Field>
          </>
        ) : (
          <p>Somem junto as {round.confirmed_count} presenças e o sorteio.</p>
        )}
      </div>
    </Modal>
  )
}
