import { useState, type FormEvent } from 'react'
import { ClipboardList, Flag, Pencil, Plus, RotateCcw, Settings2, Timer, Trophy } from 'lucide-react'
import { Link, Navigate, useParams } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { useRounds } from '@/api/rounds'
import { useTournamentSummary } from '@/api/stats'
import { useTournament, useTournamentActions } from '@/api/tournaments'
import type { MatchItem, Tournament } from '@/api/types'
import { useAuth } from '@/auth/AuthProvider'
import { Confetti } from '@/components/Confetti'
import { MatchSheetPanel } from '@/components/MatchSheetPanel'
import { useConfirm } from '@/contexts/feedback'
import { formatClock, unfinishStopwatch, useStopwatch } from '@/hooks/useStopwatch'
import { matchDuration } from '@/lib/matchTime'
import {
  Alert,
  Badge,
  Bracket,
  Button,
  Card,
  EmptyState,
  Field,
  ICON_STROKE,
  IconButton,
  LiveDot,
  Modal,
  PageHeader,
  ScoreStrip,
  Spinner,
  StandingsTable,
  TeamShield,
  cx,
  type BracketMatch,
} from '@/components/ui'
import { formatDate, knockoutLabel, minutesText, tiebreakerLabel } from '@/lib/labels'

const errorText = (err: unknown) => (err instanceof ApiError ? err.message : 'Algo deu errado')

// ---------------------------------------------------------------- Resultado

function ResultForm({ match, tieRule, onDone }: { match: MatchItem; tieRule: string; onDone: () => void }) {
  const { result } = useTournamentActions(0)
  const done = match.status === 'ENCERRADA'
  const [home, setHome] = useState(done ? match.home_score : 0)
  const [away, setAway] = useState(done ? match.away_score : 0)
  const [hp, setHp] = useState<number | ''>(match.home_penalties ?? '')
  const [ap, setAp] = useState<number | ''>(match.away_penalties ?? '')
  const knockout = match.stage === 'SEMIFINAL' || match.stage === 'FINAL'
  const needsPens = knockout && home === away && tieRule === 'PENALTIS'

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    result.mutate(
      {
        matchId: match.id,
        home_score: home,
        away_score: away,
        ...(needsPens && hp !== '' && ap !== '' ? { home_penalties: hp, away_penalties: ap } : {}),
      },
      { onSuccess: onDone },
    )
  }

  const Stepper = ({ value, set, label }: { value: number; set: (n: number) => void; label: string }) => (
    <div className="flex flex-col items-center gap-2">
      <span className="max-w-[8rem] truncate text-sm font-medium">{label}</span>
      <div className="flex items-center gap-2">
        <button type="button" onClick={() => set(Math.max(0, value - 1))} className="press h-11 w-11 rounded-full bg-soft text-xl" aria-label={`Diminuir ${label}`}>−</button>
        <span className="tabular w-10 text-center font-display text-4xl font-bold">{value}</span>
        <button type="button" onClick={() => set(value + 1)} className="press h-11 w-11 rounded-full bg-primary text-xl text-primary-on" aria-label={`Aumentar ${label}`}>+</button>
      </div>
    </div>
  )

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <div className="flex items-start justify-around">
        <Stepper value={home} set={setHome} label={match.home_label} />
        <span className="pt-10 text-xl text-muted">×</span>
        <Stepper value={away} set={setAway} label={match.away_label} />
      </div>
      {needsPens && (
        <div className="rounded-lg bg-accent/15 p-3">
          <p className="mb-2 text-sm font-medium">Empate — placar dos pênaltis</p>
          <div className="grid grid-cols-2 gap-3">
            <Field label={match.home_label}>
              <input className="input" type="number" min={0} required value={hp} onChange={(e) => setHp(e.target.value === '' ? '' : Number(e.target.value))} />
            </Field>
            <Field label={match.away_label}>
              <input className="input" type="number" min={0} required value={ap} onChange={(e) => setAp(e.target.value === '' ? '' : Number(e.target.value))} />
            </Field>
          </div>
        </div>
      )}
      {result.error && <Alert>{errorText(result.error)}</Alert>}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={result.isPending}>{done ? 'Corrigir resultado' : 'Encerrar partida'}</Button>
      </div>
    </form>
  )
}

// ---------------------------------------------------------------- Jogos

const matchTitle = (m: MatchItem) =>
  m.stage === 'GRUPO' ? `Grupo ${m.group ?? ''}${m.leg === 2 ? ' · volta' : ''}` : m.stage === 'AMISTOSO' ? 'Partida' : knockoutLabel(m.code)

