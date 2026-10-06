// Aplica o tema antes do React (evita "piscar"). Arquivo externo: a CSP de produção proíbe scripts inline.
try {
  var t = localStorage.getItem('theme') || 'dark'
  var dark = t === 'dark' || (t === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', dark)
} catch (e) {
  document.documentElement.classList.add('dark')
}
