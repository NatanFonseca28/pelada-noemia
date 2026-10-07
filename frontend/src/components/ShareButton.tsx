import { Share2 } from 'lucide-react'
import { ICON_STROKE, cx } from './ui'
import { shareText } from '@/lib/share'

/** Compartilha um texto pronto (abre o WhatsApp ou o menu de compartilhar do celular). */
export function ShareButton({ text, label = 'Compartilhar', className }: { text: () => string; label?: string; className?: string }) {
  return (
    <button
      type="button"
      onClick={() => void shareText(text())}
      className={cx('press inline-flex min-h-[44px] items-center gap-1.5 rounded-btn px-3 text-sm font-medium text-primary-ink hover:bg-soft', className)}
    >
      <Share2 size={16} strokeWidth={ICON_STROKE} aria-hidden /> {label}
    </button>
  )
}
