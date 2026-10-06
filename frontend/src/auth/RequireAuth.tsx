import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { UserRole } from '@/api/types'
import { Spinner } from '@/components/ui'
import { useAuth } from './AuthProvider'

export function RequireAuth({ roles }: { roles?: UserRole[] }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  // Troca de senha obrigatória: só "Minha conta" fica acessível até trocar
  if (user.must_change_password && location.pathname !== '/conta') return <Navigate to="/conta" replace />
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />
  return <Outlet />
}
