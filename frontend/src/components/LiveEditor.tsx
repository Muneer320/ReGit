import { useEffect, useRef, useState } from 'react'
import { CollabClient } from '../lib/ws'
import type { CollabStatus, PeerPresence } from '../lib/ws'
import { bindTextareaToYText } from '../lib/ybinding'
import { useApp } from '../state/store'

export function LiveEditor({ artifactId, branch, onCommitted }: {artifactId: string; branch: string; onCommitted: () => void}) {
  const { user, toast } = useApp()
  const textarea = useRef<HTMLTextAreaElement>(null)
  const client = useRef<CollabClient | null>(null)
  const callback = useRef(onCommitted)
  callback.current = onCommitted
  const [status, setStatus] = useState<CollabStatus>('connecting')
  const [peers, setPeers] = useState<Record<string, PeerPresence>>({})
  const [message, setMessage] = useState('Save live research draft')
  const [saving, setSaving] = useState(false)
  const [lastCommit, setLastCommit] = useState('')
  useEffect(() => {
    if (!textarea.current) return
    textarea.current.value = ''
    const connection = new CollabClient(artifactId, branch, user, {
      onStatus: setStatus, onPeers: setPeers,
      onCommitted: info => { setSaving(false); setLastCommit(info.commit_id); callback.current(); toast('Live draft committed.', 'success') },
      onError: (_code, error) => { setSaving(false); toast(error, 'error') },
    })
    const binding = bindTextareaToYText(connection.ytext, textarea.current, connection.awareness)
    client.current = connection
    connection.connect()
    return () => { binding.destroy(); connection.destroy(); client.current = null }
  }, [artifactId, branch, user, toast])
  useEffect(() => {
    if (!saving) return
    const timeout = window.setTimeout(() => { setSaving(false); toast('No commit acknowledgement yet. Check history before retrying.', 'error') }, 15000)
    return () => window.clearTimeout(timeout)
  }, [saving, toast])
  return <div className="panel-body">
    <div className="btn-row" aria-live="polite"><span className="badge">{status}</span><span>You: {user}</span><span>Peers: {Object.keys(peers).join(', ') || 'none'}</span></div>
    <p className="dim small">Open this artifact and branch in another browser session as userB. Draft updates sync live; Commit from live saves a version.</p>
    <textarea ref={textarea} aria-label="Live research draft" className="repo-editor mono" disabled={status !== 'connected'} spellCheck={false} />
    <div className="btn-row"><input className="input" aria-label="Live commit message" value={message} onChange={event => setMessage(event.target.value)} /><button className="btn primary" disabled={status !== 'connected' || saving || !message.trim()} onClick={() => { setSaving(true); client.current?.requestCommit(message.trim()) }}>Commit from live</button></div>
    {lastCommit && <p className="mono small" aria-live="polite">Saved commit {lastCommit.slice(0, 12)}</p>}
  </div>
}
