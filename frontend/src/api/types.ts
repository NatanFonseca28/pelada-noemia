export type UserRole = 'ADMIN' | 'MESARIO' | 'JOGADOR'
export type UserStatus = 'PENDENTE' | 'ATIVO' | 'BLOQUEADO'
export type PlayerType = 'MENSALISTA' | 'DIARISTA'
export type Position = 'ZAGUEIRO' | 'ALA' | 'ATACANTE' | 'GOLEIRO_FIXO'
export type Tiebreaker = 'PONTOS' | 'SALDO_GOLS' | 'GOLS_PRO' | 'CONFRONTO_DIRETO' | 'SORTEIO'
export type KnockoutTieRule = 'PENALTIS' | 'MELHOR_CAMPANHA' | 'GOL_DE_OURO'
export type RedCardRule = 'NENHUMA' | 'PROXIMA_PARTIDA' | 'RESTO_CAMPEONATO'
export type TopScorerTiebreak = 'DIVIDIDA' | 'MAIS_ASSISTENCIAS' | 'MENOS_JOGOS' | 'SORTEIO'

export interface User {
  id: number
  email: string
  name: string
  role: UserRole
  status: UserStatus
  player_id: number | null
  approved_at: string | null
  created_at: string
  /** senha definida/redefinida pelo admin: precisa trocar antes de usar o sistema */
  must_change_password?: boolean
  /** celular informado no cadastro (E.164) */
  phone?: string | null
  /** define a visibilidade das páginas; único que vê auditoria, log de acessos e design system */
  is_superadmin?: boolean
  /** páginas ocultas para a categoria do usuário logado (só em /auth/me e no login) */
  hidden_pages?: string[]
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface Player {
  id: number
  name: string
  nickname: string | null
  display_name: string
  type: PlayerType
  /** null = posição a definir (jogador importado da planilha) */
  primary_position: Position | null
  secondary_position: Position | null
  skill_level: number | null
  active: boolean
  photo_url: string | null
  /** contato em E.164 (+5521987654321) — só vem preenchido para ADMIN */
  phone: string | null
  /** consentimento para cobrança por WhatsApp (LGPD) */
  whatsapp_opt_in: boolean
}

export type PlayerInput = Omit<Player, 'id' | 'display_name' | 'photo_url'>

export interface Settings {
  weekday: number
  start_time: string
  total_minutes: number
  line_players_per_team: number
  balance_by_skill: boolean
  extra_team_threshold: number
  changeover_minutes: number
  group_match_minutes: number
  final_weight: string
  points_win: number
  points_draw: number
  points_loss: number
  tiebreakers: Tiebreaker[]
  knockout_tie_rule: KnockoutTieRule
  top_scorer_tiebreak: TopScorerTiebreak
  casual_goal_limit: number
  casual_match_minutes: number
  red_card_rule: RedCardRule
  two_yellows_red: boolean
}

export interface AuditLog {
  id: number
  user_id: number | null
  user_name: string | null
  action: string
  entity: string
  entity_id: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  created_at: string
}

// ---------- Financeiro ----------
export type CashKind = 'ENTRADA' | 'SAIDA'
export type CashCategory = 'DIARISTAS_COLETE' | 'CAMPO' | 'DIVERSOS' | 'OUTROS'

export interface FinanceConfig {
  monthly_fee: string
  finance_opening_balance: string
  finance_opening_month: string | null
}

export interface FeeCell {
  amount: string | null
  marker: string | null
}

export interface FeeRow {
  player_id: number
  name: string
  type: PlayerType
  active: boolean
  cells: Record<string, FeeCell>
  total: string
  /** mensalista ativo sem pagar o mês atual nem o anterior */
  delinquent: boolean
  months_due: string[]
}

export interface MonthSummary {
  month: string
  fees: string
  income: string
  expenses: string
  net: string
  paid_count: number
}

export interface FinanceOverview {
  year: number
  months: string[]
  rows: FeeRow[]
  summary: MonthSummary[]
  config: FinanceConfig
  balance: string
  year_total: string
  /** [anterior, atual] usados na regra de inadimplência */
  reference_months: string[]
  delinquent_count: number
  /** devem pelo menos 1 dos 2 meses de referência ("Para cobrar") */
  to_charge_count: number
}

export interface Delinquent {
  player_id: number
  name: string
  phone: string | null
  whatsapp_opt_in: boolean
  /** só os meses em aberto */
  months_due: string[]
  amount_due: string
  /** deve os 2 meses (inadimplente) ou só 1 */
  delinquent: boolean
  /** última cobrança registrada (por qualquer administrador) */
  last_charged_at: string | null
  last_charged_by: string | null
}

export interface ChargeMessage {
  message: string
  pix_key: string | null
  is_default: boolean
  default_message: string
  variables: { name: string; description: string }[]
}

export interface CashEntry {
  id: number
  month: string
  kind: CashKind
  category: CashCategory
  description: string | null
  amount: string
}

export interface CollectionItem {
  id: number
  name: string
  player_id: number | null
  amount: string
  paid: boolean
}

export interface Collection {
  id: number
  title: string
  amount_per_person: string
  items: CollectionItem[]
}

export interface ImportResult {
  players_created: string[]
  players_matched: string[]
  fee_cells: number
  cash_entries: number
  collections: number
  opening_balance: string | null
  opening_month: string | null
}

// ---------- Rodadas e sorteio ----------
export type RoundStatus = 'ABERTA' | 'FECHADA' | 'TIMES_TRAVADOS' | 'ENCERRADA'
export type TeamRole = 'LINHA' | 'GOLEIRO_FIXO' | 'REVEZAMENTO'

export interface RoundSummary {
  id: number
  date: string
  status: RoundStatus
  notes: string | null
  confirmed_count: number
  has_teams: boolean
  tournament_id: number | null
}

export interface AttendanceItem {
  player_id: number
  name: string
  type: PlayerType
  primary_position: Position | null
  source: 'APP' | 'ADMIN'
  updated_at: string
}

export interface TeamPlayerItem {
  player_id: number
  name: string
  photo_url: string | null
  position: string
  role: TeamRole
  filled_by: 'PRIMARIA' | 'SECUNDARIA' | 'SEM_POSICAO' | 'QUALQUER'
  moved_manually: boolean
}

export interface TeamItem {
  id: number
  name: string
  color: string
  players: TeamPlayerItem[]
  line_count: number
  has_fixed_gk: boolean
  has_rotation_gk: boolean
  uses_volunteer_gk: boolean
}

export interface DrawAlternative {
  num_teams: number
  line_sizes: number[]
  mode: 'PELADA_NORMAL' | 'CAMPEONATO'
  description: string
}

export interface DrawSubstitution {
  player_id: number
  name: string
  team_index: number
  position: string
  filled_by: string
}

export interface DrawInfo {
  id: number
  seed: number
  mode: 'PELADA_NORMAL' | 'CAMPEONATO'
  num_teams: number
  warnings: string[]
  infos: string[]
  substitutions: DrawSubstitution[]
  alternatives: DrawAlternative[]
  created_at: string
}

export interface RoundDetail extends RoundSummary {
  attendances: AttendanceItem[]
  my_player_id: number | null
  my_status: 'CONFIRMADO' | 'CANCELADO' | null
  draw: DrawInfo | null
  teams: TeamItem[]
  not_in_teams: { player_id: number; name: string }[]
  no_longer_confirmed: { player_id: number; name: string }[]
}

// ---------- Campeonato ----------
export interface FormatOption {
  code: string
  legs: number
  knockout_seconds: number | null
  recommended: boolean
  name: string
  description: string
  total_matches: number
  match_seconds: number
  final_seconds: number | null
  feasible: boolean
  note: string | null
  groups: Record<string, number[]>
}

export interface FormatsResponse {
  num_teams: number
  total_minutes: number
  changeover_minutes: number
  group_match_minutes: number
  final_weight: string
  options: FormatOption[]
}

export interface TeamRef {
  id: number
  name: string
  color: string
}

export interface StandingRow {
  position: number
  team: TeamRef
  played: number
  wins: number
  draws: number
  losses: number
  goals_for: number
  goals_against: number
  goal_diff: number
  points: number
  tiebreak_note: string | null
}

export interface MatchItem {
  id: number
  seq: number
  code: string
  stage: 'GRUPO' | 'SEMIFINAL' | 'FINAL' | 'AMISTOSO'
  leg: number
  group: string | null
  home: TeamRef | null
  away: TeamRef | null
  home_label: string
  away_label: string
  planned_seconds: number
  goal_limit: number | null
  status: 'AGENDADA' | 'EM_ANDAMENTO' | 'PAUSADA' | 'ENCERRADA'
  home_score: number
  away_score: number
  home_penalties: number | null
  away_penalties: number | null
  winner_team_id: number | null
  /** quem começa com a bola: grupos divididos igualmente; mata-mata = melhor campanha */
  kickoff_team_id: number | null
  /** tempo da partida medido pelo cronômetro do mesário (opcional) */
  started_at: string | null
  ended_at: string | null
  /** segundos jogados, sem pausas */
  elapsed_before_pause: number
  version: number
}

export interface Tournament {
  id: number
  round_id: number
  round_date: string
  format_code: string
  format_name: string
  legs: number
  status: 'EM_ANDAMENTO' | 'ENCERRADO'
  match_seconds: number
  knockout_seconds: number | null
  final_seconds: number | null
  config: { knockout_tie_rule: string; tiebreakers: string[]; final_weight: string; changeover_minutes: number }
  teams: TeamRef[]
  groups: { name: string; complete: boolean; standings: StandingRow[] }[]
  matches: MatchItem[]
  next_match_id: number | null
  champion: TeamRef | null
  runner_up: TeamRef | null
  finished_at: string | null
}

// ---------- Súmula e estatísticas ----------
export type EventType = 'GOL' | 'GOL_CONTRA' | 'AMARELO' | 'VERMELHO'

export interface MatchEventItem {
  id: number
  client_event_id: string
  type: EventType
  team_id: number
  player_id: number | null
  player_name: string | null
  assist_player_id: number | null
  assist_name: string | null
  minute: number | null
  second: number | null
  created_at: string
}

export interface MatchSheet {
  match_id: number
  status: string
  home_team_id: number | null
  away_team_id: number | null
  home_score: number
  away_score: number
  events: MatchEventItem[]
  rosters: Record<string, { player_id: number; name: string; role: string }[]>
}

export interface PlayerStats {
  player_id: number
  name: string
  photo_url: string | null
  type: PlayerType
  primary_position: Position | null
  presences: number
  matches: number
  wins: number
  draws: number
  losses: number
  win_rate: number
  goals: number
  own_goals: number
  assists: number
  yellows: number
  reds: number
  titles: number
  runner_ups: number
}

export interface RoundHistory {
  round_id: number
  date: string
  tournament_id: number | null
  team_name: string | null
  team_color: string | null
  matches: number
  wins: number
  draws: number
  losses: number
  goals: number
  assists: number
  yellows: number
  reds: number
  champion: boolean
  runner_up: boolean
}

export interface ScorerItem {
  player_id: number
  name: string
  team_name: string | null
  team_color: string | null
  goals: number
  assists: number
  matches: number
}

export interface TournamentSummary {
  tournament_id: number
  top_scorers: ScorerItem[]
  tiebreak: string
  scorers: ScorerItem[]
  cards: { player_id: number; name: string; yellows: number; reds: number }[]
  total_goals: number
  total_yellows: number
  total_reds: number
}

// ---------- Dashboard (gestão) ----------
export interface DashboardHighlight {
  player_id: number
  name: string
  value: string
}

export interface Dashboard {
  squad: { monthly_active: number; daily_active: number; inactive: number }
  finance: {
    balance: string
    month: string
    month_income: string
    month_expenses: string
    monthly_paid: number
    monthly_total: number
    delinquent_count: number
    delinquent_amount: string
    reference_months: string[]
    collections_open: string
  }
  current_round: {
    id: number
    date: string
    status: RoundStatus
    confirmed: number
    goalkeepers: number
    teams: number
    tournament_id: number | null
  } | null
  season: {
    year: number
    rounds_played: number
    avg_players: number
    goals: number
    last_champion: string | null
    last_champion_date: string | null
    last_tournament_id: number | null
    top_scorer: DashboardHighlight | null
    most_present: DashboardHighlight | null
    best_win_rate: DashboardHighlight | null
  }
  pending: {
    pending_users: number
    players_without_position: number
    monthly_without_whatsapp: number
    monthly_without_consent: number
    locked_accounts: number
  }
}

// ---------- Superadmin ----------
export interface PageVisibility {
  pages: { path: string; label: string }[]
  hidden: Record<UserRole, string[]>
}

export type AccessEvent = 'LOGIN' | 'LOGIN_FALHOU' | 'BLOQUEADO' | 'CONTA_BLOQUEADA' | 'LOGOUT'

export interface AccessLogEntry {
  id: number
  user_id: number | null
  user_name: string | null
  email: string
  event: AccessEvent
  ip: string | null
  user_agent: string | null
  created_at: string
}
