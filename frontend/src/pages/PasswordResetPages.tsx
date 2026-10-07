import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { ApiError, api, json } from '@/api/client'
import { Alert, Button, Field } from '@/components/ui'
import { AuthShell } from './LoginPage'

/** Esqueci minha senha: pede aos administradores um link de nova senha (enviado pelo WhatsApp). */
export function ForgotPasswordPage() {
  const [identifier, setIdentifier] = useState('')
  const [sent, setSent] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const r = await api<{ detail: string }>('/auth/forgot', { method: 'POST', body: json({ identifier }) })
      setSent(r.detail)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Não foi possível enviar o pedido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title="Esqueci minha senha">
      {sent ? (
        <div className="space-y-4">
          <Alert kind="success">{sent}</Alert>
          <Link to="/login" className="block text-center text-sm font-medium text-primary-ink hover:underline">Voltar para o login</Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Field label="E-mail ou celular" hint="O link chega pelo WhatsApp, enviado por um administrador">
            <input className="input" required autoComplete="username" value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
          </Field>
          <Button type="submit" className="w-full" loading={loading}>Pedir nova senha</Button>
          <Link to="/login" className="block text-center text-sm text-muted hover:underline">Voltar para o login</Link>
        </form>
      )}
    </AuthShell>
  )
}

/** Página aberta pelo link: cria a senha nova (link de 1 hora, uso único). */
export function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (password !== confirm) return setError('As senhas não conferem')
    setLoading(true)
    try {
      await api('/auth/reset', { method: 'POST', body: json({ token, new_password: password }) })
      setDone(true)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Não foi possível trocar a senha')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title="Criar senha nova">
      {!token ? (
        <Alert>Link incompleto. Peça um novo em “Esqueci minha senha”.</Alert>
      ) : done ? (
        <div className="space-y-4">
          <Alert kind="success">Senha trocada. Entre com a senha nova.</Alert>
          <Button className="w-full" onClick={() => navigate('/login', { replace: true })}>Ir para o login</Button>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          {error && <Alert>{error}</Alert>}
          <Field label="Senha nova" hint="Mínimo de 10 caracteres">
            <input className="input" type="password" required minLength={10} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Field label="Confirmar senha nova">
            <input className="input" type="password" required minLength={10} autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </Field>
          <Button type="submit" className="w-full" loading={loading}>Salvar senha nova</Button>
        </form>
      )}
    </AuthShell>
  )
}
