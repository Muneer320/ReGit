import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { api, currentUser, setCurrentUser } from '../lib/api'

export type Connection = 'online' | 'offline' | 'checking'

interface Toast {
  id: number
  kind: 'info' | 'error' | 'success'
  text: string
}

interface AppState {
  user: string
  switchUser: (u: string) => void
  connection: Connection
  backendVersion?: string
  toasts: Toast[]
  toast: (text: string, kind?: Toast['kind']) => void
  dismissToast: (id: number) => void
}

const Ctx = createContext<AppState | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState(currentUser())
  const [connection, setConnection] = useState<Connection>('checking')
  const [backendVersion, setBackendVersion] = useState<string | undefined>()
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismissToast = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id))
  }, [])

  const toast = useCallback(
    (text: string, kind: Toast['kind'] = 'info') => {
      const id = nextId.current++
      setToasts((t) => [...t.slice(-3), { id, kind, text }])
      window.setTimeout(() => dismissToast(id), kind === 'error' ? 7000 : 4200)
    },
    [dismissToast],
  )

  const ping = useCallback(async () => {
    setConnection('checking')
    try {
      const h = await api.health()
      setConnection('online')
      if (h?.version) setBackendVersion(h.version)
    } catch {
      setConnection('offline')
    }
  }, [])

  useEffect(() => {
    ping()
    const iv = window.setInterval(ping, 15000)
    return () => window.clearInterval(iv)
  }, [ping])

  const switchUser = useCallback((u: string) => {
    setCurrentUser(u)
    setUser(u)
  }, [])

  return (
    <Ctx.Provider value={{ user, switchUser, connection, backendVersion, toasts, toast, dismissToast }}>
      {children}
    </Ctx.Provider>
  )
}

export function useApp(): AppState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useApp outside AppProvider')
  return v
}
