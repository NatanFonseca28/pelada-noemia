import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ApiError, api, downloadFile } from '@/api/client'
import { Alert, Button, Card, PageHeader, Spinner } from '@/components/ui'

interface ExportTable {
  name: string
  label: string
}

export function ExportPage() {
  const { data: tables, isLoading } = useQuery({
    queryKey: ['export', 'tables'],
    queryFn: () => api<ExportTable[]>('/export/tables'),
  })
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
      await downloadFile(`/export/xlsx${params}`, 'pelada-export.xlsx')
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
          <Button className="mt-4 w-full sm:w-auto" onClick={onExport} loading={loading} disabled={!selected.size}>
            ⬇ Baixar .xlsx
          </Button>
        </Card>
      )}
    </>
  )
}
