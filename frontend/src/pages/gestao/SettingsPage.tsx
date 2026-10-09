import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { ApiError } from '@/api/client'
import { useSaveSettings, useSettings } from '@/api/queries'
import { useCompetitions, useSyncCatalog } from '@/api/catalog'
import { useChatbotAdmin, useChatbotStatus } from '@/api/chatbot'
import { usePageAccess } from '@/lib/pages'
import type { KnockoutTieRule, RedCardRule, Settings, Tiebreaker, TopScorerTiebreak } from '@/api/types'
import { Alert, Button, Card, Field, PageHeader, Spinner } from '@/components/ui'
import { knockoutTieLabel, redCardLabel, tiebreakerLabel, topScorerLabel, weekdayLabel } from '@/lib/labels'

const ALL_TIEBREAKERS = Object.keys(tiebreakerLabel) as Tiebreaker[]

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="p-5">
      <h2 className="mb-4 font-semibold">{title}</h2>
      <div className="grid gap-4 sm:grid-cols-2">{children}</div>
    </Card>
  )
}

function NumberInput({ value, onChange, min, max, step }: { value: number | string; onChange: (v: string) => void; min?: number; max?: number; step?: number }) {
  return <input className="input" type="number" inputMode="decimal" min={min} max={max} step={step} value={value} onChange={(e) => onChange(e.target.value)} required />
}

const STATE_LABEL: Record<string, string> = {
  open: 'Conectado',
  connecting: 'Aguardando leitura do QR Code',
  close: 'Desconectado',
  missing: 'Ainda não conectado',
  offline: 'Dormindo ou acordando (plano grátis): tente de novo em 1 minuto',
  unconfigured: 'Não configurado no servidor',
}

/** Superadmin: chatbot de cobrança pelo WhatsApp de um admin (Evolution API, não oficial). */
function ChatbotSection() {
  const status = useChatbotStatus()
  const { connect, disconnect, save } = useChatbotAdmin()
  const [qr, setQr] = useState<string | null>(null)
  const [limit, setLimit] = useState<number | null>(null)
  const s = status.data
  // enquanto o QR está na tela, confere a cada 3 s se o celular já leu
  useEffect(() => {
    if (!qr) return
    const id = setInterval(async () => {
      const r = await status.refetch()
      if (r.data?.state === 'open') setQr(null)
    }, 3000)
    return () => clearInterval(id)
  }, [qr, status])
  if (!s) return <Card className="p-4"><Spinner /></Card>
  const err = connect.error ?? disconnect.error ?? save.error
  const dailyLimit = limit ?? s.daily_limit
  const apply = (enabled: boolean) => save.mutate({ enabled, daily_limit: dailyLimit, owner_user_id: s.owner_user_id })

  return (
    <Card className="p-4">
      <h2 className="mb-1 font-display text-xl font-bold">Chatbot de cobrança</h2>
      <p className="mb-3 text-sm text-muted">
        Envia as cobranças e responde os jogadores (Pix copia e cola, "já paguei", "não vou jogar", falar com o gestor) pelo WhatsApp
        do administrador conectado. A mensagem é a mesma configurada em "Mensagem de cobrança".
      </p>
      <div className="mb-3"><Alert>
        Conexão <strong>não oficial</strong> (como o WhatsApp Web): o WhatsApp pode <strong>bloquear o número</strong>. O chatbot envia com
        intervalo de 25 a 60 s, só para quem aceitou WhatsApp, no máximo 1 cobrança a cada 3 dias por jogador e até o limite diário.
      </Alert></div>
      {err && <div className="mb-3"><Alert>{err instanceof ApiError ? err.message : 'Erro'}</Alert></div>}
      <dl className="mb-3 grid gap-2 text-sm sm:grid-cols-2">
        <div><dt className="text-muted">WhatsApp</dt><dd className="font-medium">{STATE_LABEL[s.state] ?? s.state}{s.owner_name && s.state === 'open' ? ` (${s.owner_name})` : ''}</dd></div>
        <div><dt className="text-muted">Chatbot</dt><dd className="font-medium">{s.enabled ? 'Ligado' : 'Desligado'} · {s.charges_today} cobrança(s) nas últimas 24 h · {s.pending} na fila</dd></div>
      </dl>
      {qr && (
        <div className="mb-3 rounded-btn border border-line p-3 text-center">
          <img src={qr} alt="QR Code para conectar o WhatsApp" className="mx-auto h-56 w-56 bg-white p-2" />
          <p className="mt-2 text-sm text-muted">No celular do administrador: WhatsApp → Aparelhos conectados → Conectar um aparelho → aponte para o QR Code.</p>
        </div>
      )}
      <div className="flex flex-wrap items-end gap-3">
        {s.state !== 'open' ? (
          <Button type="button" loading={connect.isPending} disabled={s.state === 'unconfigured'} onClick={() => connect.mutate(undefined, { onSuccess: (r) => setQr(r.qr) })}>
            Conectar WhatsApp
          </Button>
        ) : (
          <Button type="button" variant="secondary" loading={disconnect.isPending} onClick={() => confirm('Desconectar o WhatsApp do chatbot?') && disconnect.mutate()}>
            Desconectar
          </Button>
        )}
        <Button type="button" variant={s.enabled ? 'secondary' : 'primary'} loading={save.isPending} onClick={() => apply(!s.enabled)}>
          {s.enabled ? 'Pausar chatbot' : 'Ligar chatbot'}
        </Button>
        <Field label="Limite de cobranças por dia">
          <NumberInput value={dailyLimit} onChange={(v) => setLimit(Number(v))} min={1} max={200} />
        </Field>
        {limit !== null && limit !== s.daily_limit && (
          <Button type="button" variant="secondary" loading={save.isPending} onClick={() => apply(s.enabled)}>Salvar limite</Button>
        )}
      </div>
    </Card>
  )
}

