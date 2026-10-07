import type { MatchItem, PlayerStats, TeamItem, Tournament, TournamentSummary } from '@/api/types'

/** Abre a escolha de conversa/grupo: compartilhamento nativo do celular ou, no computador, o WhatsApp. */
export async function shareText(text: string): Promise<void> {
  if (navigator.share) {
    try {
      await navigator.share({ text })
      return
    } catch (err) {
      if ((err as DOMException)?.name === 'AbortError') return // cancelou
    }
  }
  window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank', 'noopener,noreferrer')
}

const dayMonth = (iso: string) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`

export function teamsText(date: string, teams: TeamItem[]): string {
  const lines = [`⚽ *Times da pelada de ${dayMonth(date)}*`, '']
  for (const t of teams) {
    lines.push(`*Time ${t.name}*`)
    for (const p of t.players) lines.push(`${p.role === 'GOLEIRO_FIXO' ? '🧤' : '•'} ${p.name}`)
    lines.push('')
  }
  return lines.join('\n').trim()
}

const score = (m: MatchItem) => {
  const pens = m.home_penalties != null ? ` (pên. ${m.home_penalties}–${m.away_penalties})` : ''
  return `${m.home?.name ?? m.home_label} ${m.home_score} × ${m.away_score} ${m.away?.name ?? m.away_label}${pens}`
}

export function resultText(t: Tournament, summary: TournamentSummary | undefined, title: (m: MatchItem) => string): string {
  const done = t.matches.filter((m) => m.status === 'ENCERRADA')
  const lines = [`🏆 *${t.champion ? 'Resultado' : 'Parcial'} da pelada de ${dayMonth(t.round_date)}*`, `_${t.format_name}_`, '']
  if (t.champion) {
    lines.push(`🥇 Campeão: *Time ${t.champion.name}*`)
    if (t.runner_up) lines.push(`🥈 Vice: Time ${t.runner_up.name}`)
    lines.push('')
  }
  if (done.length) {
    lines.push('*Jogos*')
    for (const m of done) lines.push(`${title(m)}: ${score(m)}`)
    lines.push('')
  }
  if (summary?.top_scorers.length) {
    const gols = summary.top_scorers[0].goals
    lines.push(`⚽ Artilharia: ${summary.top_scorers.map((s) => s.name).join(', ')} (${gols} gol${gols > 1 ? 's' : ''})`)
  }
  return lines.join('\n').trim()
}

export function statsText(rankingLabel: string, period: string, rows: PlayerStats[], value: (s: PlayerStats) => string): string {
  const medals = ['🥇', '🥈', '🥉']
  const lines = [`📊 *${rankingLabel}* — ${period}`, '']
  rows.slice(0, 5).forEach((s, i) => lines.push(`${medals[i] ?? `${i + 1}º`} ${s.name} — ${value(s)}`))
  return lines.join('\n').trim()
}

