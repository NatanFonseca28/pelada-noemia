import { yearOptions } from '@/lib/years'

/** Filtro de ano: de 2026 até o ano atual. Com um ano só, mostra o ano como texto (um filtro de uma opção só confunde). */
export function YearFilter({ value, onChange }: { value: number; onChange: (year: number) => void }) {
  const years = yearOptions()
  if (years.length === 1) return <span className="tabular rounded-btn bg-soft px-3 py-2 text-sm font-medium" aria-label="Ano">{years[0]}</span>
  return (
    <select className="input w-auto" value={value} onChange={(e) => onChange(Number(e.target.value))} aria-label="Ano">
      {years.map((y) => <option key={y} value={y}>{y}</option>)}
    </select>
  )
}
