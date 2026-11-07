import { AlertTriangle, CheckCircle2, CircleHelp, XCircle } from 'lucide-react'
import { useState } from 'react'
import type { DrawPreview } from '@/api/types'
import { Button, ICON_STROKE, Modal, cx } from '@/components/ui'

const TONE = {
  OK: { icon: CheckCircle2, box: 'border-ok/40 bg-ok/10', text: 'text-primary-ink' },
  SOBRA: { icon: AlertTriangle, box: 'border-accent/60 bg-accent/15', text: 'text-ink' },
  FALTA: { icon: XCircle, box: 'border-danger/40 bg-danger/10', text: 'text-danger-ink' },
} as const

/**
 * Faixa "Situação da lista": responde ANTES de sortear se a lista fecha times e, se não fecha, o que fazer.
 * Uma contagem, um veredito e botões de ação (nada de parágrafos).
 */
export function DrawStatus({ preview, busy, onApply }: {
  preview: DrawPreview
  busy?: boolean
  onApply: (o: DrawPreview['options'][number]) => void
}) {
  const tone = TONE[preview.status]
  const Icon = tone.icon
  const actions = preview.options.filter((o) => o.kind !== 'INFO')
  const hints = preview.options.filter((o) => o.kind === 'INFO')
  return (
    <div className={cx('mb-3 rounded-card border p-3', tone.box)} aria-live="polite">
      <p className="text-sm text-muted">
        <strong className="text-ink">{preview.confirmed} confirmados</strong> = {preview.line} de linha + {preview.goalkeepers} {preview.goalkeepers === 1 ? 'goleiro' : 'goleiros'}
      </p>
      <p className={cx('mt-1 flex items-center gap-2 font-display text-lg font-bold leading-tight', tone.text)}>
        <Icon size={20} strokeWidth={ICON_STROKE} aria-hidden /> {preview.headline}
      </p>
      <p className="mt-0.5 text-sm text-muted">{preview.detail}</p>
      {(actions.length > 0 || hints.length > 0) && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {actions.map((o) => (
            <Button key={o.label} size="sm" loading={busy} onClick={() => onApply(o)}>{o.label}</Button>
          ))}
          {hints.map((o) => <span key={o.label} className="text-sm text-ink">· {o.label}</span>)}
        </div>
      )}
    </div>
  )
}

const STEPS = ['Confirmar presença', 'Sortear', 'Travar times']

/** Passo a passo: onde a rodada está agora (0 a 2; 3 = tudo pronto). */
export function DrawSteps({ current }: { current: number }) {
  return (
    <ol className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs" aria-label="Etapas da rodada">
      {STEPS.map((label, i) => (
        <li key={label} className="flex items-center gap-2">
          <span className={cx('flex items-center gap-1.5 rounded-full px-2 py-0.5 font-medium', i < current ? 'text-primary-ink' : i === current ? 'bg-primary text-primary-on' : 'text-muted')}>
            <span aria-hidden>{i < current ? '✓' : i + 1}</span> {label}
          </span>
          {i < STEPS.length - 1 && <span className="text-muted" aria-hidden>›</span>}
        </li>
      ))}
    </ol>
  )
}

/** Botão "?" com as regras do sorteio em 4 linhas, para quem não conhece o app. */
export function DrawHelp() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} aria-label="Como funciona o sorteio" className="press inline-grid h-7 w-7 place-items-center rounded-full text-muted hover:bg-soft hover:text-ink">
        <CircleHelp size={18} strokeWidth={ICON_STROKE} aria-hidden />
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title="Como funciona o sorteio">
        <dl className="space-y-3 text-sm">
          <div><dt className="font-semibold">Todo time tem 5 na linha + 1 no gol</dt><dd className="text-muted">Nenhum time passa de 6 jogadores. Não existe reserva.</dd></div>
          <div><dt className="font-semibold">Quem fica no gol</dt><dd className="text-muted">O goleiro fixo do time, um jogador que reveza no gol, ou o goleiro da pelada que agarra para todos os times.</dd></div>
          <div><dt className="font-semibold">Quando sobra ou falta gente</dt><dd className="text-muted">A faixa no topo avisa antes de sortear e mostra o botão para resolver.</dd></div>
          <div><dt className="font-semibold">Jogar com menos 1</dt><dd className="text-muted">Quando falta só 1 para fechar mais um time, ele joga com 4 na linha e alguém do time de fora completa na hora.</dd></div>
        </dl>
      </Modal>
    </>
  )
}
