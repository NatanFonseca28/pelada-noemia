import { useState, type FormEvent } from 'react'
import { Phone, ShieldCheck } from 'lucide-react'
import { ApiError } from '@/api/client'
import { useDeletePlayer, usePlayerPhoto, usePlayers, useSavePlayer } from '@/api/queries'
import type { Player, PlayerInput, PlayerType, Position } from '@/api/types'
import { Alert, Avatar, Badge, Button, Card, EmptyState, Field, ICON_STROKE, Modal, PageHeader, Spinner, TypeBadge } from '@/components/ui'
import { playerTypeLabel, positionLabel, positionShort } from '@/lib/labels'
import { formatPhone, maskPhone } from '@/lib/phone'

const POSITIONS: Position[] = ['ZAGUEIRO', 'ALA', 'ATACANTE', 'GOLEIRO_FIXO']
const EMPTY: PlayerInput = {
  name: '',
  nickname: null,
  type: 'MENSALISTA',
  primary_position: 'ZAGUEIRO',
  secondary_position: null,
  skill_level: null,
  active: true,
  phone: null,
  whatsapp_opt_in: false,
}

function PlayerForm({ player, onDone }: { player: Player | null; onDone: () => void }) {
  const [form, setForm] = useState<PlayerInput>(player ? { ...player, phone: formatPhone(player.phone) || null } : EMPTY)
  const [phoneError, setPhoneError] = useState<string | undefined>()
  const needsPosition = !form.primary_position
  const [photo, setPhoto] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  const save = useSavePlayer()
  const uploadPhoto = usePlayerPhoto()
  const isGk = form.primary_position === 'GOLEIRO_FIXO'

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setPhoneError(undefined)
    try {
      // telefone vai como digitado; a API valida e grava em E.164 ("" limpa o campo)
      const data = { ...form, nickname: form.nickname?.trim() || null, secondary_position: isGk ? null : form.secondary_position, phone: form.phone?.trim() ?? '' }
      const saved = await save.mutateAsync({ id: player?.id, data })
      if (photo) await uploadPhoto.mutateAsync({ id: saved.id, file: photo })
      onDone()
    } catch (err) {
      const phoneMsg = err instanceof ApiError ? err.errors?.find((e) => e.field === 'phone')?.message : undefined
      if (phoneMsg) setPhoneError(phoneMsg)
      else setError(err instanceof ApiError ? err.message : 'Erro ao salvar')
    }
  }

  async function removePhoto() {
    if (!player) return
    await uploadPhoto.mutateAsync({ id: player.id, file: null })
    onDone()
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      {error && <Alert>{error}</Alert>}
      <Field label="Nome completo">
        <input className="input" required minLength={2} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
      </Field>
      <Field label="Apelido">
        <input className="input" value={form.nickname ?? ''} onChange={(e) => setForm({ ...form, nickname: e.target.value })} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Tipo">
          {/* Goleiro fixo é sempre isento (regra também garantida pela API) */}
          <select className="input" value={isGk ? 'ISENTO' : form.type} disabled={isGk} onChange={(e) => setForm({ ...form, type: e.target.value as PlayerType })}>
            {((isGk ? ['ISENTO'] : ['MENSALISTA', 'DIARISTA']) as PlayerType[]).map((t) => (
              <option key={t} value={t}>{t === 'ISENTO' ? 'Isento (goleiro)' : playerTypeLabel[t]}</option>
            ))}
          </select>
        </Field>
        <Field label="Nível técnico">
          <select
            className="input"
            value={form.skill_level ?? ''}
            onChange={(e) => setForm({ ...form, skill_level: e.target.value ? Number(e.target.value) : null })}
          >
            <option value="">Não informado</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>{'★'.repeat(n)}</option>
            ))}
          </select>
        </Field>
        <Field label="Posição principal">
          <select
            className="input"
            required
            value={form.primary_position ?? ''}
            onChange={(e) => {
              const primary = e.target.value as Position
              setForm({
                ...form,
                primary_position: primary,
                secondary_position: form.secondary_position === primary ? null : form.secondary_position,
                // saiu do gol: deixa de ser isento (mensalista por padrão; dá para trocar)
                type: primary === 'GOLEIRO_FIXO' ? 'ISENTO' : form.type === 'ISENTO' ? 'MENSALISTA' : form.type,
              })
            }}
          >
            {needsPosition && <option value="" disabled>Selecione</option>}
            {POSITIONS.map((p) => (
              <option key={p} value={p}>{positionLabel[p]}</option>
            ))}
          </select>
        </Field>
        <Field label="Posição secundária">
          <select
            className="input"
            disabled={isGk}
            value={isGk ? '' : form.secondary_position ?? ''}
            onChange={(e) => setForm({ ...form, secondary_position: (e.target.value || null) as Position | null })}
          >
            <option value="">Nenhuma</option>
            {POSITIONS.filter((p) => p !== 'GOLEIRO_FIXO' && p !== form.primary_position).map((p) => (
              <option key={p} value={p}>{positionLabel[p]}</option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Foto" hint="JPG, PNG ou WEBP até 3 MB">
        <div className="flex items-center gap-3">
          <Avatar name={form.name || '?'} url={photo ? URL.createObjectURL(photo) : player?.photo_url} size={48} />
          <input type="file" accept="image/jpeg,image/png,image/webp" className="text-sm" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
          {player?.photo_url && !photo && (
            <Button type="button" variant="ghost" size="sm" onClick={removePhoto}>Remover</Button>
          )}
        </div>
      </Field>
      <fieldset className="space-y-3 rounded-btn border border-line p-3">
        <legend className="flex items-center gap-1.5 px-1 text-sm font-medium text-ink">
          <ShieldCheck size={14} strokeWidth={ICON_STROKE} className="text-accent-ink" aria-hidden /> Contato
        </legend>
        <Field label="WhatsApp" hint="Com DDD" error={phoneError}>
          <input
            className="input"
            type="tel"
            inputMode="tel"
            autoComplete="off"
            placeholder="(21) 98765-4321"
            value={form.phone ?? ''}
            onChange={(e) => setForm({ ...form, phone: maskPhone(e.target.value) })}
          />
        </Field>
        <label className="flex min-h-[44px] items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 accent-primary"
            checked={form.whatsapp_opt_in}
            disabled={!form.phone}
            onChange={(e) => setForm({ ...form, whatsapp_opt_in: e.target.checked })}
          />
          Aceita receber cobrança por WhatsApp
        </label>
      </fieldset>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4 accent-primary" checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
        Ativo
      </label>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onDone}>Cancelar</Button>
        <Button type="submit" loading={save.isPending || uploadPhoto.isPending}>Salvar</Button>
      </div>
    </form>
  )
}

