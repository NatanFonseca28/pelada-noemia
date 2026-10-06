import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from 'react'

/**
 * Campo com label, dica e erro inline. O controle filho recebe id, aria-invalid e
 * aria-describedby automaticamente.
 */
export function Field({ label, error, hint, children }: { label: string; error?: string; hint?: string; children: ReactNode }) {
  const id = useId()
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined
  const control = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        id: (children.props as { id?: string }).id ?? id,
        'aria-invalid': error ? true : undefined,
        'aria-describedby': describedBy,
      })
    : children
  return (
    <div className="space-y-1">
      <label htmlFor={(isValidElement(children) && (children.props as { id?: string }).id) || id} className="block text-sm font-medium text-ink">
        {label}
      </label>
      {control}
      {hint && !error && <p id={`${id}-hint`} className="text-xs text-muted">{hint}</p>}
      {error && <p id={`${id}-error`} className="text-xs font-medium text-danger-ink">{error}</p>}
    </div>
  )
}
