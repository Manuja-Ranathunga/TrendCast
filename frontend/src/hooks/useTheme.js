import { useCallback, useEffect, useState } from 'react'

// Cycles system -> light -> dark, persisted to localStorage, applied via
// the [data-theme] attribute — same mechanism as the reference app's
// initTheme/applyTheme/setTheme (app.js), ported to a hook so React owns
// the state instead of reading/writing the DOM imperatively.
const THEME_KEY = 'trendcast_theme'
const ORDER = ['system', 'light', 'dark']

function applyTheme(mode) {
  const root = document.documentElement
  if (mode === 'light') root.setAttribute('data-theme', 'light')
  else if (mode === 'dark') root.setAttribute('data-theme', 'dark')
  else root.removeAttribute('data-theme')
}

export function useTheme() {
  const [theme, setThemeState] = useState(() => localStorage.getItem(THEME_KEY) || 'system')

  useEffect(() => {
    applyTheme(theme)
  }, [theme])

  const setTheme = useCallback((mode) => {
    localStorage.setItem(THEME_KEY, mode)
    setThemeState(mode)
  }, [])

  const cycleTheme = useCallback(() => {
    setTheme(ORDER[(ORDER.indexOf(theme) + 1) % ORDER.length])
  }, [theme, setTheme])

  return { theme, cycleTheme }
}
