import { useState, type ReactNode } from 'react'
import { Goal, Plus, Trash2 } from 'lucide-react'
import { useConfirm, useToast } from '@/contexts/feedback'
import {
  Alert,
  Avatar,
  Badge,
  Bracket,
  Button,
  Card,
  CardIcon,
  EmptyState,
  ErrorState,
  Field,
  ICON_STROKE,
  IconButton,
  LiveDot,
  Modal,
  PageHeader,
  PositionBadge,
  ScoreStrip,
  Skeleton,
  SkeletonList,
  StandingsTable,
  Stopwatch,
  TeamShield,
  type BracketMatch,
  type StandingsRow,
} from '@/components/ui'
import { useTheme } from '@/theme/ThemeProvider'

/* Vitrine do design system (Etapa 1). Os dados abaixo são amostras só para visualizar os componentes. */

const TEAMS = [
  { name: 'Verde', color: '#1f9d55' },
  { name: 'Azul', color: '#2f6fdb' },
  { name: 'Vermelho', color: '#e0443a' },
  { name: 'Amarelo', color: '#f4c20d' },
  { name: 'Preto', color: '#1f2937' },
  { name: 'Branco', color: '#e5e7eb' },
  { name: 'Laranja', color: '#ea580c' },
  { name: 'Roxo', color: '#7c3aed' },
]
const [VRD, AZL, VRM, AMA] = TEAMS

const TOKENS: { name: string; cls: string; use: string }[] = [
  { name: 'bg', cls: 'bg-bg', use: 'fundo' },
  { name: 'surface', cls: 'bg-surface', use: 'superfícies' },
  { name: 'soft', cls: 'bg-soft', use: 'chips, trilhas, skeleton' },
  { name: 'ink', cls: 'bg-ink', use: 'texto' },
  { name: 'muted', cls: 'bg-muted', use: 'texto secundário' },
  { name: 'line', cls: 'bg-line', use: 'bordas, linhas de campo' },
  { name: 'primary', cls: 'bg-primary', use: 'gramado · ativo · pago' },
  { name: 'accent', cls: 'bg-accent', use: 'azul refletor · destaque · gol' },
  { name: 'danger', cls: 'bg-danger', use: 'erro · exclusão · saída' },
  { name: 'board', cls: 'bg-board', use: 'bloco do placar (sempre escuro)' },
  { name: 'card-yellow', cls: 'bg-card-yellow', use: 'só cartão amarelo' },
  { name: 'card-red', cls: 'bg-card-red', use: 'só cartão vermelho' },
]

const STANDINGS: StandingsRow[] = [
  { position: 1, team: { id: 1, ...VRD }, played: 3, wins: 2, draws: 1, losses: 0, goals_for: 6, goals_against: 2, goal_diff: 4, points: 7 },
  { position: 2, team: { id: 2, ...AZL }, played: 3, wins: 2, draws: 0, losses: 1, goals_for: 5, goals_against: 4, goal_diff: 1, points: 6, tiebreak_note: 'saldo de gols' },
  { position: 3, team: { id: 3, ...VRM }, played: 3, wins: 1, draws: 1, losses: 1, goals_for: 4, goals_against: 4, goal_diff: 0, points: 4 },
  { position: 4, team: { id: 4, ...AMA }, played: 3, wins: 0, draws: 0, losses: 3, goals_for: 1, goals_against: 6, goal_diff: -5, points: 0 },
]

const SEMIS: BracketMatch[] = [
  { id: 1, code: 'SF1', title: 'Semifinal 1', home: VRD, away: VRM, homeLabel: '', awayLabel: '', homeScore: 2, awayScore: 1, winnerSide: 'home' },
  { id: 2, code: 'SF2', title: 'Semifinal 2', home: AZL, away: AMA, homeLabel: '', awayLabel: '', homeScore: 1, awayScore: 1, homePens: 4, awayPens: 3, winnerSide: 'home' },
]
const FINAL: BracketMatch = { id: 3, code: 'F', title: 'Final', home: VRD, away: AZL, homeLabel: '', awayLabel: '', homeScore: null, awayScore: null }

function Section({ title, children, note }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="font-display text-2xl font-bold">{title}</h2>
      {note && <p className="mb-3 max-w-2xl text-sm text-muted">{note}</p>}
      <div className={note ? '' : 'mt-3'}>{children}</div>
    </section>
  )
}

