import { useMemo, useState, type DragEvent } from 'react'
import { Check, Trash2 } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { usePlayers } from '@/api/queries'
import { useRound, useRoundActions } from '@/api/rounds'
import type { Player, RoundDetail, TeamItem, TeamPlayerItem } from '@/api/types'
import { DeleteRoundDialog } from '@/components/rounds/DeleteRoundDialog'
import { ShareButton } from '@/components/ShareButton'
import { teamsText } from '@/lib/share'
import { useCompetitions } from '@/api/catalog'
import { BalanceSummary, DRAG_MIME, SharedGoalkeepers, TeamCard } from '@/components/TeamCard'
import { CreateTournamentPanel } from './CreateTournamentPanel'
import { Alert, Badge, Button, Card, ICON_STROKE, Modal, PageHeader, PlayerName, Spinner, TypeLegend, cx } from '@/components/ui'
import { filledByLabel, formatDate, positionShort, roundStatusLabel, slotPositionShort } from '@/lib/labels'

const errorText = (err: unknown) => (err instanceof ApiError ? err.message : 'Algo deu errado')

// ---------------------------------------------------------------- Presença

function AttendancePanel({ round, players }: { round: RoundDetail; players: Player[] }) {
  const { attendance } = useRoundActions(round.id)
  const [q, setQ] = useState('')
  const [onlyConfirmed, setOnlyConfirmed] = useState(false)
  const confirmed = useMemo(() => new Set(round.attendances.map((a) => a.player_id)), [round.attendances])
  const editable = round.status === 'ABERTA' || round.status === 'FECHADA'

  const list = players
    .filter((p) => p.active || confirmed.has(p.id))
    .filter((p) => (onlyConfirmed ? confirmed.has(p.id) : true))
    .filter((p) => p.display_name.toLowerCase().includes(q.toLowerCase()) || p.name.toLowerCase().includes(q.toLowerCase()))
    .sort((a, b) => Number(confirmed.has(b.id)) - Number(confirmed.has(a.id)) || a.display_name.localeCompare(b.display_name))

  const counts = round.attendances.reduce<Record<string, number>>((acc, a) => {
    const k = a.primary_position ?? 'SEM'
    acc[k] = (acc[k] ?? 0) + 1
    return acc
  }, {})
  const line = round.attendances.length - (counts.GOLEIRO_FIXO ?? 0)

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex flex-wrap items-center gap-x-3 font-semibold">
          Presença · {round.attendances.length} confirmados <TypeLegend className="font-normal" />
          <Link to={`/gestao/presenca?rodada=${round.id}`} className="text-sm font-normal text-primary-ink hover:underline">
            Gerenciar presença ›
          </Link>
        </h2>
        <div className="flex flex-wrap gap-1 text-xs">
          <Badge color="green">Linha: {line}</Badge>
          <Badge>ZAG {counts.ZAGUEIRO ?? 0}</Badge>
          <Badge>ALA {counts.ALA ?? 0}</Badge>
          <Badge>ATA {counts.ATACANTE ?? 0}</Badge>
          <Badge color="blue">GOL {counts.GOLEIRO_FIXO ?? 0}</Badge>
          {counts.SEM ? <Badge color="yellow">Sem posição {counts.SEM}</Badge> : null}
        </div>
      </div>
      {attendance.error && <div className="mb-2"><Alert>{errorText(attendance.error)}</Alert></div>}
      {!editable && <div className="mb-2"><Alert kind="info">Times travados: destrave para alterar a lista.</Alert></div>}
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <input className="input max-w-xs" placeholder="Buscar jogador" value={q} onChange={(e) => setQ(e.target.value)} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="accent-primary" checked={onlyConfirmed} onChange={(e) => setOnlyConfirmed(e.target.checked)} />
          Só confirmados
        </label>
      </div>
      <ul className="grid max-h-[28rem] gap-1 overflow-y-auto sm:grid-cols-2">
        {list.map((p) => {
          const on = confirmed.has(p.id)
          return (
            <li key={p.id}>
              <button
                disabled={!editable || attendance.isPending}
                onClick={() => attendance.mutate({ playerId: p.id, confirmed: !on })}
                className={cx(
                  'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition disabled:opacity-60',
                  on
                    ? 'border-primary bg-primary/10'
                    : 'border-line hover:bg-soft',
                )}
                aria-pressed={on}
              >
                <span className={cx('grid h-6 w-6 place-items-center rounded-full border text-xs', on ? 'border-primary bg-primary text-primary-on' : 'border-line')}>
                  {on && <Check key={`on-${p.id}`} size={14} strokeWidth={2.5} className="anim-pop-in" aria-hidden />}
                </span>
                <PlayerName name={p.display_name} type={p.type} className="flex-1" />
                <span className="text-xs text-muted">{p.primary_position ? positionShort[p.primary_position] : '—'}</span>
              </button>
            </li>
          )
        })}
      </ul>
    </Card>
  )
}

