import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Flag, Goal, Sun, Trash2 } from 'lucide-react'
import { ApiError } from '@/api/client'
import { useMatchSheet, useSheetActions } from '@/api/stats'
import { reopenMatch, useMatchResult } from '@/api/tournaments'
import { useQueryClient } from '@tanstack/react-query'
import { useConfirm, useToast } from '@/contexts/feedback'
import { formatClock, unfinishStopwatch, useStopwatch } from '@/hooks/useStopwatch'
import { useWakeLock } from '@/hooks/useWakeLock'
import type { EventType, MatchItem } from '@/api/types'
import { eventLabel } from '@/lib/labels'
import { teamColor } from '@/lib/teamColors'
import { Alert, Button, CardIcon, ICON_STROKE, PlayerName, Spinner, StopwatchView, cx } from './ui'

function EventIcon({ type, animate }: { type: EventType; animate?: boolean }) {
  if (type === 'AMARELO') return <CardIcon color="yellow" animate={animate} />
  if (type === 'VERMELHO') return <CardIcon color="red" />
  return <Goal size={16} strokeWidth={ICON_STROKE} aria-hidden />
}

type Step =
  | { kind: 'idle' }
  | { kind: 'player'; type: EventType; teamId: number }
  | { kind: 'assist'; teamId: number; scorerId: number | null }

