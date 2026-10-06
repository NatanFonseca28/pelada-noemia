import { useState } from 'react'
import { Link } from 'react-router-dom'
import { usePlayers } from '@/api/queries'
import { Avatar, Badge, Card, EmptyState, PageHeader, Spinner } from '@/components/ui'
import { playerTypeLabel, positionLabel, positionText } from '@/lib/labels'

export function PlayersListPage() {
  const [q, setQ] = useState('')
  const { data, isLoading } = usePlayers({ active: true, q: q || undefined })

  return (
    <>
      <PageHeader title="Elenco" />
      <input className="input mb-4 max-w-sm" placeholder="Buscar por nome ou apelido" value={q} onChange={(e) => setQ(e.target.value)} />
      {isLoading ? (
        <Spinner />
      ) : !data?.length ? (
        <EmptyState>Nenhum jogador encontrado.</EmptyState>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((p) => (
            <Link key={p.id} to={`/jogadores/${p.id}`}>
            <Card className="flex items-center gap-3 p-3 transition hover:border-primary">
              <Avatar name={p.display_name} url={p.photo_url} />
              <div className="min-w-0">
                <p className="truncate font-medium">{p.display_name}</p>
                <div className="mt-1 flex flex-wrap gap-1">
                  <Badge color={p.primary_position ? 'green' : 'gray'}>{positionText(p.primary_position)}</Badge>
                  {p.secondary_position && <Badge>{positionLabel[p.secondary_position]}</Badge>}
                  <Badge color={p.type === 'MENSALISTA' ? 'blue' : 'yellow'}>{playerTypeLabel[p.type]}</Badge>
                </div>
              </div>
            </Card>
            </Link>
          ))}
        </div>
      )}
    </>
  )
}
