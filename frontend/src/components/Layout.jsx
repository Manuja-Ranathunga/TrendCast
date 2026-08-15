import { NavLink, Outlet } from 'react-router-dom'
import { useTheme } from '../hooks/useTheme'

const THEME_LABEL = { system: 'System', light: 'Light', dark: 'Dark' }

export function Layout() {
  const { theme, cycleTheme } = useTheme()

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">T</div>
          <div>
            <div className="brand-name">TrendCast</div>
            <div className="brand-tag">YouTube channel analytics</div>
          </div>
        </div>

        <NavLink to="/" end className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <span className="nav-icon">☰</span> Explorer
        </NavLink>
        <NavLink to="/forecast" className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
          <span className="nav-icon">🔮</span> Forecast
        </NavLink>

        <div className="sidebar-footer">
          <div className="engine-pill">
            <span className="engine-dot" /> Forecast: placeholder model
          </div>
          <button className="theme-toggle" type="button" onClick={cycleTheme}>
            <span>Theme: {THEME_LABEL[theme]}</span> <span>◐</span>
          </button>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
