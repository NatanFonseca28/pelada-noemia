import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, api, json } from '@/api/client'
import { Alert, Button, Field } from '@/components/ui'
import { AuthShell } from './LoginPage'

export function RegisterPage() {
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' })
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value })

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (form.password !== form.confirm) return setError('As senhas não conferem')
    setLoading(true)
    try {
      await api('/auth/register', { method: 'POST', body: json({ name: form.name, email: form.email, password: form.password }) })
      setDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Não foi possível cadastrar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title="Criar conta">
      {done ? (
        <div className="space-y-4">
          <Alert kind="success">Cadastro enviado! Você poderá entrar assim que um administrador aprovar.</Alert>
          <Link to="/login" className="block text-center text-sm font-medium text-primary-ink hover:underline">
            Voltar ao login
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Field label="Nome">
            <input className="input" required minLength={2} value={form.name} onChange={set('name')} autoComplete="name" />
          </Field>
          <Field label="E-mail">
            <input className="input" type="email" required value={form.email} onChange={set('email')} autoComplete="email" />
          </Field>
          <Field label="Senha" hint="Mínimo de 10 caracteres">
            <input className="input" type="password" required minLength={10} value={form.password} onChange={set('password')} autoComplete="new-password" />
          </Field>
          <Field label="Confirmar senha">
            <input className="input" type="password" required minLength={10} value={form.confirm} onChange={set('confirm')} autoComplete="new-password" />
          </Field>
          <Button type="submit" className="w-full" loading={loading}>
            Cadastrar
          </Button>
          <p className="text-center text-sm text-muted">
            Já tem conta?{' '}
            <Link to="/login" className="font-medium text-primary-ink hover:underline">
              Entrar
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  )
}
