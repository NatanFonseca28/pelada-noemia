import { useState, type FormEvent } from 'react'
import { ApiError, api, json } from '@/api/client'
import { useAuth } from '@/auth/AuthProvider'
import { Alert, Button, Card, Field, PageHeader } from '@/components/ui'
import { roleLabel } from '@/lib/labels'

export function AccountPage() {
  const { user, logout } = useAuth()
  const [form, setForm] = useState({ current: '', next: '', confirm: '' })
  const [msg, setMsg] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setMsg(null)
    if (form.next !== form.confirm) return setMsg({ kind: 'error', text: 'As senhas não conferem' })
    setLoading(true)
    try {
      await api('/auth/change-password', { method: 'POST', body: json({ current_password: form.current, new_password: form.next }) })
      setMsg({ kind: 'success', text: 'Senha alterada. Faça login novamente.' })
      setTimeout(logout, 1500)
    } catch (err) {
      setMsg({ kind: 'error', text: err instanceof ApiError ? err.message : 'Erro ao alterar senha' })
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <PageHeader title="Minha conta" />
      {user?.must_change_password && (
        <div className="mb-4">
          <Alert kind="info">
            Por segurança, defina uma senha nova antes de continuar. A senha atual é a que o administrador passou para você.
          </Alert>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-1 p-5 text-sm">
          <p><span className="text-muted">Nome:</span> {user?.name}</p>
          <p><span className="text-muted">E-mail:</span> {user?.email}</p>
          <p><span className="text-muted">Papel:</span> {user && roleLabel[user.role]}</p>
        </Card>
        <Card className="p-5">
          <h2 className="mb-4 font-semibold">Trocar senha</h2>
          <form onSubmit={onSubmit} className="space-y-3">
            {msg && <Alert kind={msg.kind}>{msg.text}</Alert>}
            <Field label="Senha atual">
              <input className="input" type="password" required autoComplete="current-password" value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} />
            </Field>
            <Field label="Nova senha">
              <input className="input" type="password" required minLength={10} autoComplete="new-password" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} />
            </Field>
            <Field label="Confirmar nova senha">
              <input className="input" type="password" required minLength={10} autoComplete="new-password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
            </Field>
            <Button type="submit" loading={loading}>Alterar senha</Button>
          </form>
        </Card>
      </div>
    </>
  )
}
