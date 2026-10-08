import { TeamShield } from './TeamShield'
import { cx } from './cx'

export interface StandingsRow {
  position: number
  team: { id: number; name: string; color?: string | null; crest_url?: string | null }
  played: number
  wins: number
  draws: number
  losses: number
  goals_for: number
  goals_against: number
  goal_diff: number
  points: number
  tiebreak_note?: string | null
}

const COLS: { key: keyof StandingsRow; label: string; title: string; mobile?: boolean }[] = [
  { key: 'points', label: 'P', title: 'Pontos', mobile: true },
  { key: 'played', label: 'J', title: 'Jogos', mobile: true },
  { key: 'wins', label: 'V', title: 'Vitórias' },
  { key: 'draws', label: 'E', title: 'Empates' },
  { key: 'losses', label: 'D', title: 'Derrotas' },
  { key: 'goals_for', label: 'GP', title: 'Gols pró' },
  { key: 'goals_against', label: 'GC', title: 'Gols contra' },
  { key: 'goal_diff', label: 'SG', title: 'Saldo de gols', mobile: true },
]

/**
 * Tabela de classificação. Quem avança (posição ≤ `qualify`) ganha a barra de gramado.
 * No celular mostra P, J e SG; a primeira coluna fica fixa se houver rolagem.
 */
export function StandingsTable({ rows, qualify = 0, caption }: { rows: StandingsRow[]; qualify?: number; caption?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            <th scope="col" className="sticky left-0 bg-surface py-2 pl-3 pr-2 text-left font-medium">Time</th>
            {COLS.map((c) => (
              <th key={c.key} scope="col" title={c.title} className={cx('px-2 py-2 text-center font-medium', !c.mobile && 'hidden sm:table-cell', c.key === 'points' && 'text-ink')}>
                <abbr title={c.title} className="no-underline">{c.label}</abbr>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const advances = r.position <= qualify
            return (
              <tr key={r.team.id} className="border-b border-line last:border-0">
                <th scope="row" className="sticky left-0 bg-surface py-2 pl-0 pr-2 text-left font-medium">
                  <span className="flex items-center gap-2">
                    <span className={cx('h-8 w-1 shrink-0', advances ? 'bg-primary' : 'bg-transparent')} aria-hidden />
                    <span className="tabular w-5 text-right font-display text-lg font-bold text-muted">{r.position}</span>
                    <TeamShield name={r.team.name} color={r.team.color} size={22} crestUrl={r.team.crest_url} />
                    <span className="min-w-0">
                      <span className="block truncate">{r.team.name}</span>
                      {r.tiebreak_note && <span className="block text-[11px] font-normal text-muted">desempate: {r.tiebreak_note}</span>}
                    </span>
                    {advances && <span className="sr-only">(classificado)</span>}
                  </span>
                </th>
                {COLS.map((c) => (
                  <td key={c.key} className={cx('tabular px-2 text-center', !c.mobile && 'hidden sm:table-cell', c.key === 'points' && 'font-display text-lg font-bold')}>
                    {c.key === 'goal_diff' && r.goal_diff > 0 ? `+${r.goal_diff}` : String(r[c.key])}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
      {qualify > 0 && (
        <p className="mt-2 flex items-center gap-2 px-3 text-xs text-muted">
          <span className="h-3 w-1 bg-primary" aria-hidden /> Avança para o mata-mata
        </p>
      )}
    </div>
  )
}
