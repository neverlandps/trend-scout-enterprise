import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import api from '../services/api'

export interface Workspace {
  id: string
  team_id: string
  name: string
  is_default: boolean
  created_at: string
  updated_at: string
}

interface WorkspaceContextValue {
  workspaces: Workspace[]
  currentWorkspace: Workspace | null
  loading: boolean
  error: string | null
  switchWorkspace: (id: string) => Promise<void>
  refresh: () => Promise<void>
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    try {
      const res = await api.get('/workspaces')
      setWorkspaces(res.data)
      if (!currentWorkspace && res.data.length > 0) {
        const current = res.data.find((w: Workspace) => w.is_default) || res.data[0]
        setCurrentWorkspace(current)
        api.defaults.headers.common['X-Workspace-ID'] = current.id
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const switchWorkspace = async (id: string) => {
    const ws = workspaces.find(w => w.id === id)
    if (!ws) return
    setCurrentWorkspace(ws)
    api.defaults.headers.common['X-Workspace-ID'] = ws.id
  }

  useEffect(() => {
    refresh()
  }, [])

  return (
    <WorkspaceContext.Provider value={{ workspaces, currentWorkspace, loading, error, switchWorkspace, refresh }}>
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const ctx = useContext(WorkspaceContext)
  if (!ctx) throw new Error('useWorkspace must be used within WorkspaceProvider')
  return ctx
}
