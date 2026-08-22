import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useApp } from '../state/store'
import { useRoute, navigate } from '../lib/router'
import { api } from '../lib/api'

const USERS = [
  { id: 'userA', color: '#4ade80' },
  { id: 'userB', color: '#7aa2f7' },
]

export function UserSelector() {
  const { user, switchUser, toast } = useApp()
  return (
    <div className="user-switch" title="Demo identity — sent as the X-User header">
      {USERS.map((u) => (
        <button
          key={u.id}
          className={user === u.id ? 'active' : ''}
          onClick={() => {
            switchUser(u.id)
            toast(`Acting as ${u.id}`, 'info')
          }}
        >
          <span className="user-dot" style={{ background: u.color }} />
          {u.id}
        </button>
      ))}
    </div>
  )
}

export function ConnectionStatus() {
  const { connection, backendVersion } = useApp()
  return (
    <span className={`connection ${connection}`} title={connection === 'online' ? `ReGit API v${backendVersion ?? '?'}` : 'Backend unreachable'}>
      <span className="dot" />
      {connection === 'online' ? 'API' : connection === 'checking' ? '…' : 'offline'}
    </span>
  )
}

function NavItem({
  icon,
  label,
  active,
  onClick,
}: {
  icon: string
  label: string
  active?: boolean
  onClick: () => void
}) {
  return (
    <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick}>
      <span className="nav-icon">{icon}</span>
      {label}
    </button>
  )
}

/** Contextual artifact nav — shown when an artifact is open. */
function ArtifactNav({ id }: { id: string }) {
  const route = useRoute()
  const branch = route.query.get('branch') ?? undefined
  const q = branch ? `?branch=${encodeURIComponent(branch)}` : ''
  return (
    <>
      <div className="nav-section-label">Artifact</div>
      <NavItem
        icon="◈"
        label="Overview"
        active={!route.path.includes('/history') && !route.path.includes('/diff') && !route.path.includes('/merge')}
        onClick={() => navigate(`/art/${id}${q}`)}
      />
      <NavItem icon="⌥" label="History" active={route.path.endsWith('/history')} onClick={() => navigate(`/art/${id}/history${q}`)} />
      <NavItem icon="±" label="Diff" active={route.path.endsWith('/diff')} onClick={() => navigate(`/art/${id}/diff${q}`)} />
      <NavItem icon="⑃" label="Merge" active={route.path.endsWith('/merge')} onClick={() => navigate(`/art/${id}/merge${q}`)} />
    </>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const route = useRoute()
  const [title, setTitle] = useState<string | null>(null)
  const artId = route.segments[0] === 'art' ? route.segments[1] : undefined

  useEffect(() => {
    if (!artId) {
      setTitle(null)
      return
    }
    let alive = true
    api
      .getArtifact(artId)
      .then((a) => alive && setTitle(a.title))
      .catch(() => alive && setTitle(artId))
    return () => {
      alive = false
    }
  }, [artId])

  const onWorkspace = route.path === '/' || route.segments[0] === 'workspace'
  const onSearch = route.segments[0] === 'search'

  return (
    <div className="app-shell">
      <header className="topbar">
        <span
          className="brand"
          style={{ cursor: 'pointer' }}
          onClick={() => navigate('/')}
          title="ReGit — research-native version control"
        >
          <span className="glyph">R</span>
          ReGit
          <span className="tagline">version control for research</span>
        </span>
        {artId && (
          <span className="crumb dim">
            /
            {title ? (
              <b style={{ color: 'var(--heading)', fontWeight: 600 }}>{title}</b>
            ) : (
              <span className="mono">{artId}</span>
            )}
          </span>
        )}
        <div className="topbar-spacer" />
        <UserSelector />
        <ConnectionStatus />
      </header>

      <aside className="sidebar">
        <div className="nav-section-label">Workspace</div>
        <NavItem icon="⌂" label="Artifacts" active={onWorkspace} onClick={() => navigate('/')} />
        <NavItem icon="⌕" label="Search" active={onSearch} onClick={() => navigate('/search')} />
        {artId && <ArtifactNav id={artId} />}
        <div style={{ flex: 1 }} />
        <div className="nav-section-label">About</div>
        <p className="faint" style={{ padding: '0 10px', fontSize: 11.5, lineHeight: 1.5 }}>
          Content-addressed research artifacts. Sentence-level diffs &amp; merges.
          Every claim traceable to a commit.
        </p>
      </aside>

      <main className="main">{children}</main>
    </div>
  )
}
