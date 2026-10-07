/** Tela de último recurso se algo quebrar de vez (o erro já foi para o Sentry). */
export function FatalError() {
  return (
    <div className="grid min-h-screen place-items-center bg-bg p-6 text-center text-ink">
      <div>
        <p className="font-display text-2xl font-bold">Algo deu errado nesta tela</p>
        <p className="mt-1 text-sm text-muted">O problema foi registrado. Recarregue a página para continuar.</p>
        <button className="press mt-4 min-h-[44px] rounded-btn bg-primary px-4 font-medium text-primary-on" onClick={() => window.location.reload()}>
          Recarregar
        </button>
      </div>
    </div>
  )
}
