import { Trophy } from 'lucide-react'
import { ScoreStrip, type StripTeam } from './ScoreStrip'
import { ICON_STROKE } from './cx'

export interface BracketMatch {
  id: number
  code: string
  title: string
  home: StripTeam | null
  away: StripTeam | null
  homeLabel: string
  awayLabel: string
  homeScore: number | null
  awayScore: number | null
  homePens?: number | null
  awayPens?: number | null
  winnerSide?: 'home' | 'away' | null
}

function Slot({ m }: { m: BracketMatch }) {
  return (
    <div className="w-full min-w-0 max-w-sm">
      <p className="mb-1 flex items-center gap-1.5 font-display text-sm font-semibold text-muted">
        {m.code === 'F' && <Trophy size={14} strokeWidth={ICON_STROKE} aria-hidden />}
        {m.title}
      </p>
      <ScoreStrip
        size="sm"
        home={m.home}
        away={m.away}
        homeLabel={m.homeLabel}
        awayLabel={m.awayLabel}
        homeScore={m.homeScore}
        awayScore={m.awayScore}
        winnerSide={m.winnerSide}
        center={m.homePens != null ? <span className="text-[11px]">pên. {m.homePens}–{m.awayPens}</span> : undefined}
      />
    </div>
  )
}

/** Chaveamento: coluna de semifinais (ou 2º×3º) → final. Empilha no celular. */
export function Bracket({ semis, final }: { semis: BracketMatch[]; final: BracketMatch }) {
  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-center">
      {semis.length > 0 && (
        <div className="flex flex-1 flex-col gap-4">
          {semis.map((m) => <Slot key={m.id} m={m} />)}
        </div>
      )}
      {semis.length > 0 && (
        <div className="hidden w-8 self-stretch md:flex md:flex-col md:justify-center" aria-hidden>
          <div className="h-1/2 border-y-2 border-r-2 border-line" />
        </div>
      )}
      <div className="flex-1">
        <Slot m={final} />
      </div>
    </div>
  )
}
