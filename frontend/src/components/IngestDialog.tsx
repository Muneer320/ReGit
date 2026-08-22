import { useRef, useState } from 'react'
import type { IngestType } from '../lib/types'
import { api } from '../lib/api'
import { useApp } from '../state/store'
import { Spinner } from './ui'
import { Icon } from './Icon'

const TYPES: { id: IngestType; label: string; exts: string }[] = [
  { id: 'markdown', label: 'Markdown', exts: '.md, .markdown' },
  { id: 'chatgpt', label: 'ChatGPT export', exts: '.json' },
  { id: 'claude', label: 'Claude export', exts: '.jsonl' },
  { id: 'pdf', label: 'PDF', exts: '.pdf' },
  { id: 'codebase', label: 'Codebase', exts: '.zip / .tar' },
]

export function IngestDialog({
  onClose,
  onIngested,
}: {
  onClose: () => void
  onIngested: () => void
}) {
  const { toast } = useApp()
  const [type, setType] = useState<IngestType>('markdown')
  const [file, setFile] = useState<File | null>(null)
  const [over, setOver] = useState(false)
  const [phase, setPhase] = useState<'pick' | 'uploading'>('pick')
  const inputRef = useRef<HTMLInputElement>(null)

  const submit = async () => {
    if (!file) return
    setPhase('uploading')
    try {
      const res = await api.ingest(file, type)
      toast(
        `Ingested ${file.name} → ${res.artifact_ids.length} artifact${res.artifact_ids.length === 1 ? '' : 's'}${res.warnings?.length ? ` (${res.warnings.length} warnings)` : ''}`,
        'success',
      )
      onIngested()
      onClose()
    } catch (e) {
      toast(`Ingest failed: ${e instanceof Error ? e.message : String(e)}`, 'error')
      setPhase('pick')
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>Ingest research source</h2>
          <button className="btn ghost sm" onClick={onClose}>
             <Icon name="x" size={13} />
          </button>
        </div>
        <div className="modal-body">
          <div className="field">
            <label>Source type</label>
            <select className="select" value={type} onChange={(e) => setType(e.target.value as IngestType)}>
              {TYPES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label} ({t.exts})
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>File</label>
            <div
              className={`file-drop ${file ? 'has-file' : ''} ${over ? 'over' : ''}`}
              onClick={() => inputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault()
                setOver(true)
              }}
              onDragLeave={() => setOver(false)}
              onDrop={(e) => {
                e.preventDefault()
                setOver(false)
                const f = e.dataTransfer.files?.[0]
                if (f) setFile(f)
              }}
            >
              {file ? (
                <>
                  <b>{file.name}</b>{' '}
                  <span className="faint mono small">({Math.ceil(file.size / 1024)} KB)</span>
                  <div className="small faint" style={{ marginTop: 4 }}>
                    click to choose a different file
                  </div>
                </>
              ) : (
                <>
                  Drop a file here or <span style={{ color: 'var(--accent)' }}>browse</span>
                  <div className="small faint" style={{ marginTop: 4 }}>
                    Parsed into canonical form, content-addressed, root commit created.
                  </div>
                </>
              )}
            </div>
            <input
              ref={inputRef}
              type="file"
              hidden
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
        </div>
        <div className="modal-foot">
          <button className="btn" onClick={onClose} disabled={phase === 'uploading'}>
            Cancel
          </button>
          <button className="btn primary" onClick={submit} disabled={!file || phase === 'uploading'}>
            {phase === 'uploading' ? (
              <>
                <Spinner /> Ingesting…
              </>
            ) : (
              'Ingest'
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
