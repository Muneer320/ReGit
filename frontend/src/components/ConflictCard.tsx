import { useState } from 'react'
import type { Conflict, ResolutionKind } from '../lib/types'
import { Badge } from './ui'

export interface PendingResolution {
  kind: ResolutionKind
  text: string
}

/** One conflict: BASE / OURS / THEIRS triple + resolution actions. */
export function ConflictCard({
  conflict,
  oursBranch,
  theirsBranch,
  value,
  onChange,
  disabled,
}: {
  conflict: Conflict
  oursBranch: string
  theirsBranch: string
  value?: PendingResolution
  onChange: (r: PendingResolution | undefined) => void
  disabled?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')

  const startEdit = () => {
    setDraft(value?.kind === 'free' ? value.text : conflict.ours_text)
    setEditing(true)
  }

  const applyEdit = () => {
    onChange({ kind: 'free', text: draft })
    setEditing(false)
  }

  const cancelEdit = () => setEditing(false)

  const resolved = value !== undefined

  const emptyish = (t: string) => t.trim() === ''

  return (
    <div className={`conflict-card ${resolved ? 'resolved' : ''}`}>
      <div className="conflict-card-head">
        <span style={{ color: 'var(--red)', fontWeight: 700 }}>⑃</span>
        <h3>Conflict in sentence</h3>
        <span className="mono faint small">{conflict.sid}</span>
        <span className="spacer" style={{ flex: 1 }} />
        {resolved ? (
          <>
            <Badge variant="green">✓ resolved · {value!.kind === 'free' ? 'custom edit' : value!.kind}</Badge>
            {!disabled && (
              <button className="btn ghost sm" onClick={() => onChange(undefined)} title="Undo this resolution">
                undo
              </button>
            )}
          </>
        ) : (
          <Badge variant="red">unresolved</Badge>
        )}
      </div>

      <div className="version-blocks">
        <div className="version-block v-base">
          <div className="version-block-label">Base</div>
          <div className={`version-block-text ${emptyish(conflict.base_text) ? 'v-empty' : ''}`}>
            {emptyish(conflict.base_text) ? '(absent in base)' : conflict.base_text}
          </div>
        </div>
        <div className="version-block v-ours">
          <div className="version-block-label">Ours · {oursBranch}</div>
          <div className={`version-block-text ${emptyish(conflict.ours_text) ? 'v-empty' : ''}`}>
            {emptyish(conflict.ours_text) ? '(deleted on ours)' : conflict.ours_text}
          </div>
        </div>
        <div className="version-block v-theirs">
          <div className="version-block-label">Theirs · {theirsBranch}</div>
          <div className={`version-block-text ${emptyish(conflict.theirs_text) ? 'v-empty' : ''}`}>
            {emptyish(conflict.theirs_text) ? '(deleted on theirs)' : conflict.theirs_text}
          </div>
        </div>
      </div>

      {editing && !resolved && (
        <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
          <div className="small dim" style={{ marginBottom: 6 }}>
            Free edit — write the resolution yourself:
          </div>
          <textarea className="code-editor" value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
          <div className="btn-row" style={{ marginTop: 8 }}>
            <button className="btn primary sm" onClick={applyEdit} disabled={!draft.trim()}>
              Apply resolution
            </button>
            <button className="btn sm" onClick={cancelEdit}>
              Cancel
            </button>
            <span className="faint small mono">{draft.trim().length} chars</span>
          </div>
        </div>
      )}

      {!editing && (
        <div className="resolution-actions">
          <span className="mono faint small" style={{ marginRight: 4 }}>
            resolve as
          </span>
          <button
            className={`btn sm ${value?.kind === 'ours' ? 'success' : ''}`}
            disabled={disabled || resolved}
            onClick={() => onChange({ kind: 'ours', text: conflict.ours_text })}
          >
            Accept Ours
          </button>
          <button
            className={`btn sm ${value?.kind === 'theirs' ? 'success' : ''}`}
            disabled={disabled || resolved}
            onClick={() => onChange({ kind: 'theirs', text: conflict.theirs_text })}
          >
            Accept Theirs
          </button>
          <button
            className={`btn sm ${value?.kind === 'free' ? 'success' : ''}`}
            disabled={disabled || resolved}
            onClick={startEdit}
          >
            Free Edit
          </button>
          {resolved && (
            <span className="chosen-note">
              ✓ {value!.kind === 'free' ? 'custom text applied' : `${value!.kind} accepted`}
            </span>
          )}
        </div>
      )}
    </div>
  )
}
