import { cx } from './cx'

export interface TabItem<T extends string> {
  id: T
  label: string
  count?: number
}

/** Abas em pílula (mesmo visual do financeiro). Controlado: quem usa guarda a aba ativa. */
export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: TabItem<T>[]; value: T; onChange: (id: T) => void; label: string }) {
  return (
    <div className="mb-4 flex gap-1 overflow-x-auto rounded-full bg-soft p-1" role="tablist" aria-label={label}>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={value === t.id}
          onClick={() => onChange(t.id)}
          className={cx('press min-h-[40px] whitespace-nowrap rounded-full px-4 py-1.5 text-sm font-medium', value === t.id ? 'bg-surface text-ink shadow-card' : 'text-muted hover:text-ink')}
        >
          {t.label}
          {t.count !== undefined && <span className="tabular ml-1.5 text-xs text-muted">{t.count}</span>}
        </button>
      ))}
    </div>
  )
}
