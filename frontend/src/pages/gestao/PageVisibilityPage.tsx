import { useEffect, useState } from 'react'
import { usePageVisibility, useSavePageVisibility } from '@/api/access'
import type { UserRole } from '@/api/types'
import { useToast } from '@/contexts/feedback'
import { Button, Card, PageHeader, QueryState, SkeletonList, errorMessage } from '@/components/ui'
import { roleLabel } from '@/lib/labels'

const ROLES: UserRole[] = ['ADMIN', 'MESARIO', 'JOGADOR']
const EMPTY: Record<UserRole, string[]> = { ADMIN: [], MESARIO: [], JOGADOR: [] }

export function PageVisibilityPage() {
  const query = usePageVisibility()
  const save = useSavePageVisibility()
  const toast = useToast()
  const [hidden, setHidden] = useState<Record<UserRole, string[]>>(EMPTY)

  useEffect(() => {
    if (query.data) setHidden({ ...EMPTY, ...query.data.hidden })
  }, [query.data])

  const visible = (role: UserRole, path: string) => !hidden[role].includes(path)
  const toggle = (role: UserRole, path: string) =>
    setHidden((h) => ({ ...h, [role]: visible(role, path) ? [...h[role], path] : h[role].filter((p) => p !== path) }))
  const dirty = query.data && JSON.stringify(ROLES.map((r) => [...hidden[r]].sort())) !== JSON.stringify(ROLES.map((r) => [...(query.data.hidden[r] ?? [])].sort()))

  const onSave = () =>
    save.mutate(hidden, {
      onSuccess: () => toast({ message: 'Visibilidade salva. Vale no próximo acesso de cada usuário.', tone: 'success' }),
      onError: (err) => toast({ message: errorMessage(err, 'Não foi possível salvar'), tone: 'error' }),
    })

  return (
    <>
      <PageHeader title="Visibilidade das páginas" actions={<Button onClick={onSave} disabled={!dirty} loading={save.isPending}>Salvar</Button>} />
      <QueryState query={query} skeleton={<SkeletonList rows={8} />}>
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[420px] text-sm">
            <thead className="text-xs text-muted">
              <tr className="border-b border-line">
                <th className="px-4 py-3 text-left font-medium">Página</th>
                {ROLES.map((r) => <th key={r} className="px-2 py-3 text-center font-medium">{roleLabel[r]}</th>)}
              </tr>
            </thead>
            <tbody>
              {query.data?.pages.map((p) => (
                <tr key={p.path} className="border-b border-line last:border-0">
                  <td className="px-4 py-2">
                    <span className="font-medium">{p.label}</span>
                    {p.path.startsWith('/gestao') && <span className="ml-1.5 text-xs text-muted">gestão</span>}
                  </td>
                  {ROLES.map((r) => (
                    <td key={r} className="px-2 py-1 text-center">
                      <label className="inline-grid h-11 w-11 cursor-pointer place-items-center">
                        <input
                          type="checkbox"
                          className="h-5 w-5 accent-primary"
                          checked={visible(r, p.path)}
                          onChange={() => toggle(r, p.path)}
                          aria-label={`${p.label} visível para ${roleLabel[r]}`}
                        />
                      </label>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <p className="mt-3 text-xs text-muted">Marcado = visível. Mesários e jogadores não acessam a gestão mesmo marcados.</p>
      </QueryState>
    </>
  )
}