/** Superadmin: catálogo de clubes (football-data.org) usado nos nomes dos times do sorteio. */
function CatalogSection() {
  const list = useCompetitions()
  const sync = useSyncCatalog()
  const [started, setStarted] = useState(false)
  // durante a atualização em segundo plano, recarrega a lista a cada 10 s
  useEffect(() => {
    if (!started) return
    const id = setInterval(() => list.refetch(), 10_000)
    const stop = setTimeout(() => setStarted(false), 150_000)
    return () => { clearInterval(id); clearTimeout(stop) }
  }, [started, list])
  return (
    <Card className="p-4">
      <h2 className="mb-1 font-display text-xl font-bold">Campeonatos do sorteio</h2>
      <p className="mb-3 text-sm text-muted">
        Clubes e escudos do football-data.org, usados para dar nomes de times reais no sorteio. Atualize uma vez por temporada.
      </p>
      {sync.error && <div className="mb-3"><Alert>{sync.error instanceof ApiError ? sync.error.message : 'Erro ao atualizar'}</Alert></div>}
      {started && <div className="mb-3"><Alert kind="info">Atualizando em segundo plano (cerca de 1 minuto e meio). A lista abaixo se atualiza sozinha.</Alert></div>}
      <div className="mb-3 overflow-x-auto">
        <table className="w-full min-w-[420px] text-sm">
          <thead>
            <tr className="border-b border-line text-left text-xs uppercase text-muted">
              <th className="py-1.5 font-medium">Campeonato</th>
              <th className="py-1.5 font-medium">Temporada</th>
              <th className="py-1.5 text-right font-medium">Times</th>
              <th className="py-1.5 text-right font-medium">Atualizado</th>
            </tr>
          </thead>
          <tbody>
            {(list.data ?? []).map((c) => (
              <tr key={c.code} className="border-b border-line/60 last:border-0">
                <td className="py-1.5">{c.name}</td>
                <td className="py-1.5 tabular">{c.season ?? '—'}</td>
                <td className="py-1.5 text-right tabular">{c.clubs}</td>
                <td className="py-1.5 text-right text-xs text-muted">{c.updated_at ? new Date(c.updated_at).toLocaleString('pt-BR') : '—'}</td>
              </tr>
            ))}
            {list.data?.length === 0 && (
              <tr><td colSpan={4} className="py-3 text-muted">Nenhum campeonato carregado ainda.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <Button type="button" loading={sync.isPending} disabled={started} onClick={() => sync.mutate(undefined, { onSuccess: () => setStarted(true) })}>
        Atualizar do football-data.org
      </Button>
    </Card>
  )
}

export function SettingsPage() {
  const { data, isLoading } = useSettings()
  const save = useSaveSettings()
  const { superadmin } = usePageAccess()
  const [form, setForm] = useState<Settings | null>(null)
  const [msg, setMsg] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)

  useEffect(() => {
    if (data) setForm(data)
  }, [data])

  if (isLoading || !form) return <Spinner />

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setForm({ ...form, [k]: v })
  const num = (k: keyof Settings) => (v: string) => set(k, Number(v) as never)

  const moveTiebreaker = (i: number, dir: -1 | 1) => {
    const list = [...form.tiebreakers]
    ;[list[i], list[i + dir]] = [list[i + dir], list[i]]
    set('tiebreakers', list)
  }
  const toggleTiebreaker = (t: Tiebreaker) =>
    set('tiebreakers', form.tiebreakers.includes(t) ? form.tiebreakers.filter((x) => x !== t) : [...form.tiebreakers, t])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setMsg(null)
    try {
      await save.mutateAsync(form!)
      setMsg({ kind: 'success', text: 'Configurações salvas.' })
    } catch (err) {
      setMsg({ kind: 'error', text: err instanceof ApiError ? err.message : 'Erro ao salvar' })
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5">
      <PageHeader
        title="Configurações da pelada"
        actions={<Button type="submit" loading={save.isPending}>Salvar</Button>}
      />
      {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}

      <Section title="Agenda">
        <Field label="Dia da semana">
          <select className="input" value={form.weekday} onChange={(e) => set('weekday', Number(e.target.value))}>
            {weekdayLabel.map((d, i) => <option key={d} value={i}>{d}</option>)}
          </select>
        </Field>
        <Field label="Horário">
          <input className="input" type="time" value={form.start_time.slice(0, 5)} onChange={(e) => set('start_time', e.target.value)} required />
        </Field>
        <Field label="Duração total (min)">
          <NumberInput value={form.total_minutes} onChange={num('total_minutes')} min={20} max={300} />
        </Field>
        <Field label="Tempo de troca entre partidas (min)">
          <NumberInput value={form.changeover_minutes} onChange={num('changeover_minutes')} min={0} max={15} />
        </Field>
      </Section>

      <Section title="Times e sorteio">
        <Field label="Jogadores de linha por time">
          <NumberInput value={form.line_players_per_team} onChange={num('line_players_per_team')} min={3} max={10} />
        </Field>
        <Field label="Sugerir time extra a partir de">
          <NumberInput value={form.extra_team_threshold} onChange={num('extra_team_threshold')} min={1} max={10} />
        </Field>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" className="h-4 w-4 accent-primary" checked={form.balance_by_skill} onChange={(e) => set('balance_by_skill', e.target.checked)} />
          Equilibrar times por nível técnico e velocidade
        </label>
      </Section>

      <Section title="Campeonato">
        <Field label="Pontos por vitória"><NumberInput value={form.points_win} onChange={num('points_win')} min={0} max={10} /></Field>
        <Field label="Pontos por empate"><NumberInput value={form.points_draw} onChange={num('points_draw')} min={0} max={10} /></Field>
        <Field label="Pontos por derrota"><NumberInput value={form.points_loss} onChange={num('points_loss')} min={0} max={10} /></Field>
        <Field label="Peso do tempo da final" hint="Ex.: 1,5">
          <NumberInput value={form.final_weight} onChange={(v) => set('final_weight', v)} min={1} max={3} step={0.1} />
        </Field>
        <Field label="Duração do jogo de tabela (min)">
          <NumberInput value={form.group_match_minutes} onChange={num('group_match_minutes')} min={1} max={60} />
        </Field>
        <Field label="Empate no mata-mata">
          <select className="input" value={form.knockout_tie_rule} onChange={(e) => set('knockout_tie_rule', e.target.value as KnockoutTieRule)}>
            {Object.entries(knockoutTieLabel).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
        <Field label="Desempate da artilharia">
          <select className="input" value={form.top_scorer_tiebreak} onChange={(e) => set('top_scorer_tiebreak', e.target.value as TopScorerTiebreak)}>
            {Object.entries(topScorerLabel).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
        <div className="sm:col-span-2">
          <p className="mb-2 text-sm font-medium text-ink">Critérios de desempate (em ordem)</p>
          <ol className="space-y-1">
            {form.tiebreakers.map((t, i) => (
              <li key={t} className="flex items-center gap-2 rounded-lg bg-soft px-3 py-1.5 text-sm">
                <span className="w-5 text-muted">{i + 1}.</span>
                <span className="flex-1">{tiebreakerLabel[t]}</span>
                <button type="button" aria-label="Subir" disabled={i === 0} onClick={() => moveTiebreaker(i, -1)} className="px-1 disabled:opacity-30">▲</button>
                <button type="button" aria-label="Descer" disabled={i === form.tiebreakers.length - 1} onClick={() => moveTiebreaker(i, 1)} className="px-1 disabled:opacity-30">▼</button>
                <button type="button" aria-label="Remover" onClick={() => toggleTiebreaker(t)} className="px-1 text-danger-ink">✕</button>
              </li>
            ))}
          </ol>
          <div className="mt-2 flex flex-wrap gap-2">
            {ALL_TIEBREAKERS.filter((t) => !form.tiebreakers.includes(t)).map((t) => (
              <Button key={t} type="button" size="sm" variant="secondary" onClick={() => toggleTiebreaker(t)}>+ {tiebreakerLabel[t]}</Button>
            ))}
          </div>
        </div>
      </Section>

      <Section title="Pelada normal (2 times)">
        <Field label="Limite de gols por partida"><NumberInput value={form.casual_goal_limit} onChange={num('casual_goal_limit')} min={1} max={10} /></Field>
        <Field label="Duração de cada partida (min)"><NumberInput value={form.casual_match_minutes} onChange={num('casual_match_minutes')} min={1} max={60} /></Field>
      </Section>

      <Section title="Cartões">
        <Field label="Cartão vermelho">
          <select className="input" value={form.red_card_rule} onChange={(e) => set('red_card_rule', e.target.value as RedCardRule)}>
            {Object.entries(redCardLabel).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-primary" checked={form.two_yellows_red} onChange={(e) => set('two_yellows_red', e.target.checked)} />
          Dois amarelos na partida viram vermelho
        </label>
      </Section>
      {superadmin && <ChatbotSection />}
      {superadmin && <CatalogSection />}
    </form>
  )
}
