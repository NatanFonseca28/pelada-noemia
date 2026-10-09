import { lazy, type ComponentType } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireAuth } from '@/auth/RequireAuth'
import { RequirePage, RequireSuperadmin } from '@/auth/RequirePage'
import { Layout } from '@/components/Layout'
import { LoginPage } from '@/pages/LoginPage'
import { ForgotPasswordPage, ResetPasswordPage } from '@/pages/PasswordResetPages'
import { RegisterPage } from '@/pages/RegisterPage'

// Rotas carregadas sob demanda (o Suspense fica no Layout, com skeleton)
const named = <T extends string>(loader: () => Promise<Record<T, ComponentType>>, name: T) =>
  lazy(() => loader().then((m) => ({ default: m[name] })))

const HomePage = named(() => import('@/pages/pelada/HomePage'), 'HomePage')
const RoundViewPage = named(() => import('@/pages/pelada/RoundViewPage'), 'RoundViewPage')
const PlayersListPage = named(() => import('@/pages/pelada/PlayersListPage'), 'PlayersListPage')
const PlayerProfilePage = named(() => import('@/pages/pelada/PlayerProfilePage'), 'PlayerProfilePage')
const StatsPage = named(() => import('@/pages/pelada/StatsPage'), 'StatsPage')
const TournamentPage = named(() => import('@/pages/pelada/TournamentPage'), 'TournamentPage')
const LatestTournamentPage = named(() => import('@/pages/pelada/TournamentPage'), 'LatestTournamentPage')
const MyAreaPage = named(() => import('@/pages/pelada/MyAreaPage'), 'MyAreaPage')
const TransparencyPage = named(() => import('@/pages/pelada/TransparencyPage'), 'TransparencyPage')
const AccountPage = named(() => import('@/pages/AccountPage'), 'AccountPage')
const DashboardPage = named(() => import('@/pages/gestao/DashboardPage'), 'DashboardPage')
const RoundsPage = named(() => import('@/pages/gestao/RoundsPage'), 'RoundsPage')
const RoundPage = named(() => import('@/pages/gestao/RoundPage'), 'RoundPage')
const AttendancePage = named(() => import('@/pages/gestao/AttendancePage'), 'AttendancePage')
const PlayersAdminPage = named(() => import('@/pages/gestao/PlayersAdminPage'), 'PlayersAdminPage')
const UsersPage = named(() => import('@/pages/gestao/UsersPage'), 'UsersPage')
const FinancePage = named(() => import('@/pages/gestao/FinancePage'), 'FinancePage')
const SettingsPage = named(() => import('@/pages/gestao/SettingsPage'), 'SettingsPage')
const AuditPage = named(() => import('@/pages/gestao/AuditPage'), 'AuditPage')
const ChargeMessagePage = named(() => import('@/pages/gestao/ChargeMessagePage'), 'ChargeMessagePage')
const AccessLogPage = named(() => import('@/pages/gestao/AccessLogPage'), 'AccessLogPage')
const PageVisibilityPage = named(() => import('@/pages/gestao/PageVisibilityPage'), 'PageVisibilityPage')
const ExportPage = named(() => import('@/pages/gestao/ExportPage'), 'ExportPage')
const DesignSystemPage = lazy(() => import('@/pages/DesignSystemPage'))
const PrivacyPage = named(() => import('@/pages/LegalPages'), 'PrivacyPage')
const TermsPage = named(() => import('@/pages/LegalPages'), 'TermsPage')
const DataDeletionPage = named(() => import('@/pages/LegalPages'), 'DataDeletionPage')

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/cadastro" element={<RegisterPage />} />
      <Route path="/esqueci-senha" element={<ForgotPasswordPage />} />
      <Route path="/redefinir-senha" element={<ResetPasswordPage />} />
      {/* públicas (sem login): exigidas pela Meta para o WhatsApp oficial */}
      <Route path="/privacidade" element={<PrivacyPage />} />
      <Route path="/termos" element={<TermsPage />} />
      <Route path="/exclusao-de-dados" element={<DataDeletionPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="conta" element={<AccountPage />} />
          <Route element={<RequirePage />}>
          <Route path="rodada" element={<RoundViewPage />} />
          <Route path="jogadores" element={<PlayersListPage />} />
          <Route path="jogadores/:id" element={<PlayerProfilePage />} />
          <Route path="estatisticas" element={<StatsPage />} />
          <Route path="minha-area" element={<MyAreaPage />} />
          <Route path="transparencia" element={<TransparencyPage />} />
          <Route path="campeonato" element={<LatestTournamentPage />} />
          <Route path="campeonato/:id" element={<TournamentPage />} />
          <Route path="gestao" element={<RequireAuth roles={['ADMIN']} />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="rodadas" element={<RoundsPage />} />
            <Route path="rodadas/:id" element={<RoundPage />} />
            <Route path="presenca" element={<AttendancePage />} />
            <Route path="jogadores" element={<PlayersAdminPage />} />
            <Route path="usuarios" element={<UsersPage />} />
            <Route path="financeiro" element={<FinancePage />} />
            <Route path="configuracoes" element={<SettingsPage />} />
            <Route path="exportar" element={<ExportPage />} />
            <Route element={<RequireSuperadmin />}>
              <Route path="auditoria" element={<AuditPage />} />
              <Route path="acessos" element={<AccessLogPage />} />
              <Route path="visibilidade" element={<PageVisibilityPage />} />
              <Route path="mensagem-cobranca" element={<ChargeMessagePage />} />
              <Route path="design" element={<DesignSystemPage />} />
            </Route>
          </Route>
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
