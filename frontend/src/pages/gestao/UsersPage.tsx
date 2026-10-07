import { useState, type FormEvent } from 'react'
import { Phone } from 'lucide-react'
import { ApiError } from '@/api/client'
import { useApproveUser, useCreateUser, usePlayers, useRejectUser, useUpdateUser, useUsers } from '@/api/queries'
import type { Player, User, UserRole, UserStatus } from '@/api/types'
import { useAuth } from '@/auth/AuthProvider'
import { Alert, Badge, Button, Card, EmptyState, Field, ICON_STROKE, Modal, PageHeader, PlayerName, Spinner, cx } from '@/components/ui'
import { formatDateTime, roleLabel, statusLabel } from '@/lib/labels'
import { formatPhone } from '@/lib/phone'

const ROLES: UserRole[] = ['JOGADOR', 'MESARIO', 'ADMIN']
const statusColor: Record<UserStatus, 'yellow' | 'green' | 'red'> = { PENDENTE: 'yellow', ATIVO: 'green', BLOQUEADO: 'red' }

function PlayerSelect({ value, onChange, players, users, selfId }: {
  value: number | null
  onChange: (v: number | null) => void
  players: Player[]
  users: User[]
  selfId?: number
}) {
  const taken = new Set(users.filter((u) => u.id !== selfId && u.player_id).map((u) => u.player_id))
  return (
    <select className="input" value={value ?? ''} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
      <option value="">Sem vínculo</option>
      {players.filter((p) => !taken.has(p.id)).map((p) => (
        <option key={p.id} value={p.id}>{p.display_name} — {p.name}</option>
      ))}
    </select>
  )
}

function UserForm({ user, users, players, onDone }: { user: User | null; users: User[]; players: Player[]; onDone: () => void }) {
  const { user: me } = useAuth()
  const [form, setForm] = useState({
    name: user?.name ?? '',
    email: user?.email ?? '',
    password: '',
    role: user?.role ?? ('JOGADOR' as UserRole),
    status: user?.status ?? ('ATIVO' as UserStatus),
    player_id: user?.player_id ?? null,
  })
  const [error, setError] = useState<string | null>(null)
  const create = useCreateUser()
  const update = useUpdateUser()

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      if (user) {
        await update.mutateAsync({
          id: user.id,
          data: {
            name: form.name,
            role: form.role,
            status: form.status,
            ...(form.player_id ? { player_id: form.player_id } : { unlink_player: true }),
            ...(form.password ? { password: form.password } : {}),
          },
        })
      } else {
        await create.mutateAsync({ name: form.name, email: form.email, password: form.password, role: form.role, player_id: form.player_id })
      }
      onDone()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro ao salvar')
    }
  }

  const isSelf = user?.id === me?.id
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <Field label="Nome">
        <input className="input" required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </Field>
      <Field label="E-mail">
        <input className="input" type="email" required disabled={!!user} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
      </Field>
      <Field label={user ? 'Nova senha' : 'Senha'} hint={user ? 'Deixe em branco para manter' : 'Mínimo de 10 caracteres. A pessoa troca no 1º acesso.'}>
        <input className="input" type="password" required={!user} minLength={10} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Papel">
          <select className="input" disabled={isSelf} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as UserRole })}>
            {ROLES.map((r) => <option key={r} value={r}>{roleLabel[r]}</option>)}
          </select>
        </Field>
        {user && (
          <Field label="Situação">
            <select className="input" disabled={isSelf} value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value as UserStatus })}>
              {(['ATIVO', 'BLOQUEADO'] as UserStatus[]).map((s) => <option key={s} value={s}>{statusLabel[s]}</option>)}
            </select>
          </Field>
        )}
      </div>
      <Field
        label="Jogador vinculado"
        hint={
          form.player_id
            ? `WhatsApp: ${formatPhone(players.find((p) => p.id === form.player_id)?.phone) || 'não cadastrado'} — edite em Gestão → Cadastro de jogadores`
            : 'Perfil esportivo deste usuário (o WhatsApp fica no cadastro do jogador)'
        }
      >
        <PlayerSelect value={form.player_id} onChange={(v) => setForm({ ...form, player_id: v })} players={players} users={users} selfId={user?.id} />
      </Field>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={create.isPending || update.isPending}>Salvar</Button>
      </div>
    </form>
  )
}

