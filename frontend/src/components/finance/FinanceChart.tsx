import { useEffect, useId, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { ArrowDownRight, ArrowUpRight, TrendingUp } from 'lucide-react'
import type { FlowPoint } from '@/lib/finance'
import { formatCurrency, formatCurrencyCompact } from '@/lib/labels'
import { ICON_STROKE, cx } from '../ui'

const PAD = { top: 18, right: 18, bottom: 30, left: 64 }
const MIN_WIDTH = 520

/** Ticks "redondos" para o eixo Y (inclui o zero). */
function niceTicks(min: number, max: number, count = 4): number[] {
  const span = Math.max(max - min, 1)
  const raw = span / count
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw
  const lo = Math.floor(min / step) * step
  const hi = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v * 100) / 100)
  return ticks
}

/** Barra com topo arredondado (raio 6px) ancorada na linha de base. */
function barPath(x: number, w: number, yTop: number, yBase: number): string {
  const h = yBase - yTop
  if (h <= 0) return ''
  const r = Math.min(6, w / 2, h)
  return `M${x},${yBase}V${yTop + r}Q${x},${yTop} ${x + r},${yTop}H${x + w - r}Q${x + w},${yTop} ${x + w},${yTop + r}V${yBase}Z`
}

function useSize() {
  const ref = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  const [desktop, setDesktop] = useState(() => window.matchMedia?.('(min-width: 768px)').matches ?? true)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    ro.observe(el)
    const mq = window.matchMedia('(min-width: 768px)')
    const onMq = () => setDesktop(mq.matches)
    mq.addEventListener('change', onMq)
    return () => {
      ro.disconnect()
      mq.removeEventListener('change', onMq)
    }
  }, [])
  return { ref, width: Math.max(width, MIN_WIDTH), height: desktop ? 320 : 260 }
}

