import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '@/components/ui'

/** Páginas públicas (sem login) exigidas pela Meta para o WhatsApp oficial: privacidade, termos e exclusão de dados. */

const CONTACT = 'natanfs28@yahoo.com.br'
const UPDATED = '9 de outubro de 2026'

function LegalLayout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-screen bg-bg px-4 py-8">
      <Card className="anim-page mx-auto max-w-3xl p-6 sm:p-8">
        <div className="mb-6 flex items-center gap-3">
          <img src="/logo-96.webp" width={48} height={48} alt="Noemia Cup" />
          <div>
            <p className="text-sm text-muted">Pelada de Quarta — Noemia Cup</p>
            <h1 className="font-display text-3xl font-bold leading-tight">{title}</h1>
          </div>
        </div>
        <div className="space-y-4 text-sm leading-relaxed [&_h2]:mt-6 [&_h2]:font-display [&_h2]:text-xl [&_h2]:font-bold [&_li]:ml-5 [&_li]:list-disc [&_a]:text-primary-ink [&_a]:underline">
          {children}
          <p className="pt-4 text-xs text-muted">Atualizado em {UPDATED}.</p>
        </div>
        <nav className="mt-6 flex flex-wrap gap-4 border-t border-line pt-4 text-sm">
          <Link to="/privacidade" className="text-primary-ink hover:underline">Privacidade</Link>
          <Link to="/termos" className="text-primary-ink hover:underline">Termos de uso</Link>
          <Link to="/exclusao-de-dados" className="text-primary-ink hover:underline">Exclusão de dados</Link>
          <Link to="/login" className="ml-auto text-muted hover:underline">Entrar no app</Link>
        </nav>
      </Card>
    </div>
  )
}

const Contact = () => <a href={`mailto:${CONTACT}`}>{CONTACT}</a>

export function PrivacyPage() {
  return (
    <LegalLayout title="Política de Privacidade">
      <p>
        Este aplicativo organiza a Pelada de Quarta (Noemia Cup): presença, sorteio de times, campeonato, estatísticas e
        mensalidades. O responsável pelos dados é o organizador da pelada, Natan Fonseca, contato: <Contact />.
      </p>
      <h2>Quais dados guardamos</h2>
      <ul>
        <li>Cadastro: nome, apelido, foto (opcional), e-mail de acesso e telefone celular.</li>
        <li>Pelada: presenças, times, posições e avaliações usadas no sorteio, gols, cartões e estatísticas.</li>
        <li>Financeiro: mensalidades e pagamentos registrados pelos administradores.</li>
        <li>WhatsApp: mensagens de cobrança enviadas, respostas do jogador ao chatbot e comprovantes enviados por ele.</li>
        <li>Segurança: registros de acesso (data, hora e endereço IP) para proteger as contas.</li>
      </ul>
      <h2>Para que usamos</h2>
      <ul>
        <li>Organizar as partidas e mostrar times, resultados e estatísticas aos participantes.</li>
        <li>Controlar mensalidades e enviar lembretes de cobrança pelo WhatsApp, só para quem autorizou.</li>
        <li>Responder às mensagens do jogador (por exemplo, enviar o Pix ou registrar um pagamento para conferência).</li>
      </ul>
      <p>Não vendemos dados nem os usamos para publicidade.</p>
      <h2>Com quem compartilhamos</h2>
      <p>
        Só com os serviços necessários para o app funcionar: hospedagem (Vercel e Render), banco de dados (Neon) e o
        WhatsApp Business Platform da Meta, que entrega as mensagens. Telefones e dados financeiros são visíveis apenas
        aos administradores da pelada.
      </p>
      <h2>Por quanto tempo</h2>
      <p>
        Enquanto a pessoa participar da pelada. Dados financeiros podem ser mantidos pelo tempo necessário para a
        prestação de contas do grupo. Após um pedido de exclusão, apagamos ou anonimizamos os dados em até 15 dias.
      </p>
      <h2>Seus direitos (LGPD)</h2>
      <p>
        Você pode pedir acesso, correção, exclusão dos seus dados ou deixar de receber mensagens pelo WhatsApp a qualquer
        momento, pelo e-mail <Contact /> ou falando com um administrador. Para parar as cobranças pelo WhatsApp, basta
        também responder "parar" na conversa. Veja como pedir a exclusão em{' '}
        <Link to="/exclusao-de-dados">Exclusão de dados</Link>.
      </p>
    </LegalLayout>
  )
}

export function TermsPage() {
  return (
    <LegalLayout title="Termos de Uso">
      <p>
        O app é de uso interno dos participantes da Pelada de Quarta (Noemia Cup), sem fins comerciais. Ao usá-lo, você
        concorda com estes termos e com a <Link to="/privacidade">Política de Privacidade</Link>.
      </p>
      <h2>Contas</h2>
      <ul>
        <li>O acesso é pessoal; não compartilhe sua senha.</li>
        <li>Os administradores podem aprovar, suspender ou remover contas e corrigir informações da pelada.</li>
      </ul>
      <h2>Mensalidades e cobranças</h2>
      <ul>
        <li>Valores e regras de pagamento são definidos pelo grupo; o app apenas registra e lembra.</li>
        <li>Mensagens de cobrança pelo WhatsApp só são enviadas a quem autorizou e por decisão de um administrador.</li>
        <li>Um pagamento só conta como quitado depois que um administrador confere e confirma.</li>
      </ul>
      <h2>Uso adequado</h2>
      <p>Não use o app para enviar conteúdo ofensivo ou para fins diferentes da organização da pelada.</p>
      <h2>Contato</h2>
      <p>Dúvidas: <Contact />.</p>
    </LegalLayout>
  )
}

export function DataDeletionPage() {
  return (
    <LegalLayout title="Exclusão de dados">
      <p>Você pode pedir a exclusão dos seus dados a qualquer momento:</p>
      <ul>
        <li>Envie um e-mail para <Contact /> com o assunto "Exclusão de dados", informando seu nome e o telefone cadastrado.</li>
        <li>Ou peça diretamente a um administrador da pelada.</li>
      </ul>
      <p>
        Confirmamos o pedido e, em até 15 dias, apagamos seu cadastro, telefone, foto, respostas ao chatbot e
        comprovantes. Registros financeiros e resultados de partidas podem ser mantidos de forma anonimizada (sem seu
        nome ou telefone) para a prestação de contas do grupo.
      </p>
      <p>
        Para apenas deixar de receber mensagens pelo WhatsApp, sem apagar o cadastro, responda "parar" na conversa ou
        peça a um administrador.
      </p>
    </LegalLayout>
  )
}
