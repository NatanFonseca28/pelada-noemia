/** @type {import('tailwindcss').Config} */
// Tokens semânticos. Valores em src/index.css (:root = claro, .dark = escuro), como canais RGB.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: token('bg'),
        surface: token('surface'),
        soft: token('soft'),
        ink: token('ink'),
        muted: token('muted'),
        line: token('line'),
        primary: { DEFAULT: token('primary'), ink: token('primary-ink'), on: token('on-primary') },
        accent: { DEFAULT: token('accent'), ink: token('accent-ink'), on: token('on-accent') },
        danger: { DEFAULT: token('danger'), ink: token('danger-ink'), on: token('on-danger') },
        // tipo de jogador: sempre o mesmo par em todo o app (azul = mensalista, laranja = diarista)
        mensalista: token('mensalista'),
        diarista: token('diarista'),
        ok: { DEFAULT: token('ok'), ink: token('primary-ink') },
        board: { DEFAULT: token('board'), ink: token('board-ink') },
        // exclusivos de cartões
        'card-yellow': token('card-yellow'),
        'card-red': token('card-red'),
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Barlow Condensed"', 'Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        // escala: 12 / 14 / 16 / 20 / 28 / 40 / 64 / 96
        score: ['4rem', { lineHeight: '1', fontWeight: '800' }],
        'score-xl': ['6rem', { lineHeight: '0.9', fontWeight: '800' }],
      },
      borderRadius: { card: '14px', btn: '12px' },
      boxShadow: { card: 'var(--shadow-card)' },
      zIndex: { header: '30', nav: '40', sheet: '50', toast: '60' },
      transitionTimingFunction: { pitch: 'cubic-bezier(.2,.8,.2,1)' },
      transitionDuration: { 160: '160ms', 220: '220ms' },
    },
  },
  plugins: [],
}
