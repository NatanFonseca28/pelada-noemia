import { useEffect, useState } from 'react'
import { CloudOff, CloudUpload, Download, RefreshCw, TriangleAlert } from 'lucide-react'
import { useAuth } from '@/auth/AuthProvider'
import { Button, ICON_STROKE, Modal, cx } from '@/components/ui'
import { useOnline, usePendingCount } from '@/hooks/useSheetQueue'
import { syncNow, useSyncState } from '@/lib/offline/syncStore'
import { backupJson, discardFailed, onQueueChange, readFailed, readQueue, type FailedOp, type SheetOp } from '@/lib/offlineQueue'

const describe = (op: SheetOp): string => {
  switch (op.kind) {
    case 'add': return `Lance da partida ${op.matchId}`
    case 'remove': return `Lance removido (partida ${op.matchId})`
    case 'result': return `Resultado ${op.body.home_score} × ${op.body.away_score} (partida ${op.matchId})`
    case 'reopen': return `Reabertura da partida ${op.matchId}`
    case 'add_match': return `Próxima partida (nº ${op.seq})`
    case 'finish_casual': return 'Encerrar a pelada da noite'
    case 'checkin': return `Chamada do jogador ${op.playerId}`
    case 'checkin_all': return 'Chamada: todos presentes'
  }
}

function downloadBackup() {
  const url = URL.createObjectURL(new Blob([backupJson()], { type: 'application/json' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `pelada-backup-${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Faixa de estado do modo offline: sem internet, ações guardadas, sincronizando, servidor acordando
 * e ações que o servidor não aceitou. Some quando está tudo em dia.
 */
export function SyncBanner() {
  const online = useOnline()
  const pending = usePendingCount()
  const sync = useSyncState()
  const { offline: sessionOffline } = useAuth()
  const [failed, setFailed] = useState<FailedOp[]>(readFailed)
  const [open, setOpen] = useState(false)
  const [tick, setTick] = useState(0)
  useEffect(() => onQueueChange(() => setFailed(readFailed())), [])
  useEffect(() => {
    if (sync.nextTryAt == null) return
    const t = window.setInterval(() => setTick((n) => n + 1), 1000)
    return () => window.clearInterval(t)
  }, [sync.nextTryAt])
  void tick

  const seconds = sync.nextTryAt ? Math.max(0, Math.round((sync.nextTryAt - Date.now()) / 1000)) : 0
  let tone = 'bg-soft text-ink'
  let icon = <CloudUpload size={16} strokeWidth={ICON_STROKE} aria-hidden />
  let text: string | null = null

  if (!online) {
    tone = 'bg-accent/20 text-ink'
    icon = <CloudOff size={16} strokeWidth={ICON_STROKE} aria-hidden />
    text = pending ? `Sem internet · ${pending} ${pending > 1 ? 'ações guardadas' : 'ação guardada'} neste celular` : 'Sem internet · o app continua funcionando e guarda o que você fizer'
  } else if (sync.phase === 'login') {
    tone = 'bg-danger/10 text-danger-ink'
    icon = <TriangleAlert size={16} strokeWidth={ICON_STROKE} aria-hidden />
    text = `Entre novamente para enviar ${pending} ${pending > 1 ? 'ações guardadas' : 'ação guardada'}`
  } else if (pending && sync.phase === 'syncing') {
    icon = <RefreshCw size={16} strokeWidth={ICON_STROKE} className="animate-spin" aria-hidden />
    text = `Enviando ${pending} ${pending > 1 ? 'ações guardadas' : 'ação guardada'}…`
  } else if (pending && sync.phase === 'waking') {
    icon = <RefreshCw size={16} strokeWidth={ICON_STROKE} className="animate-spin" aria-hidden />
    text = 'Servidor acordando… (pode levar até 1 minuto). Suas ações estão guardadas.'
  } else if (pending && sync.phase === 'waiting') {
    tone = 'bg-accent/20 text-ink'
    icon = <CloudOff size={16} strokeWidth={ICON_STROKE} aria-hidden />
    text = `Servidor fora do ar · ${pending} ${pending > 1 ? 'ações guardadas' : 'ação guardada'} · nova tentativa em ${seconds}s`
  } else if (pending) {
    text = `${pending} ${pending > 1 ? 'ações guardadas' : 'ação guardada'} para enviar`
  } else if (sessionOffline) {
    tone = 'bg-accent/20 text-ink'
    icon = <CloudOff size={16} strokeWidth={ICON_STROKE} aria-hidden />
    text = 'Sem conexão com o servidor · usando os dados guardados neste celular'
  }
  if (failed.length) {
    tone = 'bg-danger/10 text-danger-ink'
    icon = <TriangleAlert size={16} strokeWidth={ICON_STROKE} aria-hidden />
    text = `${failed.length} ${failed.length > 1 ? 'ações não foram aceitas' : 'ação não foi aceita'} pelo servidor${text ? ` · ${text}` : ''}`
  }
  if (!text) return null

  return (
    <>
      <div role="status" className={cx('flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-line px-4 py-1.5 text-sm', tone)}>
        <span className="flex min-w-0 flex-1 items-center gap-2">{icon}<span>{text}</span></span>
        {pending > 0 && online && <button type="button" onClick={syncNow} className="font-medium underline">Enviar agora</button>}
        {(pending > 0 || failed.length > 0) && <button type="button" onClick={() => setOpen(true)} className="font-medium underline">Detalhes</button>}
      </div>
      <Modal open={open} onClose={() => setOpen(false)} title="Ações guardadas neste celular">
        <div className="space-y-4 text-sm">
          {readQueue().length > 0 && (
            <div>
              <h3 className="mb-1 font-semibold">Aguardando envio ({readQueue().length})</h3>
              <ul className="list-inside list-disc text-muted">{readQueue().map((o, i) => <li key={i}>{describe(o)}</li>)}</ul>
            </div>
          )}
          {failed.length > 0 && (
            <div>
              <h3 className="mb-1 font-semibold text-danger-ink">Não aceitas pelo servidor ({failed.length})</h3>
              <ul className="space-y-2">
                {failed.map((f, i) => (
                  <li key={i} className="rounded-btn border border-line p-2">
                    <p className="font-medium">{describe(f.op)}</p>
                    <p className="text-muted">{f.reason}</p>
                    <Button size="sm" variant="ghost" onClick={() => discardFailed(i)}>Descartar</Button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <Button variant="secondary" onClick={downloadBackup}><Download size={16} strokeWidth={ICON_STROKE} aria-hidden /> Baixar cópia de segurança (.json)</Button>
        </div>
      </Modal>
    </>
  )
}
