import { NavLink, Outlet } from 'react-router-dom'
import { WorkspaceProvider } from '../contexts/WorkspaceContext'
import { WorkspaceSelector } from './WorkspaceSelector'

export function Layout() {
  return (
    <WorkspaceProvider>
      <div style={{ display: 'flex', height: '100vh' }}>
        <aside style={{ width: 220, padding: 20, borderRight: '1px solid #eee' }}>
          <h1>Trend Scout</h1>
          <nav style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <NavLink to="/sources">Sources</NavLink>
            <NavLink to="/scans">Scans</NavLink>
            <NavLink to="/reports">Reports</NavLink>
            <NavLink to="/trends">Trends</NavLink>
            <NavLink to="/settings">Settings</NavLink>
            <NavLink to="/team">Team</NavLink>
          </nav>
        </aside>
        <main style={{ flex: 1, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
            <WorkspaceSelector />
          </div>
          <Outlet />
        </main>
      </div>
    </WorkspaceProvider>
  )
}

