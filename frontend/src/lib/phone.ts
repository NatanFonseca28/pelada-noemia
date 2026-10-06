/** Máscara progressiva para digitação de telefone brasileiro: "(21) 98765-4321". Com "+", deixa livre (exterior). */
export function maskPhone(input: string): string {
  if (input.trim().startsWith('+')) return input.replace(/[^\d+ ]/g, '').slice(0, 20)
  const d = input.replace(/\D/g, '').slice(0, 11)
  if (d.length <= 2) return d.length ? `(${d}` : ''
  const ddd = d.slice(0, 2)
  const rest = d.slice(2)
  if (rest.length <= 4) return `(${ddd}) ${rest}`
  const split = rest.length === 9 ? 5 : 4
  return `(${ddd}) ${rest.slice(0, split)}-${rest.slice(split)}`
}

/** Exibe o E.164 salvo: +5521987654321 → "(21) 98765-4321"; números estrangeiros ficam como estão. */
export function formatPhone(e164: string | null | undefined): string {
  if (!e164) return ''
  if (!e164.startsWith('+55')) return e164
  return maskPhone(e164.slice(3))
}

/** Link wa.me (abre a conversa no WhatsApp). */
export const whatsappLink = (e164: string) => `https://wa.me/${e164.replace(/\D/g, '')}`
