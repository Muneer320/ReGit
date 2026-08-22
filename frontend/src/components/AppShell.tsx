import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { useApp } from '../state/store'
import { useRoute, navigate } from '../lib/router'
import { api } from '../lib/api'
import { Icon } from './Icon'
import type { IconName } from './Icon'

const USERS = [
  { id: 'userA', color: '#57c47a' },
  { id: 'userB', color: '#6ea0f6' },
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
  icon: IconName
  label: string
  active?: boolean
  onClick: () => void
}) {
  return (
    <button className={`nav-item ${active ? 'active' : ''}`} onClick={onClick}>
      <Icon name={icon} />
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
        icon="file"
        label="Overview"
        active={!route.path.includes('/history') && !route.path.includes('/diff') && !route.path.includes('/merge')}
        onClick={() => navigate(`/art/${id}${q}`)}
      />
      <NavItem icon="commit" label="History" active={route.path.endsWith('/history')} onClick={() => navigate(`/art/${id}/history${q}`)} />
      <NavItem icon="diff" label="Diff" active={route.path.endsWith('/diff')} onClick={() => navigate(`/art/${id}/diff${q}`)} />
      <NavItem icon="merge" label="Merge" active={route.path.endsWith('/merge')} onClick={() => navigate(`/art/${id}/merge${q}`)} />
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

  const onDashboard = route.path === '/'
  const onWorkspace = route.segments[0] === 'repositories' || route.segments[0] === 'workspace'
  const onSearch = route.segments[0] === 'search'

  return (
    <div className="app-shell">
      <header className="topbar">
        <span
          className="brand"
          style={{ cursor: 'pointer' }}
          onClick={() => navigate('/')}
          title="ReGit — version control for research"
        >
          <img src="/regit-wordmark-light-bg.svg" alt="ReGit wordmark" className="brand-logo" />
          <span className="tagline">version control for research</span>
        </span>
        {artId && (
          <span className="crumb">
            <Icon name="chevron-right" size={11} />
            {title ?? artId}
          </span>
        )}
        <div className="topbar-spacer" />
        <UserSelector />
        <ConnectionStatus />
      </header>

      <aside className="sidebar">
        <div className="nav-section-label" style={{ paddingTop: 2 }}>Workspace</div>
        <NavItem icon="graph" label="Dashboard" active={onDashboard} onClick={() => navigate('/')} />
        <NavItem icon="repo" label="Repositories" active={onWorkspace} onClick={() => navigate('/repositories')} />
        <NavItem icon="search" label="Search" active={onSearch} onClick={() => navigate('/search')} />
        {artId && <ArtifactNav id={artId} />}
        <div className="sidebar-footnote">
          Content-addressed artifacts. Sentence-level diffs &amp; merges — every claim traceable to a commit.
        </div>
      </aside>

      <main className="main">{children}</main>
    </div>
  )
}
