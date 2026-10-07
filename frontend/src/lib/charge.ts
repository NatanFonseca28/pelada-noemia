import type { Delinquent } from '@/api/types'
import { monthAbbr, money } from './labels'

export interface ChargeContext {
  pixKey: string | null
  monthlyFee: string | number
  /** primeiro nome de quem está cobrando */
  gestor: string
}

const monthsText = (months: string[]) => {
  const names = months.map((m) => monthAbbr[Number(m.slice(5, 7)) - 1])
  return names.length > 1 ? `${names.slice(0, -1).join(', ')} e ${names[names.length - 1]}` : names.join('')
}

/** Valores de cada variável para um inadimplente (mesmos nomes da tela de configuração). */
export function chargeValues(d: Pick<Delinquent, 'name' | 'months_due' | 'amount_due'>, ctx: ChargeContext): Record<string, string> {
  return {
    nome: d.name,
    meses: monthsText(d.months_due),
    valor: money(d.amount_due),
    mensalidade: money(ctx.monthlyFee),
    pix: ctx.pixKey || '(peça a chave Pix)',
    gestor: ctx.gestor,
  }
}

/** Troca {variavel} pelo valor; variável desconhecida fica como está (a API já impede salvar). */
export const renderChargeMessage = (template: string, values: Record<string, string>) =>
  template.replace(/\{([^{}]+)\}/g, (all, name: string) => values[name] ?? all)

/** Link que abre a conversa no WhatsApp do aparelho de quem clicou, com a mensagem já escrita. */
export const whatsappChargeLink = (phoneE164: string, text: string) =>
  `https://wa.me/${phoneE164.replace(/\D/g, '')}?text=${encodeURIComponent(text)}`

/** "hoje", "ontem", "há 3 dias" */
export function since(iso: string): string {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000)
  return days <= 0 ? 'hoje' : days === 1 ? 'ontem' : `há ${days} dias`
}

export const chargedRecently = (iso: string | null, days = 3) =>
  !!iso && Date.now() - new Date(iso).getTime() < days * 86_400_000