export function PlayersAdminPage() {
  const [q, setQ] = useState('')
  const [showInactive, setShowInactive] = useState(false)
  const [editing, setEditing] = useState<Player | null | undefined>(undefined)
  const [feedback, setFeedback] = useState<{ kind: 'error' | 'success'; text: string } | null>(null)
  const { data, isLoading } = usePlayers({ q: q || undefined, active: showInactive ? undefined : true })
  const del = useDeletePlayer()

  async function onDelete(p: Player) {
    if (!confirm(`Excluir ${p.display_name}? Essa ação não pode ser desfeita.`)) return
    try {
      await del.mutateAsync(p.id)
      setFeedback({ kind: 'success', text: 'Jogador excluído.' })
    } catch (err) {
      setFeedback({ kind: 'error', text: err instanceof ApiError ? err.message : 'Erro ao excluir' })
    }
  }

  const counts = (data ?? []).reduce<Record<string, number>>((acc, p) => {
    const key = p.primary_position ?? 'SEM'
    acc[key] = (acc[key] ?? 0) + 1
    return acc
  }, {})

  return (
    <>
      <PageHeader
        title="Jogadores"
        actions={<Button onClick={() => setEditing(null)}>+ Novo jogador</Button>}
      />
      {feedback && <div className="mb-4"><Alert kind={feedback.kind}>{feedback.text}</Alert></div>}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <input className="input max-w-xs" placeholder="Buscar" value={q} onChange={(e) => setQ(e.target.value)} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" className="accent-primary" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Mostrar inativos
        </label>
        <div className="flex gap-1">
          {POSITIONS.map((p) => (
            <Badge key={p}>{positionShort[p]}: {counts[p] ?? 0}</Badge>
          ))}
          {counts.SEM ? <Badge color="yellow">A definir: {counts.SEM}</Badge> : null}
        </div>
      </div>

      {isLoading ? (
        <Spinner />
      ) : !data?.length ? (
        <EmptyState>Nenhum jogador cadastrado.</EmptyState>
      ) : (
        <Card className="divide-y divide-line">
          {data.map((p) => (
            <div key={p.id} className="flex items-center gap-3 p-3">
              <Avatar name={p.display_name} url={p.photo_url} type={p.type} />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">
                  {p.display_name}
                  {p.nickname && <span className="ml-1 text-sm font-normal text-muted">({p.name})</span>}
                </p>
                <div className="mt-1 flex flex-wrap gap-1">
                  {p.primary_position ? (
                    <Badge color="green">{positionLabel[p.primary_position]}</Badge>
                  ) : (
                    <Badge color="yellow">Posição a definir</Badge>
                  )}
                  {p.secondary_position && <Badge>2ª: {positionLabel[p.secondary_position]}</Badge>}
                  <TypeBadge type={p.type} />
                  {p.skill_level && <Badge>{'★'.repeat(p.skill_level)}</Badge>}
                  {!p.active && <Badge color="red">Inativo</Badge>}
                </div>
                {p.phone && (
                  <p className="mt-1 flex items-center gap-1.5 text-xs text-muted">
                    <Phone size={12} strokeWidth={ICON_STROKE} aria-hidden />
                    <span className="tabular">{formatPhone(p.phone)}</span>
                    {!p.whatsapp_opt_in && <span>· sem consentimento</span>}
                  </p>
                )}
              </div>
              <div className="flex shrink-0 gap-1">
                <Button size="sm" variant="secondary" onClick={() => setEditing(p)}>Editar</Button>
                <Button size="sm" variant="ghost" onClick={() => onDelete(p)} aria-label={`Excluir ${p.display_name}`}>🗑️</Button>
              </div>
            </div>
          ))}
        </Card>
      )}

      <Modal open={editing !== undefined} onClose={() => setEditing(undefined)} title={editing ? 'Editar jogador' : 'Novo jogador'}>
        {editing !== undefined && <PlayerForm key={editing?.id ?? 'new'} player={editing} onDone={() => setEditing(undefined)} />}
      </Modal>
    </>
  )
}
