export type UserRole = 'ADMIN' | 'MESARIO' | 'JOGADOR'
export type UserStatus = 'PENDENTE' | 'ATIVO' | 'BLOQUEADO'
/** ISENTO = goleiro fixo: não paga mensalidade nem diária */
export type PlayerType = 'MENSALISTA' | 'DIARISTA' | 'ISENTO'
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
  /** velocidade 1–5 (só ADMIN vê) */
  speed: number | null
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
  /** valor diferente da mensalidade marcado como quitado (conta como pago) */
  settled: boolean
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
  /** chamada no local; null = ainda não chamado */
  checkin?: 'PRESENTE' | 'FALTOU' | null
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
  /** sigla oficial e escudo (times com nome de clube) */
  abbr?: string | null
  crest_url?: string | null
  players: TeamPlayerItem[]
  line_count: number
  has_fixed_gk: boolean
  has_rotation_gk: boolean
  uses_volunteer_gk: boolean
  /** sem goleiro próprio: usa os goleiros fixos da pelada */
  uses_shared_gk: boolean
  /** médias por jogador de linha (força = nível + velocidade); só vêm para ADMIN */
  level_avg?: number | null
  speed_avg?: number | null
  strength_avg?: number | null
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
  /** sorteio feito com a opção "time com um a menos" */
  allow_short_team: boolean
  /** campeonato usado nos nomes dos times (null = cores) */
  competition?: string | null
  created_at: string
}

export interface RoundDetail extends RoundSummary {
  attendances: AttendanceItem[]
  /** avisaram que não vão; quem não tem registro ainda não respondeu */
  absences: AttendanceItem[]
  my_player_id: number | null
  my_status: 'CONFIRMADO' | 'CANCELADO' | null
  draw: DrawInfo | null
  teams: TeamItem[]
  not_in_teams: { player_id: number; name: string }[]
  /** goleiros fixos sem time: agarram para os times que estiverem em campo */
  shared_goalkeepers: { player_id: number; name: string }[]
  no_longer_confirmed: { player_id: number; name: string }[]
  /** escala de empréstimos depois da chamada (só com campeonato montado) */
  loans?: Loan[]
  /** partidas com time desfalcado e ninguém de fora para emprestar */
  unfilled?: { match_id: number; match_seq: number; match_label: string; missing_names: string[] }[]
}

export interface Loan {
  match_id: number
  match_seq: number
  match_label: string
  finished: boolean
  team_id: number
  team_name: string
  player_id: number
  player_name: string
  from_team_name: string
  replaces_name: string
  /** força média do time com o emprestado − com quem faltou (só ADMIN) */
  strength_delta: number | null
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
  abbr?: string | null
  crest_url?: string | null
}

export interface CatalogCompetition {
  code: string
  name: string
  season: number | null
  clubs: number
  updated_at: string | null
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
  /** quem completa time desfalcado nesta partida (chamada) */
  loans?: { team_id: number; player_id: number; player_name: string; from_team_name: string; replaces_name: string }[]
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

// ---------- Área do jogador ----------
/** out = "F" (fora): não jogou no mês, não é dívida */
export type MyMonthStatus = 'paid' | 'partial' | 'out' | 'open' | 'late' | 'future' | 'none'

export interface MyFinance {
  has_player: boolean
  player_name: string | null
  type: PlayerType | null
  year: number
  monthly_fee: string
  months: { month: string; amount: string | null; marker: string | null; status: MyMonthStatus }[]
  total_paid: string
  months_due: string[]
  amount_due: string
  pix_key: string | null
}

export interface PasswordRequest {
  id: number
  user_id: number
  name: string
  email: string
  phone: string | null
  requested_at: string
  link_sent_at: string | null
}

// ---------- Portal da transparência ----------
export interface TransparencyExpense {
  month: string
  category: CashCategory
  description: string | null
  amount: string
}

export interface Transparency {
  year: number
  months: string[]
  balance: string
  year_income: string
  year_expenses: string
  summary: MonthSummary[]
  expenses: TransparencyExpense[]
  /** situação dos mensalistas ativos mês a mês (chave "YYYY-MM"), sem valores */
  players: { name: string; months: Record<string, MyMonthStatus> }[]
}
