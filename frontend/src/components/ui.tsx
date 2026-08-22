import type { ReactNode } from 'react'
import { useApp } from '../state/store'

export function Badge({
  children,
  variant,
  className = '',
}: {
  children: ReactNode
  variant?: string
  className?: string
}) {
  return <span className={`badge ${variant ?? ''} ${className}`}>{children}</span>
}

export function KindBadge({ kind }: { kind: string }) {
  return (
    <span className={`badge kind-${kind}`}>
      {kind === 'md' && 'MD'}
      {kind === 'txt' && 'TXT'}
      {kind === 'chat' && 'CHAT'}
      {kind === 'pdf' && 'PDF'}
      {kind === 'codebase' && 'CODE'}
      {!['md', 'txt', 'chat', 'pdf', 'codebase'].includes(kind) && kind.toUpperCase()}
    </span>
  )
}

export function BranchBadge({ name }: { name: string }) {
  return (
    <span className="badge branch" title="branch">
      <svg width="9" height="9" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
        <path d="M5 3.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm0 2.122a2.25 2.25 0 1 0-1.5 0v5.256a2.251 2.251 0 1 0 1.5 0V7.4c.435-.14.81-.42 1.068-.79L6.6 5.98A2.75 2.75 0 0 1 10.5 7.5v.256a2.25 2.25 0 1 0 1.5 0V7.5a4.25 4.25 0 0 0-6.88-3.34l-.12.09Z" />
      </svg>
      {name}
    </span>
  )
}

export function shortHash(h: string | undefined, n = 7): string {
  if (!h) return ''
  return h.slice(0, n)
}

export function Hash({ hash, n }: { hash: string | undefined; n?: number }) {
  if (!hash) return null
  return (
    <span className="hash">
      <b>{shortHash(hash, n)}</b>
    </span>
  )
}

export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return iso
  const s = Math.max(0, (Date.now() - then) / 1000)
  if (s < 60) return `${Math.floor(s)}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

export function Spinner() {
  return <span className="spinner" aria-label="loading" />
}

export function LoadingState({ label = 'Loading from backend…' }: { label?: string }) {
  return (
    <div className="state-block">
      <Spinner />
      <p style={{ marginTop: 10 }}>{label}</p>
    </div>
  )
}

export function EmptyState({
  icon = '∅',
  title,
  hint,
  action,
}: {
  icon?: string
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="state-block">
      <div className="icon">{icon}</div>
      <div className="title">{title}</div>
      {hint && <p>{hint}</p>}
      {action && <div style={{ marginTop: 14 }}>{action}</div>}
    </div>
  )
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return (
    <div className="state-block">
      <div className="icon">⚠</div>
      <div className="title">Something failed</div>
      <p className="mono small" style={{ color: 'var(--red)' }}>
        {message}
      </p>
      {retry && (
        <button className="btn sm" style={{ marginTop: 12 }} onClick={retry}>
          Retry
        </button>
      )}
    </div>
  )
}

export function MockChip() {
  return (
    <span
      className="badge amber"
      title="Backend engine for this surface is still a stub — rendered by the local demo adapter over real repository data."
    >
      demo adapter
    </span>
  )
}

export function Toasts() {
  const { toasts, dismissToast } = useApp()
  return (
    <div className="toast-host">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.kind}`} onClick={() => dismissToast(t.id)}>
          <span>{t.kind === 'error' ? '✕' : t.kind === 'success' ? '✓' : '›'}</span>
          <span>{t.text}</span>
        </div>
      ))}
    </div>
  )
}

/** Word-level highlight of the changed region inside an edited sentence. */
export function inlineHighlight(oldText: string, newText: string): ReactNode {
  const ow = oldText.split(/\s+/)
  const nw = newText.split(/\s+/)
  // Common prefix/suffix trim — highlight only the changed middle.
  let start = 0
  while (start < ow.length && start < nw.length && ow[start] === nw[start]) start++
  let endO = ow.length
  let endN = nw.length
  while (endO > start && endN > start && ow[endO - 1] === nw[endN - 1]) {
    endO--
    endN--
  }
  const pre = nw.slice(0, start).join(' ')
  const mid = nw.slice(start, endN).join(' ')
  const post = endN < nw.length ? ' ' + nw.slice(endN).join(' ') : ''
  return (
    <>
      {pre}
      {pre && mid ? ' ' : ''}
      <ins>{mid}</ins>
      {post}
    </>
  )
}
