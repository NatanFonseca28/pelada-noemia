import { Flag, Pause, Play, RotateCcw } from 'lucide-react'
import { formatClock, useStopwatch, type StopwatchController } from '@/hooks/useStopwatch'
import { Button } from './Button'
import { cx, ICON_STROKE } from './cx'

/**
 * Visual do cronômetro local, controlado por fora (ex.: a súmula finaliza o cronômetro ao enviar o resultado).
 * `plannedSeconds` é só referência: não encerra sozinho, as pausas da pelada são imprevisíveis.
 */
export function StopwatchView({ sw, plannedSeconds, size = 'md', hideFinish }: {
  sw: StopwatchController
  plannedSeconds?: number
  size?: 'md' | 'xl'
  /** esconde "Encerrar" quando outro botão finaliza (ex.: "Finalizar súmula") */
  hideFinish?: boolean
}) {
  const over = plannedSeconds ? sw.elapsedMs / 1000 > plannedSeconds : false
  const btn = size === 'xl' ? 'xl' : 'md'
  return (
    <div className="flex flex-col items-center gap-2">
      <div
        role="timer"
        aria-label={`Cronômetro ${formatClock(sw.elapsedMs)}${sw.running ? ', rodando' : sw.finished ? ', encerrado' : ', pausado'}`}
        className={cx(
          'tabular font-display font-extrabold leading-none',
          size === 'xl' ? 'text-score' : 'text-5xl',
          !sw.running && sw.started && !sw.finished && 'anim-blink-paused',
          over && 'text-accent-ink',
        )}
      >
        {formatClock(sw.elapsedMs)}
      </div>
      {plannedSeconds ? (
        <p className={cx('text-xs', over ? 'font-semibold text-accent-ink' : 'text-muted')}>
          {over ? 'passou do previsto' : 'previsto'} {formatClock(plannedSeconds * 1000)}
        </p>
      ) : null}
      {sw.finished ? (
        <div className="flex flex-col items-center gap-2">
          <p className="text-center text-sm font-medium">
            Tempo de jogo <span className="tabular font-display text-lg font-bold">{formatClock(sw.elapsedMs)}</span>
            <span className="text-muted"> · com pausas </span>
            <span className="tabular font-display text-lg font-bold">{formatClock(sw.wallMs)}</span>
          </p>
          <Button variant="ghost" size="sm" onClick={sw.reset}>
            <RotateCcw size={16} strokeWidth={ICON_STROKE} aria-hidden /> Zerar
          </Button>
        </div>
      ) : (
        <div className="flex gap-2">
          {sw.running ? (
            <Button variant="secondary" size={btn} onClick={sw.pause}>
              <Pause size={20} strokeWidth={ICON_STROKE} aria-hidden /> Pausar
            </Button>
          ) : (
            <Button variant="accent" size={btn} onClick={sw.start}>
              <Play size={20} strokeWidth={ICON_STROKE} aria-hidden /> {sw.started ? 'Retomar' : 'Iniciar'}
            </Button>
          )}
          {sw.started && !hideFinish && (
            <Button variant="ghost" size={btn} onClick={sw.finish}>
              <Flag size={20} strokeWidth={ICON_STROKE} aria-hidden /> Encerrar
            </Button>
          )}
          {sw.started && hideFinish && !sw.running && (
            <Button variant="ghost" size={btn} onClick={sw.reset} aria-label="Zerar cronômetro">
              <RotateCcw size={18} strokeWidth={ICON_STROKE} aria-hidden />
            </Button>
          )}
        </div>
      )}
    </div>
  )
}

/** Cronômetro autônomo (com estado próprio, salvo no aparelho por `id`). */
export function Stopwatch({ id, plannedSeconds, size = 'md' }: { id: string; plannedSeconds?: number; size?: 'md' | 'xl' }) {
  const sw = useStopwatch(id)
  return <StopwatchView sw={sw} plannedSeconds={plannedSeconds} size={size} />
}
