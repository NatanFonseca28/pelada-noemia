import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { usePageAccess } from '@/lib/pages'

/** Páginas ocultas para a categoria do usuário voltam para o Início (também ao abrir o endereço direto). */
export function RequirePage() {
  const { pathname } = useLocation()
  const { isHidden } = usePageAccess()
  return isHidden(pathname) ? <Navigate to="/" replace /> : <Outlet />
}

/** Auditoria, log de acessos, visibilidade e design system: só o superadmin. */
export function RequireSuperadmin() {
  const { superadmin } = usePageAccess()
  return superadmin ? <Outlet /> : <Navigate to="/" replace />
}
