import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

export type Theme = 'light' | 'dark' | 'system'

const ThemeContext = createContext<{ theme: Theme; setTheme: (t: Theme) => void }>({
  theme: 'dark',
  setTheme: () => {},
})

function readTheme(): Theme {
  try {
    return (localStorage.getItem('theme') as Theme) || 'dark' // escuro é o padrão
  } catch {
    return 'dark'
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(readTheme)

  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)')
    const apply = () =>
      document.documentElement.classList.toggle('dark', theme === 'dark' || (theme === 'system' && media.matches))
    apply()
    try {
      localStorage.setItem('theme', theme)
    } catch {
      /* armazenamento indisponível */
    }
    media.addEventListener('change', apply)
    return () => media.removeEventListener('change', apply)
  }, [theme])

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
}

export const useTheme = () => useContext(ThemeContext)
