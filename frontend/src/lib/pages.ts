import { useAuth } from '@/auth/AuthProvider'

/** A página (ou uma sub-rota dela) está oculta para a categoria do usuário? */
export const isHiddenPath = (path: string, hidden: string[]) => hidden.some((p) => path === p || path.startsWith(p + '/'))

/** Páginas ocultas para o usuário logado e se ele é superadmin. */
export function usePageAccess() {
  const { user } = useAuth()
  const hidden = user?.hidden_pages ?? []
  return { hidden, isHidden: (path: string) => isHiddenPath(path, hidden), superadmin: !!user?.is_superadmin }
}
