import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '@/api/client'
import { useAuth } from '@/auth/AuthProvider'
import { Alert, Button, Card, Field } from '@/components/ui'

export function AuthShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen place-items-center bg-bg p-4">
      <Card className="anim-page w-full max-w-sm overflow-hidden">
        <div className="pitch-lines border-b border-line px-6 pb-5 pt-6 text-center">
          <img src="/logo-192.webp" width={96} height={96} alt="Noemia Cup" className="mx-auto" />
          <h1 className="mt-2 text-xl font-bold">{title}</h1>
          <p className="text-sm text-muted">Pelada de Quarta</p>
        </div>
        <div className="p-6">{children}</div>
      </Card>
    </div>
  )
}

export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (user) return <Navigate to="/" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
      navigate((location.state as { from?: string } | null)?.from ?? '/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Não foi possível entrar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title="Entrar">
      <form onSubmit={onSubmit} className="space-y-4">
        {error && <Alert>{error}</Alert>}
        <Field label="E-mail">
          <input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Senha">
          <input className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <p className="-mt-2 text-right text-sm">
          <Link to="/esqueci-senha" className="text-primary-ink hover:underline">Esqueci minha senha</Link>
        </p>
        <Button type="submit" className="w-full" loading={loading}>
          Entrar
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-muted">
        Ainda não tem conta?{' '}
        <Link to="/cadastro" className="font-medium text-primary-ink hover:underline">
          Cadastre-se
        </Link>
      </p>
    </AuthShell>
  )
}