export default function DesignSystemPage() {
  const { theme, setTheme } = useTheme()
  const toast = useToast()
  const confirm = useConfirm()
  const [sheet, setSheet] = useState(false)
  const [score, setScore] = useState<[number, number]>([2, 1])
  const [name, setName] = useState('')

  return (
    <>
      <PageHeader
        title="Design system"
        subtitle="Etapa 1 do redesign — tokens, tipografia e componentes base"
        actions={
          <div className="flex rounded-full bg-soft p-1 text-sm" role="tablist" aria-label="Tema">
            {(['dark', 'light'] as const).map((t) => (
              <button key={t} role="tab" aria-selected={theme === t} onClick={() => setTheme(t)} className={`press min-h-[40px] rounded-full px-4 font-medium ${theme === t ? 'bg-surface text-ink shadow-card' : 'text-muted'}`}>
                {t === 'dark' ? 'Escuro' : 'Claro'}
              </button>
            ))}
          </div>
        }
      />

      <Section title="Placar" note="Elemento-assinatura: tarja de transmissão com canto chanfrado. O bloco do placar é sempre escuro, nos dois temas.">
        <div className="space-y-3">
          <ScoreStrip size="xl" home={VRD} away={AZL} homeScore={score[0]} awayScore={score[1]} center={<LiveDot label="2º tempo" />} live />
          <div className="flex flex-wrap gap-2">
            <Button variant="accent" size="xl" onClick={() => { setScore(([h, a]) => [h + 1, a]); toast({ message: 'Gol do Verde', tone: 'success', action: { label: 'Desfazer', onClick: () => setScore(([h, a]) => [Math.max(0, h - 1), a]) } }) }}>
              <Goal size={22} strokeWidth={ICON_STROKE} aria-hidden /> Gol Verde
            </Button>
            <Button variant="secondary" size="xl" onClick={() => { setScore(([h, a]) => [h, a + 1]); toast({ message: 'Gol do Azul', tone: 'success', action: { label: 'Desfazer', onClick: () => setScore(([h, a]) => [h, Math.max(0, a - 1)]) } }) }}>
              Gol Azul
            </Button>
          </div>
          <ScoreStrip size="lg" home={VRM} away={AMA} homeScore={0} awayScore={3} winnerSide="away" center="FIM" />
          <ScoreStrip size="md" home={VRD} away={null} awayLabel="Vencedor 2º × 3º" homeScore={null} awayScore={null} center="12:30" />
          <ScoreStrip size="sm" home={AZL} away={VRD} homeScore={1} awayScore={1} center={<span className="text-[11px]">pên. 4–3</span>} winnerSide="home" />
        </div>
      </Section>

      <Section title="Cronômetro" note="Local, no aparelho do mesário: iniciar, pausar e encerrar (mostra o tempo total). Não encerra sozinho — as pausas da pelada são imprevisíveis.">
        <Card className="pitch-lines p-6">
          <Stopwatch id="design-demo" plannedSeconds={480} size="xl" />
        </Card>
      </Section>

      <Section title="Cores" note="Amarelo e vermelho são exclusivos dos cartões. Erros, exclusões e saídas usam magenta.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {TOKENS.map((t) => (
            <div key={t.name} className="card overflow-hidden">
              <div className={`h-14 ${t.cls}`} />
              <div className="p-3">
                <p className="font-display text-lg font-semibold">{t.name}</p>
                <p className="text-xs text-muted">{t.use}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Tipografia" note="Barlow Condensed para títulos, placares e números (sempre tabular); Inter para texto e tabelas.">
        <Card className="space-y-2 p-5">
          <p className="tabular font-display text-score-xl">3 × 2</p>
          <p className="font-display text-score font-extrabold">08:00</p>
          <p className="font-display text-4xl font-bold">Rodada de quarta, 21 de outubro</p>
          <p className="font-display text-2xl font-semibold">Classificação do grupo</p>
          <p className="text-base">Texto corrido em Inter 16px, para descrições e formulários.</p>
          <p className="text-sm text-muted">Texto secundário em 14px.</p>
          <p className="text-xs text-muted">Legenda em 12px.</p>
        </Card>
      </Section>

      <Section title="Times">
        <div className="flex flex-wrap gap-4">
          {TEAMS.map((t) => (
            <div key={t.name} className="flex flex-col items-center gap-1">
              <TeamShield name={t.name} color={t.color} size={44} />
              <span className="text-xs text-muted">{t.name}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Botões">
        <div className="flex flex-wrap items-center gap-2">
          <Button>Confirmar presença</Button>
          <Button variant="accent">Sortear times</Button>
          <Button variant="secondary">Cancelar</Button>
          <Button variant="ghost">Ver todos</Button>
          <Button variant="danger"><Trash2 size={16} strokeWidth={ICON_STROKE} aria-hidden /> Excluir</Button>
          <Button loading>Salvando</Button>
          <Button disabled>Indisponível</Button>
          <IconButton label="Adicionar"><Plus size={18} strokeWidth={ICON_STROKE} /></IconButton>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm">sm 44px</Button>
          <Button size="md">md 44px</Button>
          <Button size="lg">lg 48px</Button>
          <Button size="xl">XL 56px</Button>
        </div>
      </Section>

      <Section title="Badges, posições e cartões">
        <div className="flex flex-wrap items-center gap-2">
          <PositionBadge position="ZAGUEIRO" />
          <PositionBadge position="ALA" />
          <PositionBadge position="ATACANTE" />
          <PositionBadge position="GOLEIRO_FIXO" />
          <PositionBadge position={null} />
          <Badge color="green">Pago</Badge>
          <Badge color="blue">Mensalista</Badge>
          <Badge color="yellow">Coringa</Badge>
          <Badge color="red">Atrasado</Badge>
          <Badge>Diarista</Badge>
          <LiveDot />
          <span className="flex items-center gap-1 text-sm"><CardIcon color="yellow" /> amarelo</span>
          <span className="flex items-center gap-1 text-sm"><CardIcon color="red" /> vermelho</span>
          <Avatar name="Beto Lima" />
          <Avatar name="Caio Souza" size={32} />
        </div>
      </Section>

      <Section title="Classificação e chaveamento">
        <div className="grid gap-5 lg:grid-cols-2">
          <Card className="p-2"><StandingsTable rows={STANDINGS} qualify={4} caption="Classificação de exemplo" /></Card>
          <Card className="p-4"><Bracket semis={SEMIS} final={FINAL} /></Card>
        </div>
      </Section>

      <Section title="Formulário" note="Label sempre visível, dica e erro no próprio campo.">
        <Card className="max-w-md space-y-3 p-5">
          <Field label="Nome completo" hint="Como aparece nas súmulas" error={name.length === 1 ? 'Use ao menos 2 letras' : undefined}>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Alert kind="info">Mensagens informativas usam o neutro.</Alert>
          <Alert kind="success">Presença confirmada.</Alert>
          <Alert>E-mail ou senha inválidos.</Alert>
        </Card>
      </Section>

      <Section title="Estados" note="Toda tela terá os 4: carregando, vazio (com o que fazer), erro (com tentar de novo) e sucesso.">
        <div className="grid gap-4 md:grid-cols-3">
          <Card className="p-4"><Skeleton className="mb-3 h-8 w-2/3" /><SkeletonList rows={3} /></Card>
          <Card><EmptyState title="Nenhuma rodada ainda" action={<Button size="sm"><Plus size={16} strokeWidth={ICON_STROKE} aria-hidden /> Criar rodada</Button>}>Crie a rodada da quarta para abrir a lista de presença.</EmptyState></Card>
          <Card><ErrorState error={new Error('x')} onRetry={() => toast({ message: 'Tentando de novo…' })} /></Card>
        </div>
      </Section>

      <Section title="Sheet, confirmação e toast">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => setSheet(true)}>Abrir sheet</Button>
          <Button variant="secondary" onClick={async () => toast(await confirm({ title: 'Excluir esta rodada?', description: 'Presenças e sorteios desta rodada serão apagados.', confirmLabel: 'Excluir rodada', danger: true }) ? { message: 'Rodada excluída', tone: 'success' } : 'Nada foi excluído')}>
            Confirmação
          </Button>
          <Button variant="secondary" onClick={() => toast({ message: 'Não foi possível salvar', tone: 'error' })}>Toast de erro</Button>
        </div>
        <Modal open={sheet} onClose={() => setSheet(false)} title="Quem fez o gol?" footer={<Button className="w-full" variant="secondary" onClick={() => setSheet(false)}>Cancelar</Button>}>
          <div className="grid gap-2">
            {['Beto', 'Caio', 'Duda', 'Edu'].map((n, i) => (
              <button key={n} onClick={() => setSheet(false)} className="press flex min-h-[56px] items-center gap-3 rounded-btn border border-line px-3 text-left text-lg font-medium hover:bg-soft">
                <PositionBadge position={['ZAGUEIRO', 'ALA', 'ATACANTE', 'ALA'][i]} /> {n}
              </button>
            ))}
          </div>
        </Modal>
      </Section>
    </>
  )
}