export function FinanceChart({ points, summaryLabel, animationKey }: { points: FlowPoint[]; summaryLabel: string; animationKey: string }) {
  const { ref, width, height } = useSize()
  const uid = useId().replace(/:/g, '')
  const [hover, setHover] = useState<number | null>(null)
  const [pinned, setPinned] = useState<number | null>(null)
  const active = pinned ?? hover

  const geo = useMemo(() => {
    const values = points.flatMap((p) => [p.entradas, p.saidas, p.saldo ?? 0])
    const ticks = niceTicks(Math.min(0, ...values), Math.max(1, ...values))
    const yMin = ticks[0]
    const yMax = ticks[ticks.length - 1]
    const plotW = width - PAD.left - PAD.right
    const plotH = height - PAD.top - PAD.bottom
    const y = (v: number) => PAD.top + plotH - ((v - yMin) / (yMax - yMin || 1)) * plotH
    const groupW = plotW / points.length
    const barW = Math.max(4, Math.min(22, (groupW - 12) / 2))
    const cx0 = (i: number) => PAD.left + groupW * i + groupW / 2
    return { ticks, y, groupW, barW, cx0, plotH }
  }, [points, width, height])

  const linePts = points
    .map((p, i) => (p.saldo === null ? null : { i, x: geo.cx0(i), y: geo.y(p.saldo), v: p.saldo }))
    .filter((p): p is { i: number; x: number; y: number; v: number } => p !== null)
  const linePath = linePts.map((p, k) => `${k ? 'L' : 'M'}${p.x},${p.y}`).join('')
  const last = linePts[linePts.length - 1]
  const base = geo.y(0)

  const tip = active !== null ? points[active] : null
  const tipX = active !== null ? geo.cx0(active) : 0

  return (
    <div className="relative">
      <div className="-mx-1 overflow-x-auto px-1">
        <div ref={ref} style={{ minWidth: MIN_WIDTH }} className="relative">
          <svg
            key={animationKey}
            width={width}
            height={height}
            role="img"
            aria-label={summaryLabel}
            className="block select-none"
            onMouseLeave={() => setHover(null)}
          >
            <defs>
              {/* Textura das saídas: separa de "entradas" também para daltônicos e impressão */}
              <pattern id={`hatch-${uid}`} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <rect width="6" height="6" fill="rgb(var(--danger))" />
                <line x1="0" y1="0" x2="0" y2="6" stroke="rgb(var(--surface))" strokeOpacity="0.45" strokeWidth="2" />
              </pattern>
            </defs>

            {/* grade e eixo Y */}
            {geo.ticks.map((t) => (
              <g key={t}>
                <line
                  x1={PAD.left}
                  x2={width - PAD.right}
                  y1={geo.y(t)}
                  y2={geo.y(t)}
                  stroke="rgb(var(--line))"
                  strokeDasharray={t === 0 ? undefined : '4 4'}
                  strokeWidth={1}
                />
                <text x={PAD.left - 8} y={geo.y(t)} dy="0.32em" textAnchor="end" className="fill-muted text-[11px] tabular">
                  {formatCurrencyCompact(t)}
                </text>
              </g>
            ))}

            {/* barras */}
            {points.map((p, i) => {
              const x = geo.cx0(i)
              return (
                <g key={p.key} style={{ '--i': i } as CSSProperties} opacity={active === null || active === i ? 1 : 0.55}>
                  <path className="anim-bar" style={{ '--i': i } as CSSProperties} d={barPath(x - geo.barW - 1, geo.barW, geo.y(p.entradas), base)} fill="rgb(var(--ok))" />
                  <path className="anim-bar" style={{ '--i': i } as CSSProperties} d={barPath(x + 1, geo.barW, geo.y(p.saidas), base)} fill={`url(#hatch-${uid})`} />
                  <text x={x} y={height - 10} textAnchor="middle" className={cx('text-[11px]', active === i ? 'fill-ink font-semibold' : 'fill-muted')}>
                    {p.label}
                  </text>
                </g>
              )
            })}

            {/* saldo acumulado: contorno escuro por baixo garante leitura do âmbar no tema claro */}
            {linePts.length > 1 && (
              <>
                <path d={linePath} fill="none" stroke="rgb(var(--ink))" strokeOpacity="0.35" strokeWidth={4.5} strokeLinejoin="round" strokeLinecap="round" pathLength={1} className="anim-line" />
                <path d={linePath} fill="none" stroke="rgb(var(--accent))" strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" pathLength={1} className="anim-line" />
              </>
            )}
            {linePts.map((p) => (
              <circle key={p.i} cx={p.x} cy={p.y} r={active === p.i ? 5.5 : 4} fill="rgb(var(--accent))" stroke="rgb(var(--surface))" strokeWidth={2} />
            ))}
            {last && (
              <text x={Math.min(last.x, width - PAD.right - 4)} y={last.y - 10} textAnchor={last.x > width - 120 ? 'end' : 'middle'} className="fill-ink text-[11px] font-semibold tabular">
                {formatCurrency(last.v)}
              </text>
            )}

            {/* alvos de hover/toque: a coluna inteira do mês */}
            {points.map((p, i) => (
              <rect
                key={`hit-${p.key}`}
                x={geo.cx0(i) - geo.groupW / 2}
                y={PAD.top}
                width={geo.groupW}
                height={geo.plotH}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onClick={() => setPinned((cur) => (cur === i ? null : i))}
                style={{ cursor: 'pointer' }}
              />
            ))}
            {active !== null && (
              <line x1={tipX} x2={tipX} y1={PAD.top} y2={base} stroke="rgb(var(--muted))" strokeOpacity="0.4" strokeDasharray="2 3" pointerEvents="none" />
            )}
          </svg>

          {tip && (
            <div
              role="status"
              className="pointer-events-none absolute top-2 z-10 min-w-[180px] rounded-btn border border-line bg-surface p-3 text-xs shadow-card"
              style={{ left: Math.min(Math.max(tipX - 90, 4), width - 188) }}
            >
              <p className="mb-1.5 font-semibold capitalize text-ink">{tip.name}{pinned !== null && <span className="ml-1 font-normal text-muted">(fixado)</span>}</p>
              <TipRow icon={<ArrowUpRight size={14} strokeWidth={ICON_STROKE} className="text-primary-ink" />} label="Entradas" value={formatCurrency(tip.entradas)} />
              <TipRow icon={<ArrowDownRight size={14} strokeWidth={ICON_STROKE} className="text-danger-ink" />} label="Saídas" value={formatCurrency(tip.saidas)} />
              <TipRow icon={<TrendingUp size={14} strokeWidth={ICON_STROKE} className="text-ink" />} label="Saldo" value={tip.saldo === null ? '—' : formatCurrency(tip.saldo)} />
            </div>
          )}
        </div>
      </div>

      {/* Legenda fixa (sem legenda flutuante) */}
      <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink">
        <li className="flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-ok" aria-hidden />
          <ArrowUpRight size={14} strokeWidth={ICON_STROKE} aria-hidden /> Entradas
        </li>
        <li className="flex items-center gap-1.5">
          <svg width="12" height="12" aria-hidden>
            <rect width="12" height="12" rx="3" fill={`url(#hatch-${uid})`} />
          </svg>
          <ArrowDownRight size={14} strokeWidth={ICON_STROKE} aria-hidden /> Saídas
        </li>
        <li className="flex items-center gap-1.5">
          <svg width="22" height="12" aria-hidden>
            <line x1="1" x2="21" y1="6" y2="6" stroke="rgb(var(--accent))" strokeWidth="2.5" strokeLinecap="round" />
            <circle cx="11" cy="6" r="3.5" fill="rgb(var(--accent))" stroke="rgb(var(--surface))" strokeWidth="1.5" />
          </svg>
          Saldo acumulado
        </li>
      </ul>

      {/* Tabela equivalente para leitores de tela */}
      <table className="sr-only">
        <caption>{summaryLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Período</th>
            <th scope="col">Entradas</th>
            <th scope="col">Saídas</th>
            <th scope="col">Saldo acumulado</th>
          </tr>
        </thead>
        <tbody>
          {points.map((p) => (
            <tr key={p.key}>
              <th scope="row">{p.name}</th>
              <td>{formatCurrency(p.entradas)}</td>
              <td>{formatCurrency(p.saidas)}</td>
              <td>{p.saldo === null ? 'sem saldo registrado' : formatCurrency(p.saldo)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TipRow({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <p className="flex items-center justify-between gap-4 py-0.5">
      <span className="flex items-center gap-1.5 text-muted">{icon}{label}</span>
      <span className="tabular font-semibold text-ink">{value}</span>
    </p>
  )
}