function PendingCard({ user, users, players }: { user: User; users: User[]; players: Player[] }) {
  const [role, setRole] = useState<UserRole>('JOGADOR')
  const [playerId, setPlayerId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const approve = useApproveUser()
  const reject = useRejectUser()

  const run = async (fn: () => Promise<unknown>) => {
    setError(null)
    try {
      await fn()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Erro')
    }
  }

  return (
    <Card className="space-y-3 p-4">
      <div>
        <p className="font-medium">{user.name}</p>
        <p className="text-sm text-muted">{user.email} · {formatDateTime(user.created_at)}</p>
      </div>
      {error && <Alert>{error}</Alert>}
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Papel">
          <select className="input" value={role} onChange={(e) => setRole(e.target.value as UserRole)}>
            {ROLES.map((r) => <option key={r} value={r}>{roleLabel[r]}</option>)}
          </select>
        </Field>
        <Field label="Vincular ao jogador">
          <PlayerSelect value={playerId} onChange={setPlayerId} players={players} users={users} />
        </Field>
      </div>
      <div className="flex justify-end gap-2">
        <Button variant="secondary" loading={reject.isPending} onClick={() => confirm(`Recusar o cadastro de ${user.name}?`) && run(() => reject.mutateAsync(user.id))}>
          Recusar
        </Button>
        <Button loading={approve.isPending} onClick={() => run(() => approve.mutateAsync({ id: user.id, role, player_id: playerId }))}>
          Aprovar
        </Button>
      </div>
    </Card>
  )
}

export function UsersPage() {
  const [tab, setTab] = useState<'pendentes' | 'todos'>('todos')
  const [editing, setEditing] = useState<User | null | undefined>(undefined)
  const { data: users, isLoading } = useUsers()
  const { data: players = [] } = usePlayers()
  const pending = (users ?? []).filter((u) => u.status === 'PENDENTE')
  const others = (users ?? []).filter((u) => u.status !== 'PENDENTE')
  const playerName = (id: number | null) => players.find((p) => p.id === id)?.display_name
  const playerPhone = (id: number | null) => players.find((p) => p.id === id)?.phone ?? null

  return (
    <>
      <PageHeader title="Usuários" actions={<Button onClick={() => setEditing(null)}>+ Novo usuário</Button>} />
      <div className="mb-4 inline-flex rounded-lg bg-soft p-1" role="tablist">
        {(['todos', 'pendentes'] as const).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            onClick={() => setTab(t)}
            className={cx('rounded-md px-3 py-1.5 text-sm font-medium', tab === t ? 'bg-surface shadow' : 'text-muted')}
            >
            {t === 'todos' ? 'Usuários' : 'Pendentes'}
            {t === 'pendentes' && pending.length > 0 && <span className="ml-1.5 rounded-full bg-accent px-1.5 text-xs font-semibold text-accent-on">{pending.length}</span>}
          </button>
        ))}
      </div>

      {isLoading ? (
        <Spinner />
      ) : tab === 'pendentes' ? (
        pending.length ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {pending.map((u) => <PendingCard key={u.id} user={u} users={users ?? []} players={players} />)}
          </div>
        ) : (
          <EmptyState>Nenhum cadastro aguardando aprovação.</EmptyState>
        )
      ) : (
        <Card className="divide-y divide-line">
          {others.map((u) => (
            <div key={u.id} className="flex flex-wrap items-center gap-3 p-3">
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{u.name}</p>
                <p className="truncate text-sm text-muted">{u.email}</p>
              </div>
              <div className="flex flex-wrap gap-1">
                <Badge color="blue">{roleLabel[u.role]}</Badge>
                <Badge color={statusColor[u.status]}>{statusLabel[u.status]}</Badge>
                {u.player_id && <Badge><PlayerName id={u.player_id} name={playerName(u.player_id) ?? `#${u.player_id}`} /></Badge>}
                {u.player_id && playerPhone(u.player_id) && (
                  <Badge>
                    <Phone size={11} strokeWidth={ICON_STROKE} aria-hidden /> {formatPhone(playerPhone(u.player_id))}
                  </Badge>
                )}
              </div>
              <Button size="sm" variant="secondary" onClick={() => setEditing(u)}>Editar</Button>
            </div>
          ))}
        </Card>
      )}

      <Modal open={editing !== undefined} onClose={() => setEditing(undefined)} title={editing ? 'Editar usuário' : 'Novo usuário'}>
        {editing !== undefined && (
          <UserForm key={editing?.id ?? 'new'} user={editing} users={users ?? []} players={players} onDone={() => setEditing(undefined)} />
        )}
      </Modal>
    </>
  )
}