function MatchCard({ match, isNext, canEdit, onEdit, onReopen, onSheet }: {
  match: MatchItem
  isNext: boolean
  canEdit: boolean
  onEdit: () => void
  onReopen: () => void
  onSheet: () => void
}) {
  const done = match.status === 'ENCERRADA'
  const ready = !!match.home && !!match.away
  const winnerSide = done && match.winner_team_id ? (match.winner_team_id === match.home?.id ? 'home' : 'away') : null
  const showActions = ready && (canEdit || done)
  // cronômetro local desta partida (só aparece no aparelho de quem está com a súmula)
  const sw = useStopwatch(`match-${match.id}`)
  const clockOn = !done && sw.started && !sw.finished
  const duration = done ? matchDuration(match) : null
  return (
    <li className={cx('rounded-card p-3', isNext ? 'bg-accent/10 ring-1 ring-inset ring-accent/50' : 'bg-surface shadow-card')}>
      <div className="mb-2 flex items-center justify-between gap-2 text-xs">
        <span className="font-display text-sm font-semibold text-muted">
          Jogo {match.seq} · {matchTitle(match)}
        </span>
        {clockOn ? (
          <LiveDot label={`${sw.running ? 'Em andamento' : 'Pausado'} ${formatClock(sw.elapsedMs)}`} />
        ) : (
          isNext && !done && <LiveDot label="Próxima" />
        )}
        {done && <span className="font-display text-sm font-semibold text-muted">Encerrado</span>}
      </div>
      <ScoreStrip
        size="md"
        home={match.home}
        away={match.away}
        homeLabel={match.home_label}
        awayLabel={match.away_label}
        homeScore={done ? match.home_score : null}
        awayScore={done ? match.away_score : null}
        winnerSide={winnerSide}
        center={
          done
            ? match.home_penalties != null
              ? <span className="text-[11px] leading-tight">pên.<br />{match.home_penalties}–{match.away_penalties}</span>
              : 'FIM'
            : minutesText(match.planned_seconds).replace(' min', '′')
        }
      />
      {duration && (
        <p className="mt-2 flex flex-wrap items-center gap-x-2 text-xs text-muted">
          <Timer size={14} strokeWidth={ICON_STROKE} aria-hidden />
          {duration.played && <span><span className="tabular font-semibold text-ink">{duration.played}</span> de jogo</span>}
          {duration.wall && <span><span className="tabular font-semibold text-ink">{duration.wall}</span> com pausas</span>}
        </p>
      )}
      {showActions && (
        <div className="mt-2 flex gap-2">
          <Button variant="secondary" className="flex-1" onClick={onSheet}>
            <ClipboardList size={18} strokeWidth={ICON_STROKE} aria-hidden /> Súmula
          </Button>
          {canEdit && (
            <Button variant={done ? 'secondary' : 'primary'} className="flex-1" onClick={onEdit}>
              {done ? <Pencil size={16} strokeWidth={ICON_STROKE} aria-hidden /> : <Flag size={18} strokeWidth={ICON_STROKE} aria-hidden />}
              {done ? 'Corrigir' : 'Resultado'}
            </Button>
          )}
          {canEdit && done && (
            <IconButton label={`Reabrir jogo ${match.seq}`} onClick={onReopen} className="border border-line">
              <RotateCcw size={18} strokeWidth={ICON_STROKE} />
            </IconButton>
          )}
        </div>
      )}
    </li>
  )
}

/** Quantos avançam do grupo, pelo formato (só para destacar na tabela). */
const QUALIFY: Record<string, number> = {
  GRUPO_REPESCAGEM_FINAL: 3,
  GRUPO_SEMI_FINAL: 4,
  GRUPO_FINAL: 2,
  DOIS_GRUPOS_SEMI_FINAL: 2,
  DOIS_GRUPOS_FINAL: 1,
}

const toBracket = (m: MatchItem): BracketMatch => ({
  id: m.id,
  code: m.code,
  title: m.code === 'F' ? 'Final' : knockoutLabel(m.code),
  home: m.home,
  away: m.away,
  homeLabel: m.home_label,
  awayLabel: m.away_label,
  homeScore: m.status === 'ENCERRADA' ? m.home_score : null,
  awayScore: m.status === 'ENCERRADA' ? m.away_score : null,
  homePens: m.home_penalties,
  awayPens: m.away_penalties,
  winnerSide: m.status === 'ENCERRADA' && m.winner_team_id ? (m.winner_team_id === m.home?.id ? 'home' : 'away') : null,
})

// ---------------------------------------------------------------- Resumo

