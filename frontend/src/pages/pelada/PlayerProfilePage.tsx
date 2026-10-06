import { Link, useParams } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { usePlayerProfile } from '@/api/stats'
import { Alert, Avatar, Badge, Card, EmptyState, Spinner } from '@/components/ui'
import { formatDate, playerTypeLabel, positionText } from '@/lib/labels'

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <Card className="p-3 text-center">
      <p className="text-2xl font-bold tabular-nums">{value}</p>
      <p className="text-xs text-muted">{label}</p>
      {hint && <p className="text-[11px] text-muted">{hint}</p>}
    </Card>
  )
}

export function PlayerProfilePage() {
  const id = Number(useParams().id)
  const { data, isLoading, error } = usePlayerProfile(id)
  if (isLoading) return <Spinner />
  if (error || !data) return <Alert>{error instanceof ApiError ? error.message : 'Erro ao carregar'}</Alert>
  const s = data.stats

  return (
    <>
      <Link to="/estatisticas" className="mb-3 inline-block text-sm text-primary-ink hover:underline">‹ Estatísticas</Link>
      <div className="mb-5 flex items-center gap-4">
        <Avatar name={s.name} url={s.photo_url} size={72} />
        <div>
          <h1 className="text-2xl font-bold">{s.name}</h1>
          <div className="mt-1 flex flex-wrap gap-1">
            <Badge color="green">{positionText(s.primary_position)}</Badge>
            <Badge color={s.type === 'MENSALISTA' ? 'blue' : 'yellow'}>{playerTypeLabel[s.type]}</Badge>
            {s.titles > 0 && <Badge color="yellow">🏆 {s.titles} título(s)</Badge>}
          </div>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        <Stat label="Presenças" value={s.presences} />
        <Stat label="Jogos" value={s.matches} hint={`${s.wins}V ${s.draws}E ${s.losses}D`} />
        <Stat label="Aproveitamento" value={`${s.win_rate.toLocaleString('pt-BR')}%`} />
        <Stat label="Gols" value={s.goals} hint={s.matches ? `${(s.goals / s.matches).toLocaleString('pt-BR', { maximumFractionDigits: 2 })} por jogo` : undefined} />
        <Stat label="Assistências" value={s.assists} />
        <Stat label="Cartões" value={`${s.yellows}🟨 ${s.reds}🟥`} />
        <Stat label="Títulos" value={s.titles} />
        <Stat label="Vices" value={s.runner_ups} />
      </div>

      <h2 className="mb-2 text-lg font-semibold">Histórico por rodada</h2>
      {data.history.length === 0 ? (
        <EmptyState>Ainda não jogou nenhuma rodada.</EmptyState>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th className="px-3 py-2 text-left">Rodada</th>
                <th className="py-2 text-left">Time</th>
                <th className="px-2 text-center">J</th>
                <th className="px-2 text-center">V-E-D</th>
                <th className="px-2 text-center">Gols</th>
                <th className="px-2 text-center">Ast</th>
                <th className="px-2 text-center">Cartões</th>
                <th className="px-2 text-center" />
              </tr>
            </thead>
            <tbody>
              {data.history.map((h) => (
                <tr key={h.round_id} className="border-b border-line">
                  <td className="px-3 py-1.5 capitalize">
                    {h.tournament_id ? <Link className="hover:underline" to={`/campeonato/${h.tournament_id}`}>{formatDate(h.date)}</Link> : formatDate(h.date)}
                  </td>
                  <td className="py-1.5">
                    <span className="flex items-center gap-2">
                      <span className="h-3 w-3 rounded-full border border-black/10" style={{ background: h.team_color ?? undefined }} /> {h.team_name}
                    </span>
                  </td>
                  <td className="px-2 text-center tabular-nums">{h.matches}</td>
                  <td className="px-2 text-center tabular-nums">{h.wins}-{h.draws}-{h.losses}</td>
                  <td className="px-2 text-center font-semibold tabular-nums">{h.goals || ''}</td>
                  <td className="px-2 text-center tabular-nums">{h.assists || ''}</td>
                  <td className="px-2 text-center">{'🟨'.repeat(h.yellows)}{'🟥'.repeat(h.reds)}</td>
                  <td className="px-2 text-center">{h.champion ? '🏆' : h.runner_up ? '🥈' : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
