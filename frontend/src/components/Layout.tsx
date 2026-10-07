import { Suspense, useEffect, useState } from 'react'
import {
  ArrowDownToLine,
  BarChart3,
  CalendarCheck,
  CircleUserRound,
  Dices,
  Home,
  EyeOff,
  KeyRound,
  LayoutDashboard,
  ListChecks,
  LogIn,
  MessageSquareText,
  LogOut,
  Monitor,
  Moon,
  MoreHorizontal,
  Palette,
  Settings,
  ShieldCheck,
  Shirt,
  Sun,
  Trophy,
  UserCheck,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import type { UserRole } from '@/api/types'
import { useAuth } from '@/auth/AuthProvider'
import { usePageAccess } from '@/lib/pages'
import { AccountChip } from './AccountChip'
import { NotificationBell } from './NotificationBell'
import { useSheetQueueFlusher } from '@/hooks/useSheetQueue'
import { roleLabel } from '@/lib/labels'
import { useTheme, type Theme } from '@/theme/ThemeProvider'
import { ICON_STROKE, Modal, SkeletonList, cx } from './ui'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  roles?: UserRole[]
  /** rota exata (não marca ativo em sub-rotas) */
  end?: boolean
}

// Área da pelada (todos)
const PELADA: NavItem[] = [
  { to: '/', label: 'Início', icon: Home, end: true },
  { to: '/rodada', label: 'Rodada', icon: CalendarCheck },
  { to: '/campeonato', label: 'Campeonato', icon: Trophy },
  { to: '/estatisticas', label: 'Estatísticas', icon: BarChart3 },
  { to: '/jogadores', label: 'Jogadores', icon: Shirt },
  { to: '/minha-area', label: 'Minha área', icon: CircleUserRound },
]

// Área de gestão (admin)
const GESTAO: NavItem[] = [
  { to: '/gestao/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/gestao/rodadas', label: 'Rodadas e sorteio', icon: Dices },
  { to: '/gestao/presenca', label: 'Presença', icon: UserCheck },
  { to: '/gestao/jogadores', label: 'Cadastro de jogadores', icon: ListChecks },
  { to: '/gestao/usuarios', label: 'Usuários', icon: Users },
  { to: '/gestao/financeiro', label: 'Financeiro', icon: Wallet },
  { to: '/gestao/configuracoes', label: 'Configurações', icon: Settings },
  { to: '/gestao/exportar', label: 'Exportar dados', icon: ArrowDownToLine },
]

// Só o superadmin
const SUPER: NavItem[] = [
  { to: '/gestao/visibilidade', label: 'Visibilidade das páginas', icon: EyeOff },
  { to: '/gestao/mensagem-cobranca', label: 'Mensagem de cobrança', icon: MessageSquareText },
  { to: '/gestao/acessos', label: 'Log de acessos', icon: LogIn },
  { to: '/gestao/auditoria', label: 'Auditoria', icon: ShieldCheck },
  { to: '/gestao/design', label: 'Design system', icon: Palette },
]

// Barra inferior do celular: no máximo 5 itens; o resto vai para "Mais"
const BOTTOM: NavItem[] = [PELADA[0], PELADA[1], PELADA[2], PELADA[3]]

const themeIcons: Record<Theme, LucideIcon> = { light: Sun, dark: Moon, system: Monitor }
const themeNames: Record<Theme, string> = { light: 'claro', dark: 'escuro', system: 'do sistema' }
const nextTheme: Record<Theme, Theme> = { dark: 'light', light: 'system', system: 'dark' }

/** Título da seção atual (cabeçalho compacto do celular). */
function sectionTitle(path: string): string {
  const all = [...SUPER, ...GESTAO, ...PELADA, { to: '/conta', label: 'Minha conta', icon: KeyRound }]
  const hit = all
    .filter((i) => (i.to === '/' ? path === '/' : path === i.to || path.startsWith(i.to + '/')))
    .sort((a, b) => b.to.length - a.to.length)[0]
  return hit?.label ?? 'Pelada de Quarta'
}

function isActive(item: NavItem, path: string) {
  return item.end ? path === item.to : path === item.to || path.startsWith(item.to + '/')
}

/** Marca: escudo Noemia Cup + nome em Barlow. */
function Brand() {
  return (
    <span className="flex items-center gap-2">
      <img src="/logo-96.webp" width={36} height={36} alt="" aria-hidden className="shrink-0" />
      <span className="font-display text-xl font-bold leading-none tracking-wide">Pelada de Quarta</span>
    </span>
  )
}

function SideLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive: active }) =>
        cx(
          'press relative flex min-h-[44px] items-center gap-3 rounded-btn px-3 text-sm font-medium',
          active ? 'bg-primary/15 text-primary-ink' : 'text-muted hover:bg-soft hover:text-ink',
        )
      }
    >
      {({ isActive: active }) => (
        <>
          {active && <span className="absolute inset-y-2 left-0 w-1 rounded-r bg-primary" aria-hidden />}
          <item.icon size={19} strokeWidth={ICON_STROKE} aria-hidden />
          {item.label}
        </>
      )}
    </NavLink>
  )
}

function GroupLabel({ children, admin }: { children: string; admin?: boolean }) {
  return (
    <p className={cx('flex items-center gap-1.5 px-3 pb-1 pt-5 font-display text-sm font-semibold', admin ? 'text-accent-ink' : 'text-muted')}>
      {admin && <ShieldCheck size={14} strokeWidth={ICON_STROKE} aria-hidden />}
      {children}
    </p>
  )
}

export function Layout() {
  const { user, logout, hasRole } = useAuth()
  const { theme, setTheme } = useTheme()
  const [moreOpen, setMoreOpen] = useState(false)
  const { pathname } = useLocation()
  const ThemeIcon = themeIcons[theme]
  const admin = hasRole('ADMIN')
  const { isHidden, superadmin } = usePageAccess()
  useSheetQueueFlusher() // lances da súmula guardados sem internet
  const pelada = PELADA.filter((i) => !isHidden(i.to))
  const gestao = GESTAO.filter((i) => !isHidden(i.to))
  const bottom = BOTTOM.filter((i) => !isHidden(i.to))
  const inGestao = pathname.startsWith('/gestao')
  const title = sectionTitle(pathname)

  useEffect(() => {
    document.title = `${title} · Pelada de Quarta`
    setMoreOpen(false)
  }, [title, pathname])

  const themeButton = (
    <button
      onClick={() => setTheme(nextTheme[theme])}
      className="press grid h-11 w-11 place-items-center rounded-btn text-muted hover:bg-soft hover:text-ink"
      title={`Tema ${themeNames[theme]} (alternar)`}
      aria-label={`Tema ${themeNames[theme]}, alternar`}
    >
      <ThemeIcon size={19} strokeWidth={ICON_STROKE} />
    </button>
  )

  return (
    <div className="min-h-dvh lg:pl-64">
      <a href="#conteudo" className="sr-only z-toast rounded-btn bg-accent px-4 py-2 text-accent-on focus:not-sr-only focus:fixed focus:left-3 focus:top-3">
        Pular para o conteúdo
      </a>

      {/* ---------------- Barra lateral (desktop) ---------------- */}
      <aside className="fixed inset-y-0 left-0 z-nav hidden w-64 flex-col border-r border-line bg-surface lg:flex" aria-label="Navegação principal">
        <div className="flex h-16 items-center px-5">
          <Brand />
        </div>
        <nav className="flex-1 overflow-y-auto px-3 pb-4">
          <GroupLabel>Pelada</GroupLabel>
          <div className="space-y-0.5">{pelada.map((i) => <SideLink key={i.to} item={i} />)}</div>
          {admin && gestao.length > 0 && (
            <>
              <GroupLabel admin>Gestão</GroupLabel>
              <div className="space-y-0.5">{gestao.map((i) => <SideLink key={i.to} item={i} />)}</div>
            </>
          )}
          {superadmin && (
            <>
              <GroupLabel admin>Superadmin</GroupLabel>
              <div className="space-y-0.5">{SUPER.map((i) => <SideLink key={i.to} item={i} />)}</div>
            </>
          )}
        </nav>
        <div className="flex items-center gap-1 border-t border-line p-3">
          <AccountChip />
          <NotificationBell />
          {themeButton}
          <button onClick={logout} aria-label="Sair" title="Sair" className="press grid h-11 w-11 place-items-center rounded-btn text-muted hover:bg-soft hover:text-ink">
            <LogOut size={19} strokeWidth={ICON_STROKE} />
          </button>
        </div>
      </aside>

      {/* ---------------- Cabeçalho compacto (celular) ---------------- */}
      <header
        className={cx(
          'sticky top-0 z-header flex h-14 items-center justify-between gap-2 border-b border-line bg-surface/95 px-4 backdrop-blur lg:hidden',
          inGestao && 'border-t-[3px] border-t-accent',
        )}
      >
        <div className="flex min-w-0 items-center gap-2">
          <img src="/logo-96.webp" width={28} height={28} alt="" aria-hidden className="shrink-0" />
          <span className="truncate font-display text-xl font-bold">{title}</span>
          {inGestao && <span className="rounded-full bg-accent/15 px-2 py-0.5 text-xs font-semibold text-accent-ink">Gestão</span>}
        </div>
        <div className="flex items-center">
          <NotificationBell />
          {themeButton}
        </div>
      </header>

      {/* Faixa da área de gestão (desktop) */}
      {inGestao && (
        <div className="sticky top-0 z-header hidden items-center gap-2 border-b border-line border-t-[3px] border-t-accent bg-surface/95 px-6 py-2 text-sm backdrop-blur lg:flex">
          <ShieldCheck size={16} strokeWidth={ICON_STROKE} className="text-accent-ink" aria-hidden />
          <span className="font-display text-base font-semibold text-accent-ink">Gestão</span>
          <span className="text-muted">— área do administrador</span>
        </div>
      )}

      <main id="conteudo" tabIndex={-1} className="mx-auto w-full min-w-0 max-w-6xl px-4 pb-28 pt-5 outline-none sm:px-6 lg:pb-10 lg:pt-8">
        {/* key por rota: fade + subida curta a cada troca de tela */}
        <div key={pathname} className="anim-page">
          <Suspense fallback={<SkeletonList rows={6} />}>
            <Outlet />
          </Suspense>
        </div>
      </main>

      {/* ---------------- Barra inferior (celular) ---------------- */}
      <nav className="pb-safe fixed inset-x-0 bottom-0 z-nav border-t border-line bg-surface/95 backdrop-blur lg:hidden" aria-label="Navegação principal">
        <ul className="mx-auto grid max-w-lg" style={{ gridTemplateColumns: `repeat(${bottom.length + 1}, minmax(0, 1fr))` }}>
          {bottom.map((item) => {
            const active = isActive(item, pathname)
            return (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className={cx('press flex min-h-[60px] flex-col items-center justify-center gap-0.5 text-[11px] font-medium', active ? 'text-primary-ink' : 'text-muted')}
                >
                  <span className={cx('grid h-7 w-12 place-items-center rounded-full transition-colors', active && 'bg-primary/15')}>
                    <item.icon size={21} strokeWidth={active ? 2.25 : ICON_STROKE} aria-hidden />
                  </span>
                  {item.label}
                </NavLink>
              </li>
            )
          })}
          <li>
            <button
              onClick={() => setMoreOpen(true)}
              aria-haspopup="dialog"
              className={cx(
                'press flex min-h-[60px] w-full flex-col items-center justify-center gap-0.5 text-[11px] font-medium',
                inGestao || pathname.startsWith('/jogadores') || pathname === '/minha-area' || pathname === '/conta' ? 'text-primary-ink' : 'text-muted',
              )}
            >
              <span className="grid h-7 w-12 place-items-center rounded-full">
                <MoreHorizontal size={21} strokeWidth={ICON_STROKE} aria-hidden />
              </span>
              Mais
            </button>
          </li>
        </ul>
      </nav>

      {/* "Mais" (celular): bottom sheet com o restante da navegação */}
      <Modal open={moreOpen} onClose={() => setMoreOpen(false)} title="Mais">
        <div className="space-y-1">
          {PELADA.slice(4).filter((i) => !isHidden(i.to)).map((i) => <SideLink key={i.to} item={i} onNavigate={() => setMoreOpen(false)} />)}
          <SideLink item={{ to: '/conta', label: 'Minha conta', icon: KeyRound }} onNavigate={() => setMoreOpen(false)} />
          {admin && gestao.length > 0 && (
            <>
              <GroupLabel admin>Gestão</GroupLabel>
              {gestao.map((i) => <SideLink key={i.to} item={i} onNavigate={() => setMoreOpen(false)} />)}
            </>
          )}
          {superadmin && (
            <>
              <GroupLabel admin>Superadmin</GroupLabel>
              {SUPER.map((i) => <SideLink key={i.to} item={i} onNavigate={() => setMoreOpen(false)} />)}
            </>
          )}
          <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{user?.name}</p>
              <p className="text-xs text-muted">{user && roleLabel[user.role]} · tema {themeNames[theme]}</p>
            </div>
            <div className="flex">
              {themeButton}
              <button onClick={logout} className="press flex min-h-[44px] items-center gap-2 rounded-btn px-3 text-sm font-medium text-danger-ink hover:bg-danger/10">
                <LogOut size={18} strokeWidth={ICON_STROKE} aria-hidden /> Sair
              </button>
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