const tiebreakText: Record<string, string> = {
  DIVIDIDA: 'artilharia dividida',
  MAIS_ASSISTENCIAS: 'desempate por assistências',
  MENOS_JOGOS: 'desempate por menos jogos',
  SORTEIO: 'desempate por sorteio',
}

function SummaryCard({ tournamentId }: { tournamentId: number }) {
  const { data } = useTournamentSummary(tournamentId)
  if (!data || (!data.total_goals && !data.total_yellows && !data.total_reds)) return null
  return (
    <Card className="p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase text-muted">⚽ Artilharia</p>
          {data.top_scorers.length ? (
            <>
              {data.top_scorers.map((s) => (
                <p key={s.player_id} className="text-lg font-semibold">
                  <Link to={`/jogadores/${s.player_id}`} className="hover:underline">{s.name}</Link>{' '}
                  <span className="text-sm font-normal text-muted">{s.goals} gol(s) · Time {s.team_name}</span>
                </p>
              ))}
              {data.top_scorers.length > 1 || data.scorers.filter((x) => x.goals === data.top_scorers[0].goals).length > 1 ? (
                <p className="text-xs text-muted">{tiebreakText[data.tiebreak]}</p>
              ) : null}
              <p className="mt-1 text-xs text-muted">
                {data.scorers.slice(data.top_scorers.length, data.top_scorers.length + 4).map((s) => `${s.name} ${s.goals}`).join(' · ')}
              </p>
            </>
          ) : (
            <p className="text-sm text-muted">Nenhum gol com autor registrado.</p>
          )}
        </div>
        <div>
          <p className="text-xs font-semibold uppercase text-muted">Cartões</p>
          <p className="text-lg font-semibold">{data.total_yellows} 🟨 · {data.total_reds} 🟥</p>
          <p className="text-xs text-muted">{data.cards.map((c) => `${c.name} ${'🟨'.repeat(c.yellows)}${'🟥'.repeat(c.reds)}`).join(' · ')}</p>
        </div>
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------- Página

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-btn bg-soft px-3 py-2">
      <p className="tabular font-display text-xl font-bold leading-none">{value}</p>
      <p className="mt-1 text-xs text-muted">{label}</p>
    </div>
  )
}

