import { useEffect, useRef, useState } from 'react'
import { useChargeMessage, useDelinquents, useFinanceOverview, useSaveChargeMessage } from '@/api/finance'
import { useAuth } from '@/auth/AuthProvider'
import { useToast } from '@/contexts/feedback'
import { Alert, Button, Card, Field, PageHeader, QueryState, SkeletonList, errorMessage } from '@/components/ui'
import { chargeValues, renderChargeMessage } from '@/lib/charge'

const SAMPLE = { name: 'Daniel', months_due: ['2026-09-01', '2026-10-01'], amount_due: '100.00' }

export function ChargeMessagePage() {
  const query = useChargeMessage()
  const save = useSaveChargeMessage()
  const toast = useToast()
  const { user } = useAuth()
  const { data: overview } = useFinanceOverview(new Date().getFullYear())
  const { data: delinquents } = useDelinquents(true)
  const [message, setMessage] = useState('')
  const [pix, setPix] = useState('')
  const [error, setError] = useState<string | null>(null)
  const area = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (query.data) {
      setMessage(query.data.message)
      setPix(query.data.pix_key ?? '')
    }
  }, [query.data])

  const example = delinquents?.[0] ?? SAMPLE
  const values = chargeValues(example, {
    pixKey: pix.trim() || null,
    monthlyFee: overview?.config.monthly_fee ?? '50',
    gestor: user?.name.split(' ')[0] ?? 'Natan',
  })
  const dirty = !!query.data && (message !== query.data.message || pix !== (query.data.pix_key ?? ''))

  /** Insere a variável onde está o cursor. */
  const insert = (name: string) => {
    const el = area.current
    const token = `{${name}}`
    const start = el?.selectionStart ?? message.length
    const end = el?.selectionEnd ?? message.length
    setMessage(message.slice(0, start) + token + message.slice(end))
    requestAnimationFrame(() => {
      el?.focus()
      el?.setSelectionRange(start + token.length, start + token.length)
    })
  }

  const onSave = () => {
    setError(null)
    save.mutate(
      { message, pix_key: pix.trim() || null },
      {
        onSuccess: () => toast({ message: 'Mensagem de cobrança salva', tone: 'success' }),
        onError: (err) => setError(errorMessage(err, 'Não foi possível salvar')),
      },
    )
  }

  return (
    <>
      <PageHeader title="Mensagem de cobrança" actions={<Button onClick={onSave} disabled={!dirty} loading={save.isPending}>Salvar</Button>} />
      <QueryState query={query} skeleton={<SkeletonList rows={6} />}>
        {query.data && (
          <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
            <Card className="space-y-4 p-4">
              {error && <Alert>{error}</Alert>}
              <Field label="Chave Pix" hint="Entra no lugar de {pix}">
                <input className="input" value={pix} maxLength={140} onChange={(e) => setPix(e.target.value)} placeholder="e-mail, telefone, CPF ou chave aleatória" />
              </Field>
              <Field label="Mensagem">
                <textarea ref={area} className="input min-h-[160px] py-2 leading-relaxed" value={message} maxLength={1000} onChange={(e) => setMessage(e.target.value)} />
              </Field>
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-muted">Inserir:</span>
                {query.data.variables.map((v) => (
                  <button key={v.name} type="button" onClick={() => insert(v.name)} className="press min-h-[36px] rounded-full bg-soft px-3 font-mono text-sm hover:bg-primary/15">
                    {`{${v.name}}`}
                  </button>
                ))}
                <Button variant="ghost" size="sm" className="ml-auto" disabled={message === query.data.default_message} onClick={() => setMessage(query.data.default_message)}>
                  Voltar ao texto padrão
                </Button>
              </div>

              <section aria-labelledby="como-usar" className="rounded-btn border border-line p-3">
                <h2 id="como-usar" className="mb-2 font-semibold">Como usar as variáveis</h2>
                <ul className="mb-3 list-disc space-y-1 pl-5 text-sm">
                  <li>Escreva a variável entre chaves, exatamente como na tabela: <code className="font-mono">{'{nome}'}</code>.</li>
                  <li>Na hora de cobrar, cada variável vira o dado daquele jogador.</li>
                  <li>Variável escrita errado (ex.: <code className="font-mono">{'{Nome}'}</code>) impede salvar, e o aviso mostra qual é.</li>
                  <li>Quebras de linha e emojis são mantidos. Limite de 1.000 caracteres.</li>
                </ul>
                <table className="w-full text-sm">
                  <thead className="text-xs text-muted">
                    <tr>
                      <th className="py-1 text-left font-medium">Variável</th>
                      <th className="py-1 text-left font-medium">Vira</th>
                      <th className="py-1 text-left font-medium">Exemplo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.variables.map((v) => (
                      <tr key={v.name} className="border-t border-line">
                        <td className="py-1.5 pr-2 font-mono">{`{${v.name}}`}</td>
                        <td className="py-1.5 pr-2">{v.description}</td>
                        <td className="py-1.5 text-muted">{values[v.name]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            </Card>

            <Card className="h-fit p-4 lg:sticky lg:top-20">
              <h2 className="mb-1 font-semibold">Prévia</h2>
              <p className="mb-3 text-xs text-muted">Como {example.name} vai receber, enviado por {values.gestor}</p>
              <p className="whitespace-pre-wrap rounded-card rounded-tr-none bg-[#d9fdd3] p-3 text-sm text-[#111b21] shadow-card">
                {renderChargeMessage(message, values)}
              </p>
            </Card>
          </div>
        )}
      </QueryState>
    </>
  )
}