/** Súmula: registrar gols (autor, assistência, gol contra) e cartões por jogador. */
export function MatchSheetPanel({ match, canEdit, tieRule, onFinished }: {
  match: MatchItem
  canEdit: boolean
  /** regra de empate do mata-mata (do campeonato): com PENALTIS, pede o placar dos pênaltis ao finalizar */
  tieRule?: string
  /** chamado depois de "Finalizar súmula" enviar o resultado */
  onFinished?: () => void
}) {
  const { data: sheet, isLoading } = useMatchSheet(match.id)
  const { add, remove } = useSheetActions(match.id)
  const [step, setStep] = useState<Step>({ kind: 'idle' })
  const toast = useToast()
  const confirm = useConfirm()
  const sw = useStopwatch(`match-${match.id}`)
  // quem lança a súmula não pode ter a tela apagando no meio do jogo
  const wake = useWakeLock(canEdit && match.status !== 'ENCERRADA')
  const submit = useMatchResult()
  const qc = useQueryClient()
  const [pens, setPens] = useState<{ home: string; away: string }>({ home: '', away: '' })
  const error = add.error ?? remove.error ?? submit.error

  // Gol: placar faz "pop" e o lado do time pisca na cor dele por 600ms
  const [goalFx, setGoalFx] = useState<{ teamId: number; key: number } | null>(null)
  const lastScore = useRef<string | null>(null)
  const knownEvents = useRef<Set<number> | null>(null)
  useEffect(() => {
    if (!sheet) return
    const score = `${sheet.home_score}-${sheet.away_score}`
    if (lastScore.current !== null && lastScore.current !== score) {
      const [h0, a0] = lastScore.current.split('-').map(Number)
      const teamId = sheet.home_score > h0 ? sheet.home_team_id : sheet.away_score > a0 ? sheet.away_team_id : null
      if (teamId) setGoalFx({ teamId, key: Date.now() })
    }
    lastScore.current = score
    // Toast para gols recém-registrados
    const ids = new Set(sheet.events.map((e) => e.id))
    if (knownEvents.current) {
      for (const e of sheet.events) {
        if (!knownEvents.current.has(e.id) && (e.type === 'GOL' || e.type === 'GOL_CONTRA')) {
          toast(e.player_name ? `⚽ Gol de ${e.player_name}${e.type === 'GOL_CONTRA' ? ' (contra)' : ''}` : '⚽ Gol!')
        }
      }
    }
    knownEvents.current = ids
  }, [sheet, toast])
  const newEventIds = knownEvents.current

  if (isLoading || !sheet) return <Spinner />
  const teams = [match.home, match.away].filter(Boolean) as NonNullable<MatchItem['home']>[]
  const rosterOf = (teamId: number) => sheet.rosters[String(teamId)] ?? []
  const opponent = (teamId: number) => teams.find((t) => t.id !== teamId)!

  const knockout = match.stage === 'SEMIFINAL' || match.stage === 'FINAL'
  const tied = sheet.home_score === sheet.away_score
  const needsPens = knockout && tied && tieRule === 'PENALTIS'
  const pensValid = !needsPens || (pens.home !== '' && pens.away !== '' && pens.home !== pens.away)
  const canFinish = !!match.home && !!match.away && pensValid

  const finalize = async () => {
    const home = match.home!
    const away = match.away!
    const ok = await confirm({
      title: 'Finalizar súmula?',
      description: (
        <>
          Placar final <strong className="tabular">Time {home.name} {sheet.home_score} × {sheet.away_score} Time {away.name}</strong>
          {needsPens && <> (pênaltis {pens.home} × {pens.away})</>}. O resultado entra na classificação e no chaveamento.
        </>
      ),
      confirmLabel: 'Finalizar e enviar',
    })
    if (!ok) return
    const endedAt = Date.now()
    const timing = sw.started && sw.firstStartedAt
      ? { started_at: new Date(sw.firstStartedAt).toISOString(), ended_at: new Date(endedAt).toISOString(), played_seconds: Math.floor(sw.elapsedMs / 1000) }
      : {}
    const times = sw.started ? ` · ${formatClock(sw.elapsedMs)} de jogo (${formatClock(endedAt - (sw.firstStartedAt ?? endedAt))} com pausas)` : ''
    const matchId = match.id
    const seq = match.seq
    submit.mutate(
      {
        matchId,
        home_score: sheet.home_score,
        away_score: sheet.away_score,
        ...(needsPens ? { home_penalties: Number(pens.home), away_penalties: Number(pens.away) } : {}),
        ...timing,
      },
      {
        onSuccess: () => {
          if (sw.started) sw.finish()
          toast({
            message: `Jogo ${seq} encerrado: ${sheet.home_score} × ${sheet.away_score}${times}`,
            tone: 'success',
            duration: 8000,
            // Escape para encerramento acidental: reabre a partida e devolve o cronômetro pausado
            action: {
              label: 'Desfazer',
              onClick: () =>
                reopenMatch(qc, matchId)
                  .then(() => {
                    unfinishStopwatch(`match-${matchId}`)
                    toast({ message: `Jogo ${seq} reaberto — a súmula foi mantida`, tone: 'success' })
                  })
                  .catch((err: unknown) => toast({ message: err instanceof ApiError ? err.message : 'Não foi possível reabrir o jogo', tone: 'error' })),
            },
          })
          onFinished?.()
        },
      },
    )
  }

  const register = (type: EventType, teamId: number, playerId: number | null, assistId: number | null = null) =>
    add.mutate({ type, team_id: teamId, player_id: playerId, assist_player_id: assistId }, { onSuccess: () => setStep({ kind: 'idle' }) })

  // Gol contra: o jogador é do time adversário ao beneficiado; o evento é registrado no time dele
  const pickTeam = step.kind === 'player' ? step.teamId : step.kind === 'assist' ? step.teamId : 0

  return (
    <div className="space-y-4">
      {/* Placar da mesa: único lugar (além do login) com o gramado listrado */}
      <div className="pitch-lines flex items-center justify-center gap-4 rounded-card border border-line px-3 py-4 text-center">
        {teams.map((t, i) => (
          <div
            key={goalFx?.teamId === t.id ? `${t.id}-${goalFx.key}` : t.id}
            className={cx('flex flex-1 flex-col items-center rounded-btn py-1', i === 1 && 'order-3', goalFx?.teamId === t.id && 'anim-team-flash')}
            style={{ '--flash': `${teamColor(t.name, t.color)}55` } as CSSProperties}
          >
            <span className="h-4 w-4 rounded-full border border-line" style={{ background: teamColor(t.name, t.color) }} />
            <span className="mt-1 text-sm font-medium">Time {t.name}</span>
          </div>
        ))}
        <span key={goalFx?.key ?? 0} className={cx('tabular order-2 font-display text-5xl font-extrabold', goalFx && 'anim-pop')}>
          {sheet.home_score} <span className="text-muted">×</span> {sheet.away_score}
        </span>
      </div>

      {canEdit && match.status !== 'ENCERRADA' && (
        <div className="rounded-card border border-line py-4">
          <StopwatchView sw={sw} plannedSeconds={match.planned_seconds} hideFinish />
          <p aria-live="polite" className="mt-2 flex min-h-[18px] items-center justify-center gap-1 text-xs text-muted">
            {wake.locked && (
              <>
                <Sun size={13} strokeWidth={ICON_STROKE} aria-hidden /> Tela ligada
              </>
            )}
          </p>
        </div>
      )}

      {error && <Alert>{error instanceof ApiError ? error.message : 'Erro'}</Alert>}

      {canEdit && step.kind === 'idle' && (
        <div className="grid grid-cols-2 gap-3">
          {teams.map((t) => (
            <div key={t.id} className="space-y-2">
              <Button size="lg" className="w-full" onClick={() => setStep({ kind: 'player', type: 'GOL', teamId: t.id })}>
                <Goal size={18} strokeWidth={ICON_STROKE} aria-hidden /> Gol {t.name}
              </Button>
              <div className="grid grid-cols-3 gap-1">
                <Button size="sm" variant="secondary" onClick={() => setStep({ kind: 'player', type: 'AMARELO', teamId: t.id })} aria-label={`Amarelo para o Time ${t.name}`}>
                  <CardIcon color="yellow" size={16} />
                </Button>
                <Button size="sm" variant="secondary" onClick={() => setStep({ kind: 'player', type: 'VERMELHO', teamId: t.id })} aria-label={`Vermelho para o Time ${t.name}`}>
                  <CardIcon color="red" size={16} />
                </Button>
                <Button size="sm" variant="secondary" title="Gol contra (de um jogador deste time)" onClick={() => setStep({ kind: 'player', type: 'GOL_CONTRA', teamId: t.id })}>
                  contra
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {canEdit && step.kind === 'player' && (
        <div className="anim-page rounded-card border border-line p-3">
          <p className="mb-2 flex items-center gap-2 text-sm font-medium">
            <EventIcon type={step.type} /> {eventLabel[step.type]} — {step.type === 'GOL_CONTRA' ? `quem fez contra (Time ${teams.find((t) => t.id === pickTeam)?.name}) a favor do Time ${opponent(pickTeam).name}?` : `quem? (Time ${teams.find((t) => t.id === pickTeam)?.name})`}
          </p>
          <div className="grid max-h-72 grid-cols-2 gap-1.5 overflow-y-auto">
            {rosterOf(pickTeam).map((p) => (
              <Button
                key={p.player_id}
                variant="secondary"
                className="justify-start"
                loading={add.isPending}
                onClick={() =>
                  step.type === 'GOL' ? setStep({ kind: 'assist', teamId: pickTeam, scorerId: p.player_id }) : register(step.type, pickTeam, p.player_id)
                }
              >
                <PlayerName id={p.player_id} name={p.name} />
              </Button>
            ))}
            {step.type === 'GOL' && (
              <Button variant="ghost" onClick={() => register('GOL', pickTeam, null)}>Sem autor identificado</Button>
            )}
          </div>
          <Button variant="ghost" size="sm" className="mt-2" onClick={() => setStep({ kind: 'idle' })}>Cancelar</Button>
        </div>
      )}

      {canEdit && step.kind === 'assist' && (
        <div className="anim-page rounded-card border border-line p-3">
          <p className="mb-2 text-sm font-medium">Assistência (opcional)</p>
          <div className="grid max-h-72 grid-cols-2 gap-1.5 overflow-y-auto">
            <Button loading={add.isPending} onClick={() => register('GOL', step.teamId, step.scorerId)}>Sem assistência</Button>
            {rosterOf(step.teamId)
              .filter((p) => p.player_id !== step.scorerId)
              .map((p) => (
                <Button key={p.player_id} variant="secondary" className="justify-start" loading={add.isPending} onClick={() => register('GOL', step.teamId, step.scorerId, p.player_id)}>
                  <PlayerName id={p.player_id} name={p.name} />
                </Button>
              ))}
          </div>
        </div>
      )}

      <div>
        <p className="mb-1 text-xs font-semibold uppercase text-muted">Lances</p>
        {sheet.events.length === 0 ? (
          <p className="text-sm text-muted">Nenhum lance registrado.</p>
        ) : (
          <ul className="divide-y divide-line text-sm">
            {sheet.events.map((e) => {
              const team = teams.find((t) => t.id === e.team_id)
              return (
                <li key={e.id} className={cx('flex min-h-[44px] items-center gap-2 py-1', newEventIds && !newEventIds.has(e.id) && 'anim-slide-in')}>
                  <span className="grid w-5 place-items-center text-ink">
                    <EventIcon type={e.type} animate={!!newEventIds && !newEventIds.has(e.id)} />
                  </span>
                  <span className="sr-only">{eventLabel[e.type]}</span>
                  <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: team ? teamColor(team.name, team.color) : undefined }} />
                  <span className="flex-1">
                    {e.player_name ? <PlayerName id={e.player_id} name={e.player_name} /> : <em className="text-muted">sem autor</em>}
                    {e.type === 'GOL_CONTRA' && <span className="text-muted"> (contra)</span>}
                    {e.assist_name && <span className="text-muted"> · assist. {e.assist_name}</span>}
                  </span>
                  {e.minute != null && <span className="text-xs text-muted">{e.minute}'</span>}
                  {canEdit && (
                    <button className="press grid h-11 w-11 place-items-center rounded-btn text-muted hover:bg-soft hover:text-danger-ink" aria-label="Excluir lance" onClick={() => remove.mutate(e.id)}>
                      <Trash2 size={16} strokeWidth={ICON_STROKE} />
                    </button>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
      {canEdit && match.status !== 'ENCERRADA' && (
        <div className="sticky bottom-0 -mx-5 -mb-5 space-y-3 border-t border-line bg-surface px-5 pb-5 pt-3">
          {needsPens && (
            <fieldset className="rounded-btn bg-soft p-3">
              <legend className="sr-only">Placar dos pênaltis</legend>
              <p className="mb-2 text-sm font-medium">Empate no mata-mata — placar dos pênaltis</p>
              <div className="grid grid-cols-2 gap-3">
                {(['home', 'away'] as const).map((side) => (
                  <label key={side} className="space-y-1">
                    <span className="block truncate text-xs text-muted">Time {(side === 'home' ? match.home : match.away)?.name}</span>
                    <input
                      className="input tabular text-center font-display text-2xl font-bold"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      value={pens[side]}
                      onChange={(e) => setPens((p) => ({ ...p, [side]: e.target.value }))}
                    />
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          <Button size="xl" className="w-full" loading={submit.isPending} disabled={!canFinish} onClick={finalize}>
            <Flag size={22} strokeWidth={ICON_STROKE} aria-hidden /> Finalizar súmula
          </Button>
        </div>
      )}
    </div>
  )
}
