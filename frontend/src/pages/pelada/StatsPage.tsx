import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { usePlayerStats } from '@/api/stats'
import type { PlayerStats } from '@/api/types'
import { Avatar, Card, EmptyState, PageHeader, PlayerName, Spinner, cx } from '@/components/ui'

type Key = keyof Pick<PlayerStats, 'goals' | 'assists' | 'presences' | 'win_rate' | 'titles' | 'yellows' | 'matches'>

const RANKINGS: { id: string; label: string; sort: Key; tie?: Key; filter?: (s: PlayerStats) => boolean; hint?: string }[] = [
  { id: 'artilharia', label: '⚽ Artilharia', sort: 'goals', tie: 'assists', filter: (s) => s.goals > 0 },
  { id: 'assistencias', label: '🎯 Assistências', sort: 'assists', tie: 'goals', filter: (s) => s.assists > 0 },
  { id: 'presencas', label: '📅 Presenças', sort: 'presences', tie: 'matches' },
  { id: 'aproveitamento', label: '📈 Aproveitamento', sort: 'win_rate', tie: 'matches', filter: (s) => s.matches >= 3, hint: 'mínimo de 3 jogos' },
  { id: 'titulos', label: '🏆 Títulos', sort: 'titles', tie: 'presences', filter: (s) => s.titles + s.runner_ups > 0 },
  { id: 'cartoes', label: '🟨 Cartões', sort: 'yellows', filter: (s) => s.yellows + s.reds > 0 },
]

const COLUMNS: { key: keyof PlayerStats; label: string; title: string }[] = [
  { key: 'presences', label: 'Pres', title: 'Presenças' },
  { key: 'matches', label: 'J', title: 'Jogos' },
  { key: 'wins', label: 'V', title: 'Vitórias' },
  { key: 'draws', label: 'E', title: 'Empates' },
  { key: 'losses', label: 'D', title: 'Derrotas' },
  { key: 'win_rate', label: '%', title: 'Aproveitamento' },
  { key: 'goals', label: 'Gols', title: 'Gols' },
  { key: 'assists', label: 'Ast', title: 'Assistências' },
  { key: 'yellows', label: '🟨', title: 'Amarelos' },
  { key: 'reds', label: '🟥', title: 'Vermelhos' },
  { key: 'titles', label: '🏆', title: 'Títulos' },
  { key: 'runner_ups', label: '🥈', title: 'Vices' },
]

export function StatsPage() {
  const thisYear = new Date().getFullYear()
  const [year, setYear] = useState<number | null>(null)
  const [tab, setTab] = useState(RANKINGS[0].id)
  const { data, isLoading } = usePlayerStats(year)
  const ranking = RANKINGS.find((r) => r.id === tab)!

  const rows = useMemo(() => {
    const list = (data ?? []).filter(ranking.filter ?? (() => true))
    const sortKey = ranking.sort === 'yellows' ? (s: PlayerStats) => s.reds * 100 + s.yellows : (s: PlayerStats) => Number(s[ranking.sort])
    return [...list].sort(
      (a, b) => sortKey(b) - sortKey(a) || (ranking.tie ? Number(b[ranking.tie]) - Number(a[ranking.tie]) : 0) || a.name.localeCompare(b.name),
    )
  }, [data, ranking])

  // Posição compartilhada em caso de empate no critério principal
  const positions = rows.map((r, i) => {
    let pos = i + 1
    while (pos > 1 && Number(rows[pos - 2][ranking.sort]) === Number(r[ranking.sort]) && Number(rows[pos - 2].reds) === Number(r.reds)) pos--
    return pos
  })

  return (
    <>
      <PageHeader
        title="Estatísticas"
        actions={
          <select className="input w-auto" value={year ?? ''} onChange={(e) => setYear(e.target.value ? Number(e.target.value) : null)} aria-label="Período">
            <option value="">Todos os tempos</option>
            {[thisYear, thisYear - 1, thisYear - 2].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        }
      />
      <div className="mb-4 flex gap-1 overflow-x-auto rounded-lg bg-soft p-1" role="tablist">
        {RANKINGS.map((r) => (
          <button
            key={r.id}
            role="tab"
            aria-selected={tab === r.id}
            onClick={() => setTab(r.id)}
            className={cx('whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium', tab === r.id ? 'bg-surface shadow' : 'text-muted')}
            >
            {r.label}
          </button>
        ))}
      </div>
      {ranking.hint && <p className="mb-2 text-xs text-muted">{ranking.hint}</p>}

      {isLoading ? (
        <Spinner />
      ) : !rows.length ? (
        <EmptyState>Sem dados ainda. As estatísticas aparecem quando houver partidas com súmula.</EmptyState>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th className="px-3 py-2 text-left">#</th>
                <th className="py-2 text-left">Jogador</th>
                {COLUMNS.map((c) => (
                  <th key={c.key} title={c.title} className={cx('px-2 py-2 text-center', c.key === ranking.sort && 'text-primary-ink')}>
                  {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((s, i) => (
                <tr key={s.player_id} className="border-b border-line hover:bg-soft">
                  <td className="px-3 py-1.5 font-semibold">{positions[i] <= 3 ? ['🥇', '🥈', '🥉'][positions[i] - 1] : positions[i]}</td>
                  <td className="py-1.5">
                    <Link to={`/jogadores/${s.player_id}`} className="flex items-center gap-2 hover:underline">
                      <Avatar name={s.name} url={s.photo_url} size={28} type={s.type} />
                      <PlayerName name={s.name} type={s.type} className="font-medium" />
                    </Link>
                  </td>
                  {COLUMNS.map((c) => (
                    <td key={c.key} className={cx('px-2 text-center tabular-nums', c.key === ranking.sort && 'font-bold')}>
                    {c.key === 'win_rate' ? `${s.win_rate.toLocaleString('pt-BR')}%` : String(s[c.key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </>
  )
}
