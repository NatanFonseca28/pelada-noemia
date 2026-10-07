import type { CashCategory, KnockoutTieRule, PlayerType, Position, RedCardRule, Tiebreaker, TopScorerTiebreak, UserRole, UserStatus } from '@/api/types'

export const positionLabel: Record<Position, string> = {
  ZAGUEIRO: 'Zagueiro',
  ALA: 'Ala',
  ATACANTE: 'Atacante',
  GOLEIRO_FIXO: 'Goleiro fixo',
}
export const positionShort: Record<Position, string> = { ZAGUEIRO: 'ZAG', ALA: 'ALA', ATACANTE: 'ATA', GOLEIRO_FIXO: 'GOL' }
export const playerTypeLabel: Record<PlayerType, string> = { MENSALISTA: 'Mensalista', DIARISTA: 'Diarista', ISENTO: 'Isento' }
export const roleLabel: Record<UserRole, string> = { ADMIN: 'Administrador', MESARIO: 'Mesário', JOGADOR: 'Jogador' }
export const statusLabel: Record<UserStatus, string> = { PENDENTE: 'Pendente', ATIVO: 'Ativo', BLOQUEADO: 'Bloqueado' }
export const tiebreakerLabel: Record<Tiebreaker, string> = {
  PONTOS: 'Pontos',
  SALDO_GOLS: 'Saldo de gols',
  GOLS_PRO: 'Gols pró',
  CONFRONTO_DIRETO: 'Confronto direto',
  SORTEIO: 'Sorteio',
}
export const knockoutTieLabel: Record<KnockoutTieRule, string> = {
  PENALTIS: 'Pênaltis',
  MELHOR_CAMPANHA: 'Melhor campanha avança',
  GOL_DE_OURO: 'Gol de ouro',
}
export const redCardLabel: Record<RedCardRule, string> = {
  NENHUMA: 'Sem suspensão',
  PROXIMA_PARTIDA: 'Suspenso da próxima partida',
  RESTO_CAMPEONATO: 'Suspenso do resto do campeonato',
}
export const topScorerLabel: Record<TopScorerTiebreak, string> = {
  DIVIDIDA: 'Artilharia dividida',
  MAIS_ASSISTENCIAS: 'Mais assistências',
  MENOS_JOGOS: 'Menos jogos',
  SORTEIO: 'Sorteio',
}
export const weekdayLabel = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']

export const entityLabel: Record<string, string> = {
  user: 'Usuário',
  player: 'Jogador',
  settings: 'Configurações',
  finance: 'Financeiro (importação)',
  finance_config: 'Config. financeira',
  monthly_fee: 'Mensalidade',
  cash_entry: 'Lançamento de caixa',
  collection: 'Cobrança avulsa',
  collection_item: 'Item de cobrança',
  export: 'Exportação',
  round: 'Rodada',
  tournament: 'Campeonato',
  match: 'Partida',
  match_event: 'Evento da súmula',
}
export const actionLabel: Record<string, string> = {
  CREATE: 'Criou',
  UPDATE: 'Alterou',
  DELETE: 'Excluiu',
  APPROVE: 'Aprovou',
  REJECT: 'Recusou',
  REGISTER: 'Autocadastro',
  CHANGE_PASSWORD: 'Trocou a senha',
  UPDATE_PHOTO: 'Trocou a foto',
  REMOVE_PHOTO: 'Removeu a foto',
  IMPORT: 'Importou',
  EXPORT: 'Exportou',
  DRAW: 'Sorteou os times da',
  MOVE: 'Ajustou os times da',
  ATTENDANCE: 'Alterou presença na',
  OPEN: 'Abriu a lista da',
  CLOSE: 'Fechou a lista da',
  LOCK: 'Travou os times da',
  UNLOCK: 'Destravou os times da',
  RESULT: 'Lançou o resultado da',
  REOPEN: 'Reabriu a',
  FINISH: 'Encerrou o',
}

export const formatDateTime = (iso: string) =>
  new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

export const positionText = (p: Position | null) => (p ? positionLabel[p] : 'Posição a definir')

export const cashCategoryLabel: Record<CashCategory, string> = {
  DIARISTAS_COLETE: 'Diaristas / colete',
  CAMPO: 'Aluguel do campo',
  DIVERSOS: 'Diversos (churrasco, bola, colete)',
  OUTROS: 'Outros',
}

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
export const money = (v: string | number | null | undefined) => (v == null ? '—' : brl.format(Number(v)))

const monthFmt = new Intl.DateTimeFormat('pt-BR', { month: 'short', year: '2-digit', timeZone: 'UTC' })
const monthLongFmt = new Intl.DateTimeFormat('pt-BR', { month: 'long', year: 'numeric', timeZone: 'UTC' })
export const monthShort = (iso: string) => monthFmt.format(new Date(iso + (iso.length === 7 ? '-01' : ''))).replace('.', '')
export const monthLong = (iso: string) => monthLongFmt.format(new Date(iso + (iso.length === 7 ? '-01' : '')))

export const roundStatusLabel: Record<string, string> = {
  ABERTA: 'Lista aberta',
  FECHADA: 'Lista fechada',
  TIMES_TRAVADOS: 'Times travados',
  ENCERRADA: 'Encerrada',
}

export const formatDate = (iso: string) =>
  new Date(iso + 'T12:00:00').toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' })

export const filledByLabel: Record<string, string> = {
  SECUNDARIA: 'pela posição secundária',
  SEM_POSICAO: 'sem posição definida',
  QUALQUER: 'jogador de outra posição',
}

export const slotPositionShort: Record<string, string> = { ZAGUEIRO: 'ZAG', ALA: 'ALA', ATACANTE: 'ATA', GOLEIRO_FIXO: 'GOL' }

export const mmss = (secs: number) => `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`
export const minutesText = (secs: number) => (secs % 60 ? `${mmss(secs)} min` : `${secs / 60} min`)

/** Nome curto do jogo eliminatório pelo código. */
export const knockoutLabel = (code: string) =>
  ({ F: 'Final', R: '2º × 3º', SF1: 'Semifinal 1', SF2: 'Semifinal 2' })[code] ?? code

export const stageLabel: Record<string, string> = {
  GRUPO: 'Fase de grupos',
  SEMIFINAL: 'Semifinal',
  FINAL: 'Final',
  AMISTOSO: 'Partida',
}

export const eventIcon: Record<string, string> = { GOL: '⚽', GOL_CONTRA: '⚽', AMARELO: '🟨', VERMELHO: '🟥' }
export const eventLabel: Record<string, string> = { GOL: 'Gol', GOL_CONTRA: 'Gol contra', AMARELO: 'Cartão amarelo', VERMELHO: 'Cartão vermelho' }

/** Moeda completa (R$ 1.234,56). Mesmo formato do `money`. */
export const formatCurrency = (v: string | number | null | undefined) => money(v)

const brlCompact = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', notation: 'compact', maximumFractionDigits: 1 })
/** Moeda compacta para eixos: R$ 1,2 mil. */
export const formatCurrencyCompact = (v: number) => brlCompact.format(v).replace(/\u00a0/g, ' ')

export const monthInitial = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
export const monthAbbr = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