// ---------------------------------------------------------------- Sorteio

function MoveDialog({
  player,
  round,
  onClose,
}: {
  player: TeamPlayerItem | { player_id: number; name: string }
  round: RoundDetail
  onClose: () => void
}) {
  const { move } = useRoundActions(round.id)
  const current = round.teams.find((t) => t.players.some((p) => p.player_id === player.player_id))
  const slot = current?.players.find((p) => p.player_id === player.player_id)

  const run = (body: Parameters<typeof move.mutate>[0]) => move.mutate(body, { onSuccess: onClose })

  return (
    <div className="space-y-4">
      <p className="text-sm">
        <span className="font-semibold">{player.name}</span>
        {current ? <> está no <span className="font-medium">Time {current.name}</span>.</> : ' ainda não está em nenhum time.'}
      </p>
      {move.error && <Alert>{errorText(move.error)}</Alert>}
      <div>
        <p className="mb-2 text-xs font-semibold uppercase text-muted">Mover para</p>
        <div className="grid grid-cols-2 gap-2">
          {round.teams
            .filter((t) => t.id !== current?.id)
            .map((t) => (
              <Button key={t.id} variant="secondary" onClick={() => run({ player_id: player.player_id, team_id: t.id })} loading={move.isPending}>
                <span className="h-3 w-3 rounded-full border border-black/10" style={{ background: t.color }} /> Time {t.name}
              </Button>
            ))}
        </div>
      </div>
      {current && slot && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-muted">Função</p>
          <div className="flex flex-wrap gap-2">
            {slot.role !== 'REVEZAMENTO' && (
              <Button size="sm" variant="secondary" onClick={() => run({ player_id: player.player_id, team_id: current.id, role: 'REVEZAMENTO' })}>
                🧤 Revezar no gol
              </Button>
            )}
            {slot.role !== 'LINHA' && (
              <Button size="sm" variant="secondary" onClick={() => run({ player_id: player.player_id, team_id: current.id, role: 'LINHA' })}>
                Jogar na linha
              </Button>
            )}
            {slot.role !== 'GOLEIRO_FIXO' && !current.has_fixed_gk && (
              <Button size="sm" variant="secondary" onClick={() => run({ player_id: player.player_id, team_id: current.id, role: 'GOLEIRO_FIXO' })}>
                Goleiro fixo
              </Button>
            )}
          </div>
        </div>
      )}
      <div className="flex justify-between border-t border-line pt-3">
        {current ? (
          <Button variant="ghost" className="text-danger-ink" onClick={() => run({ player_id: player.player_id, team_id: null })}>
            Tirar do time
          </Button>
        ) : (
          <span />
        )}
        <Button variant="secondary" onClick={onClose}>Fechar</Button>
      </div>
    </div>
  )
}