function TournamentView({ t }: { t: Tournament }) {
  const { hasRole } = useAuth()
  const canEdit = hasRole('ADMIN', 'MESARIO')
  const isAdmin = hasRole('ADMIN')
  const actions = useTournamentActions(t.id)
  const confirm = useConfirm()
  const [editing, setEditing] = useState<MatchItem | null>(null)
  const [sheetFor, setSheetFor] = useState<MatchItem | null>(null)
  const casual = t.format_code === 'PELADA_NORMAL'
  const final = t.matches.find((m) => m.stage === 'FINAL')
  const semis = t.matches.filter((m) => m.stage === 'SEMIFINAL')
  const err = actions.reopen.error ?? actions.addMatch.error ?? actions.finish.error

  return (
    <>
      <PageHeader
        title={casual ? 'Pelada normal' : 'Campeonato'}
        subtitle={`${formatDate(t.round_date)} — ${t.format_name}`}
        actions={
          isAdmin && (
            <Link to={`/gestao/rodadas/${t.round_id}`} className="press inline-flex min-h-[44px] items-center gap-1.5 rounded-btn px-3 text-sm font-medium text-primary-ink hover:bg-soft">
              <Settings2 size={16} strokeWidth={ICON_STROKE} aria-hidden /> Gerenciar rodada
            </Link>
          )
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="jogos" value={String(t.matches.length)} />
        <Stat label="jogo de tabela" value={minutesText(t.match_seconds)} />
        {t.knockout_seconds ? <Stat label="mata-mata" value={minutesText(t.knockout_seconds)} /> : null}
        {t.final_seconds ? <Stat label="final" value={minutesText(t.final_seconds)} /> : null}
      </div>

      {t.champion && (
        <Card className="anim-champion relative mb-5 overflow-hidden p-5 ring-1 ring-inset ring-accent/50">
          <Confetti />
          <div className="flex items-center gap-4">
            <TeamShield name={t.champion.name} color={t.champion.color} size={56} />
            <div className="min-w-0">
              <p className="flex items-center gap-1.5 text-sm font-medium text-accent-ink"><Trophy size={16} strokeWidth={ICON_STROKE} aria-hidden /> Campeão</p>
              <p className="font-display text-3xl font-bold leading-tight">Time {t.champion.name}</p>
              {t.runner_up && <p className="text-sm text-muted">Vice: Time {t.runner_up.name}</p>}
            </div>
          </div>
        </Card>
      )}
      {err && <div className="mb-4"><Alert>{errorText(err)}</Alert></div>}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section aria-labelledby="jogos">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 id="jogos" className="font-display text-2xl font-bold">Jogos</h2>
            {casual && canEdit && t.status === 'EM_ANDAMENTO' && (
              <div className="flex gap-2">
                <Button size="sm" variant="primary" onClick={() => actions.addMatch.mutate(undefined)} loading={actions.addMatch.isPending}>
                  <Plus size={16} strokeWidth={ICON_STROKE} aria-hidden /> Próxima partida
                </Button>
                {isAdmin && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={async () => (await confirm({ title: 'Encerrar a pelada da noite?', description: 'Partidas não jogadas serão descartadas.', confirmLabel: 'Encerrar' })) && actions.finish.mutate(undefined)}
                  >
                    Encerrar
                  </Button>
                )}
              </div>
            )}
          </div>
          <ul className="space-y-3">
            {t.matches.map((m) => (
              <MatchCard
                key={m.id}
                match={m}
                isNext={m.id === t.next_match_id}
                canEdit={canEdit}
                onEdit={() => setEditing(m)}
                onReopen={async () =>
                  (await confirm({
                    title: `Reabrir o jogo ${m.seq}?`,
                    description: 'Use se a partida foi encerrada por engano. O resultado deixa de valer na classificação; a súmula e o cronômetro são mantidos.',
                    confirmLabel: 'Reabrir jogo',
                  })) && actions.reopen.mutate(m.id, { onSuccess: () => unfinishStopwatch(`match-${m.id}`) })
                }
                onSheet={() => setSheetFor(m)}
              />
            ))}
          </ul>
        </section>

        <section className="space-y-4" aria-labelledby="tabela">
          <SummaryCard tournamentId={t.id} />
          <h2 id="tabela" className="font-display text-2xl font-bold">{casual ? 'Placar da noite' : 'Classificação'}</h2>
          {t.groups.map((g) => (
            <Card key={g.name} className="p-2">
              <div className="flex items-center justify-between px-3 pb-1 pt-2">
                <h3 className="font-display text-lg font-semibold">{t.groups.length > 1 ? `Grupo ${g.name}` : casual ? 'Vitórias e gols' : 'Grupo único'}</h3>
                {g.complete && <Badge color="green">encerrado</Badge>}
              </div>
              <StandingsTable rows={g.standings} qualify={casual ? 0 : QUALIFY[t.format_code] ?? 0} caption={`Classificação ${g.name}`} />
            </Card>
          ))}
          {!casual && (
            <p className="text-xs text-muted">
              Desempate: {t.config.tiebreakers.map((c) => tiebreakerLabel[c as keyof typeof tiebreakerLabel] ?? c).join(', ')}.
            </p>
          )}
          {final && (
            <>
              <h2 className="pt-2 font-display text-2xl font-bold">Mata-mata</h2>
              <Card className="p-4">
                <Bracket semis={semis.map(toBracket)} final={toBracket(final)} />
              </Card>
            </>
          )}
        </section>
      </div>

      <Modal open={!!sheetFor} onClose={() => setSheetFor(null)} title={sheetFor ? `Súmula · jogo ${sheetFor.seq}` : ''} size="lg">
        {sheetFor && (
          <MatchSheetPanel
            key={sheetFor.id}
            match={t.matches.find((m) => m.id === sheetFor.id) ?? sheetFor}
            canEdit={canEdit}
            tieRule={t.config.knockout_tie_rule}
            onFinished={() => setSheetFor(null)}
          />
        )}
      </Modal>

      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing ? `Jogo ${editing.seq} · ${matchTitle(editing)}` : ''}>
        {editing && <ResultForm key={editing.id} match={editing} tieRule={t.config.knockout_tie_rule} onDone={() => setEditing(null)} />}
      </Modal>
    </>
  )
}

export function TournamentPage() {
  const id = Number(useParams().id)
  const { data, isLoading, error } = useTournament(id)
  if (isLoading) return <Spinner />
  if (error || !data) return <Alert>{errorText(error)}</Alert>
  return <TournamentView t={data} />
}

/** /campeonato: abre o campeonato mais recente. */
export function LatestTournamentPage() {
  const { data: rounds, isLoading } = useRounds()
  if (isLoading) return <Spinner />
  const latest = rounds?.find((r) => r.tournament_id)
  if (!latest?.tournament_id) {
    return (
      <>
        <PageHeader title="Campeonato" />
        <EmptyState>Nenhum campeonato criado ainda.</EmptyState>
      </>
    )
  }
  return <Navigate to={`/campeonato/${latest.tournament_id}`} replace />
}
