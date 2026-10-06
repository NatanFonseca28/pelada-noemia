import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ApiError, api, downloadFile } from '@/api/client'
import { Download } from 'lucide-react'
import { Alert, Button, Card, ICON_STROKE, PageHeader, Spinner, cx } from '@/components/ui'

interface ExportTable {
  name: string
  label: string
}

type Format = 'xlsx' | 'csv'
const FORMATS: { value: Format; title: string; text: string }[] = [
  { value: 'xlsx', title: 'Planilha (.xlsx)', text: 'Uma aba por tabela, para abrir no Excel' },
  { value: 'csv', title: 'CSV (.zip)', text: 'Valores exatos, com manifesto e SHA-256 para conferência' },
]

export function ExportPage() {
  const { data: tables, isLoading } = useQuery({
    queryKey: ['export', 'tables'],
    queryFn: () => api<ExportTable[]>('/export/tables'),
  })
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [format, setFormat] = useState<Format>('xlsx')

  useEffect(() => {
    if (tables) setSelected(new Set(tables.map((t) => t.name)))
  }, [tables])

  const toggle = (name: string) => {
    const next = new Set(selected)
    if (next.has(name)) next.delete(name)
    else next.add(name)
    setSelected(next)
  }
  const allSelected = !!tables && selected.size === tables.length

  async function onExport() {
    setError(null)
    setLoading(true)
    try {
      const params = allSelected ? '' : '?' + [...selected].map((t) => `tables=${encodeURIComponent(t)}`).join('&')
      await downloadFile(`/export/${format}${params}`, `pelada-export.${format === 'csv' ? 'zip' : 'xlsx'}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao exportar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader title="Exportar dados" />
      {isLoading || !tables ? (
        <Spinner />
      ) : (
        <Card className="max-w-xl p-5">
          {error && <div className="mb-4"><Alert>{error}</Alert></div>}
          <label className="mb-3 flex items-center gap-2 border-b border-line pb-3 text-sm font-medium">
            <input
              type="checkbox"
              className="h-4 w-4 accent-primary"
              checked={allSelected}
              onChange={() => setSelected(allSelected ? new Set() : new Set(tables.map((t) => t.name)))}
            />
            Todas as tabelas
          </label>
          <div className="grid gap-2 sm:grid-cols-2">
            {tables.map((t) => (
              <label key={t.name} className="flex items-center gap-2 text-sm">
                <input type="checkbox" className="h-4 w-4 accent-primary" checked={selected.has(t.name)} onChange={() => toggle(t.name)} />
                {t.label}
                <span className="font-mono text-xs text-muted">{t.name}</span>
              </label>
            ))}
          </div>
          <fieldset className="mt-5 border-t border-line pt-4">
            <legend className="mb-2 text-sm font-medium">Formato</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {FORMATS.map((f) => (
                <label
                  key={f.value}
                  className={cx('press flex min-h-[56px] cursor-pointer items-start gap-2 rounded-btn border p-3 text-sm', format === f.value ? 'border-primary bg-primary/10' : 'border-line hover:bg-soft')}
                >
                  <input type="radio" name="formato" className="mt-0.5 accent-primary" checked={format === f.value} onChange={() => setFormat(f.value)} />
                  <span>
                    <span className="block font-medium">{f.title}</span>
                    <span className="block text-xs text-muted">{f.text}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <Button className="mt-4 w-full sm:w-auto" onClick={onExport} loading={loading} disabled={!selected.size}>
            <Download size={18} strokeWidth={ICON_STROKE} aria-hidden /> Baixar {format === 'csv' ? '.zip' : '.xlsx'}
          </Button>
        </Card>
      )}
    </>
  )
}