function DrawPanel({ round }: { round: RoundDetail }) {
  const { draw, move, status } = useRoundActions(round.id)
  const [selected, setSelected] = useState<{ player_id: number; name: string } | null>(null)
  const editable = round.status === 'ABERTA' || round.status === 'FECHADA'
  const locked = round.status === 'TIMES_TRAVADOS'
  const d = round.draw
  const [allowShort, setAllowShort] = useState(d?.allow_short_team ?? false)
  const competitions = useCompetitions(editable)
  // lembra o último campeonato usado; 1º sorteio: Brasileirão, se o catálogo já tiver clubes
  const [competition, setCompetition] = useState<string>(d ? d.competition ?? '' : 'BSA')
  const available = (competitions.data ?? []).filter((c) => c.clubs > 0)
  const chosen = available.some((c) => c.code === competition) ? competition : ''

  const drop = (team: TeamItem) => (playerId: number) => {
    if (!team.players.some((p) => p.player_id === playerId)) move.mutate({ player_id: playerId, team_id: team.id })
  }
  const removeDrop = (e: DragEvent) => {
    e.preventDefault()
    const id = Number(e.dataTransfer.getData(DRAG_MIME))
    if (id && round.teams.some((t) => t.players.some((p) => p.player_id === id))) move.mutate({ player_id: id, team_id: null })
  }

  const doDraw = (num_teams?: number) => {
    if (round.teams.length && !confirm('Refazer o sorteio? Os ajustes manuais serão perdidos.')) return
    draw.mutate({ ...(num_teams ? { num_teams } : {}), allow_short_team: allowShort, competition: chosen || null })
  }

  const error = draw.error ?? move.error ?? status.error
  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex flex-wrap items-center gap-x-3 font-semibold">
          Sorteio dos times <TypeLegend className="font-normal" />
        </h2>
        <div className="flex flex-wrap gap-2">
          {locked && round.teams.length > 0 && <ShareButton text={() => teamsText(round.date, round.teams, round.shared_goalkeepers)} label="Compartilhar times" />}
          {editable && (
            <Button onClick={() => doDraw()} loading={draw.isPending}>
              🎲 {round.teams.length ? 'Refazer sorteio' : 'Sortear times'}
            </Button>
          )}
          {editable && round.teams.length > 0 && (
            <Button variant="secondary" onClick={() => confirm('Travar os times? Depois disso não será possível sortear de novo sem destravar.') && status.mutate('lock')} loading={status.isPending}>
              🔒 Travar times
            </Button>
          )}
          {locked && (
            <Button variant="secondary" onClick={() => status.mutate('unlock')} loading={status.isPending}>
              🔓 Destravar
            </Button>
          )}
        </div>
      </div>

      {editable && (
        <label className="mb-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="font-medium">Times do sorteio</span>
          <select className="input w-auto" value={chosen} onChange={(e) => setCompetition(e.target.value)} aria-label="Campeonato dos nomes dos times">
            <option value="">Cores (Verde, Azul, Vermelho…)</option>
            {available.map((c) => (
              <option key={c.code} value={c.code}>{c.name}{c.season ? ` ${c.season}` : ''} · {c.clubs} times</option>
            ))}
          </select>
          {competitions.data && available.length === 0 && (
            <span className="text-xs text-muted">Nenhum campeonato carregado: o superadmin atualiza em Configurações.</span>
          )}
        </label>
      )}
      {editable && (
        <label className="mb-3 flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-0.5 h-4 w-4 accent-primary" checked={allowShort} onChange={(e) => setAllowShort(e.target.checked)} />
          <span>
            Permitir um time com um a menos
            <span className="block text-xs text-muted">Se faltar só 1 para formar mais um time, ele é completado na hora por alguém do time que está de fora (só com 3 times ou mais).</span>
          </span>
        </label>
      )}
      {error && <div className="mb-3"><Alert>{errorText(error)}</Alert></div>}
      {!d && !error && (
        <p className="py-6 text-center text-sm text-muted">
          Confirme os presentes e clique em <strong>Sortear times</strong>. Sortear fecha a lista de presença.
        </p>
      )}

      {d && (
        <div className="mb-4 space-y-2">
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <Badge color={d.mode === 'CAMPEONATO' ? 'green' : 'yellow'}>{d.mode === 'CAMPEONATO' ? 'Campeonato' : 'Pelada normal (2 gols ou 10 min)'}</Badge>
            <span>{d.num_teams} times · seed <code className="font-mono">{d.seed}</code> · {new Date(d.created_at).toLocaleString('pt-BR')}</span>
            {locked && <Badge color="blue">🔒 Travados</Badge>}
            <BalanceSummary teams={round.teams} />
          </div>
          {d.warnings.map((w) => <Alert key={w}>{w}</Alert>)}
          {d.infos.map((i) => <Alert key={i} kind="info">{i}</Alert>)}
          {d.alternatives.length > 0 && editable && (
            <div className="rounded-lg border border-accent/60 bg-accent/15 p-3 text-sm">
              <p className="mb-2 font-medium">Formações possíveis — escolha uma:</p>
              <div className="flex flex-wrap gap-2">
                {d.alternatives.map((a) => (
                  <Button key={a.num_teams} size="sm" variant={a.num_teams === d.num_teams ? 'primary' : 'secondary'} onClick={() => a.num_teams !== d.num_teams && doDraw(a.num_teams)}>
                    {a.description}
                  </Button>
                ))}
              </div>
            </div>
          )}
          {d.substitutions.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer text-muted">
                {d.substitutions.length} vaga(s) completada(s) fora da posição principal
              </summary>
              <ul className="mt-1 list-inside list-disc text-muted">
                {d.substitutions.map((s) => (
                  <li key={s.player_id}>
                    {s.name} como {slotPositionShort[s.position]} no Time {round.teams[s.team_index]?.name ?? s.team_index + 1} ({filledByLabel[s.filled_by]})
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {(round.not_in_teams.length > 0 || round.no_longer_confirmed.length > 0) && (
        <div className="mb-3 space-y-2">
          {round.not_in_teams.length > 0 && (
            <Alert kind="info">
              Confirmados fora dos times — reservas ou confirmados depois do sorteio (arraste para um time ou toque para escolher):{' '}
              {round.not_in_teams.map((p) => (
                <button
                  key={p.player_id}
                  draggable={editable}
                  onDragStart={(e) => e.dataTransfer.setData(DRAG_MIME, String(p.player_id))}
                  onClick={() => editable && setSelected(p)}
                  className="mx-0.5 rounded bg-surface px-1.5 py-0.5 font-medium underline decoration-dotted"
                >
                  <PlayerName id={p.player_id} name={p.name} />
                </button>
              ))}
            </Alert>
          )}
          {round.no_longer_confirmed.length > 0 && (
            <Alert>Cancelaram mas estão em time: {round.no_longer_confirmed.map((p) => p.name).join(', ')}. Toque no jogador e use “Tirar do time”.</Alert>
          )}
        </div>
      )}

      {round.teams.length > 0 && (
        <>
          <SharedGoalkeepers players={round.shared_goalkeepers} />
          <div className={cx('grid gap-3 sm:grid-cols-2', round.teams.length >= 3 && 'lg:grid-cols-3', round.teams.length >= 4 && 'xl:grid-cols-4')}>
              {round.teams.map((t) => (
              <TeamCard key={t.id} team={t} editable={editable} onDropPlayer={drop(t)} onPlayerClick={editable ? setSelected : undefined} />
            ))}
          </div>
          {editable && (
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={removeDrop}
              className="mt-3 rounded-lg border-2 border-dashed border-line p-3 text-center text-xs text-muted"
            >
              Solte aqui para tirar o jogador do time
            </div>
          )}
          {move.isPending && <p className="mt-2 text-xs text-muted">Salvando…</p>}
        </>
      )}

      <Modal open={!!selected} onClose={() => setSelected(null)} title="Ajustar jogador">
        {selected && <MoveDialog player={selected} round={round} onClose={() => setSelected(null)} />}
      </Modal>
    </Card>
  )
}

// ---------------------------------------------------------------- Página

export function RoundPage() {
  const id = Number(useParams().id)
  const { data: round, isLoading, error } = useRound(id)
  const { data: players = [] } = usePlayers()
  const { status } = useRoundActions(id)
  const [deleting, setDeleting] = useState(false)
  const navigate = useNavigate()

  if (isLoading) return <Spinner />
  if (error || !round) return <Alert>{errorText(error)}</Alert>

  const noPosition = players.filter((p) => p.active && !p.primary_position).length

  return (
    <>
      <Link to="/gestao/rodadas" className="mb-2 inline-block text-sm text-primary-ink hover:underline">‹ Rodadas</Link>
      <PageHeader
        title={`Rodada de ${formatDate(round.date)}`}
        subtitle={roundStatusLabel[round.status]}
        actions={
          <div className="flex flex-wrap gap-2">
            {round.status === 'ABERTA' && <Button variant="secondary" onClick={() => status.mutate('close')}>Fechar lista</Button>}
            {round.status === 'FECHADA' && <Button variant="secondary" onClick={() => status.mutate('open')}>Reabrir lista</Button>}
            <Button variant="ghost" aria-label="Excluir rodada" onClick={() => setDeleting(true)}>
              <Trash2 size={18} strokeWidth={ICON_STROKE} aria-hidden />
            </Button>
          </div>
        }
      />
      {noPosition > 0 && (
        <div className="mb-4">
          <Alert kind="info">
            {noPosition} jogador(es) ativo(s) estão com posição a definir e entram no sorteio como coringa.{' '}
            <Link to="/gestao/jogadores" className="font-medium underline">Definir posições</Link>
          </Alert>
        </div>
      )}
      <div className="mb-4">
        <CreateTournamentPanel round={round} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <AttendancePanel round={round} players={players} />
        <DrawPanel round={round} />
      </div>
      <DeleteRoundDialog round={deleting ? round : null} onClose={() => setDeleting(false)} onDeleted={() => navigate('/gestao/rodadas')} />
    </>
  )
}
