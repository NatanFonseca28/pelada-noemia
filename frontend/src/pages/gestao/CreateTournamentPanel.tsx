import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { useCreateTournament, useFormats, useRoundTournament } from '@/api/tournaments'
import type { RoundDetail } from '@/api/types'
import { Alert, Badge, Button, Card, Field, Spinner, cx } from '@/components/ui'
import { minutesText } from '@/lib/labels'

export function CreateTournamentPanel({ round }: { round: RoundDetail }) {
  const { data: tournament, isLoading: loadingT } = useRoundTournament(round.id)
  const locked = round.status === 'TIMES_TRAVADOS'
  const [weight, setWeight] = useState('1')
  const { data, isLoading, error } = useFormats(round.id, weight, locked && !tournament && !loadingT)
  const [selected, setSelected] = useState<string | null>(null)
  const create = useCreateTournament(round.id)
  const navigate = useNavigate()

  if (loadingT) return null
  if (tournament) {
    return (
      <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div>
          <p className="font-semibold">🏆 {tournament.format_name}</p>
          <p className="text-sm text-muted">
            {tournament.matches.length} jogos · {minutesText(tournament.match_seconds)} por partida
            {tournament.champion && ` · Campeão: Time ${tournament.champion.name}`}
          </p>
        </div>
        <Link to={`/campeonato/${tournament.id}`}>
          <Button>Abrir campeonato →</Button>
        </Link>
      </Card>
    )
  }
  if (!locked) {
    return round.teams.length ? (
      <Card className="p-4 text-sm text-muted">🔒 Trave os times para criar o campeonato da rodada.</Card>
    ) : null
  }

  const keyOf = (o: { code: string; legs: number }) => `${o.code}:${o.legs}`
  const recommended = data?.options.find((o) => o.recommended)
  const selectedKey = selected ?? (recommended ? keyOf(recommended) : null)
  const choice = data?.options.find((o) => keyOf(o) === selectedKey)

  return (
    <Card className="p-4">
      <h2 className="mb-1 font-semibold">🏆 Criar campeonato</h2>
      {data && (
        <p className="mb-3 text-sm text-muted">
          {data.num_teams} times, {data.total_minutes} min no total
        </p>
      )}
      {error && <Alert>{error instanceof ApiError ? error.message : 'Erro ao calcular formatos'}</Alert>}
      {isLoading || !data ? (
        <Spinner />
      ) : (
        <>
          <div className="space-y-2">
            {data.options.map((o) => {
              const active = !!choice && keyOf(choice) === keyOf(o)
              return (
                <button
                  key={keyOf(o)}
                  disabled={!o.feasible}
                  onClick={() => setSelected(keyOf(o))}
                  className={cx(
                    'w-full rounded-lg border p-3 text-left transition disabled:opacity-50',
                    active ? 'border-primary bg-primary/10 ring-2 ring-primary/30' : 'border-line hover:bg-soft',
                  )}
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-medium">
                      {o.name} {o.recommended && <Badge color="green">recomendado</Badge>}
                    </span>
                    <span className="text-sm tabular-nums">
                      <strong>{o.total_matches}</strong> jogos · tabela <strong>{minutesText(o.match_seconds)}</strong>
                      {o.knockout_seconds && <> · mata-mata {minutesText(o.knockout_seconds)}</>}
                      {o.final_seconds && <> · final <strong>{minutesText(o.final_seconds)}</strong></>}
                    </span>
                  </div>
                  <p className="text-xs text-muted">{o.description}</p>
                  {o.note && <Badge color={o.feasible ? 'gray' : 'red'}>{o.note}</Badge>}
                </button>
              )
            })}
          </div>
          {data.options.some((o) => o.final_seconds) && (
            <div className="mt-3 w-48">
              <Field label="Peso do tempo da final" hint="Ex.: 1,5">
                <select className="input" value={weight} onChange={(e) => setWeight(e.target.value)}>
                  {['1', '1.25', '1.5', '2'].map((w) => (
                    <option key={w} value={w}>{w.replace('.', ',')}×</option>
                  ))}
                </select>
              </Field>
            </div>
          )}
          {create.error && <div className="mt-3"><Alert>{create.error instanceof ApiError ? create.error.message : 'Erro'}</Alert></div>}
          <Button
            className="mt-4"
            disabled={!choice}
            loading={create.isPending}
            onClick={() =>
              choice &&
              create.mutate(
                { format_code: choice.code, legs: choice.legs, final_weight: weight },
                { onSuccess: (t) => t && navigate(`/campeonato/${t.id}`) },
              )
            }
          >
            Criar campeonato
          </Button>
        </>
      )}
    </Card>
  )
}
