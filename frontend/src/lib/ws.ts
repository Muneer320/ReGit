// Realtime collaboration client — hand-written yjs-over-WebSocket binding
// per docs/specs/realtime-protocol.md (kept hand-written deliberately).
//
// Wire format: binary frames = y-protocols (sync step1/step2 + updates,
// awareness) prefixed by message number; JSON text frames = our control layer
// ({type:"commit_request"…} C→S, {type:"committed"|error} S→C).

import * as Y from 'yjs'
import { Awareness, applyAwarenessUpdate, encodeAwarenessUpdate } from 'y-protocols/awareness'
import * as syncProtocol from 'y-protocols/sync'
import * as encoding from 'lib0/encoding'
import * as decoding from 'lib0/decoding'

const MESSAGE_SYNC = 0
const MESSAGE_AWARENESS = 1

export type CollabStatus = 'connecting' | 'connected' | 'disconnected'

export interface PeerPresence {
  user: string
  color?: string
  cursor?: unknown
}

export interface CollabEvents {
  onStatus?: (s: CollabStatus) => void
  onPeers?: (peers: Record<string, PeerPresence>) => void
  onCommitted?: (info: { commit_id: string; author?: string; message?: string }) => void
  onError?: (code: string, message: string) => void
}

export class CollabClient {
  readonly doc: Y.Doc = new Y.Doc()
  readonly awareness: Awareness
  readonly artifactId: string
  readonly branch: string
  readonly user: string

  private ws: WebSocket | null = null
  private lastStatus: CollabStatus = 'disconnected'
  private retry = 0
  private closedByUs = false
  private events: CollabEvents

  constructor(artifactId: string, branch: string, user: string, events: CollabEvents = {}) {
    this.artifactId = artifactId
    this.branch = branch
    this.user = user
    this.events = events
    this.awareness = new Awareness(this.doc)
    this.awareness.setLocalStateField('user', {
      user,
      color: user === 'userB' ? '#7aa2f7' : '#4ade80',
    })
    this.awareness.on('update', () => this.broadcastAwareness())
  }

  get ytext(): Y.Text {
    return this.doc.getText('content')
  }

  connect() {
    this.closedByUs = false
    this.setStatus('connecting')
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${window.location.host}/api/collaborate/${encodeURIComponent(
      this.artifactId,
    )}?branch=${encodeURIComponent(this.branch)}&user=${encodeURIComponent(this.user)}`
    const ws = new WebSocket(url)
    ws.binaryType = 'arraybuffer'
    this.ws = ws

    ws.onopen = () => {
      this.retry = 0
      this.setStatus('connected')
      // Sync step 1: send state vector; server answers step 2 + its own step 1.
      const enc = encoding.createEncoder()
      encoding.writeVarUint(enc, MESSAGE_SYNC)
      syncProtocol.writeSyncStep1(enc, this.doc)
      this.sendBinary(encoding.toUint8Array(enc))
      this.broadcastAwareness()
    }
    ws.onmessage = (ev) => this.onMessage(ev.data)
    ws.onclose = () => {
      this.setStatus('disconnected')
      this.ws = null
      if (!this.closedByUs && this.retry < 6) {
        // Reconnect with backoff; sync step 1 heals any missed updates.
        window.setTimeout(() => this.connect(), Math.min(800 * 2 ** this.retry++, 10000))
      }
    }
    ws.onerror = () => {
      try {
        ws.close()
      } catch {
        /* noop */
      }
    }
  }

  disconnect() {
    this.closedByUs = true
    try {
      this.ws?.close()
    } catch {
      /* noop */
    }
    this.ws = null
    this.setStatus('disconnected')
  }

  /** Ask the server to snapshot the live doc into an immutable DAG commit. */
  requestCommit(message: string) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
    this.ws.send(JSON.stringify({ type: 'commit_request', message }))
  }

  localText(): string {
    return this.ytext.toString()
  }

  private setStatus(s: CollabStatus) {
    if (s !== this.lastStatus) {
      this.lastStatus = s
      this.events.onStatus?.(s)
    }
  }

  private sendBinary(data: Uint8Array) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(data.slice().buffer as ArrayBuffer)
    }
  }

  private broadcastAwareness() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return
    const enc = encoding.createEncoder()
    encoding.writeVarUint(enc, MESSAGE_AWARENESS)
    encoding.writeVarUint8Array(
      enc,
      encodeAwarenessUpdate(this.awareness, [...this.awareness.getStates().keys()]),
    )
    this.sendBinary(encoding.toUint8Array(enc))
  }

  private onMessage(data: ArrayBuffer | string) {
    if (typeof data === 'string') {
      try {
        const msg = JSON.parse(data)
        switch (msg.type) {
          case 'committed':
            this.events.onCommitted?.(msg)
            break
          case 'error':
            this.events.onError?.(String(msg.code ?? 'ERROR'), String(msg.message ?? ''))
            break
          default:
            break
        }
      } catch {
        /* malformed control frame — ignore */
      }
      return
    }
    const decoder = decoding.createDecoder(new Uint8Array(data))
    const type = decoding.readVarUint(decoder)
    if (type === MESSAGE_SYNC) {
      const reply = encoding.createEncoder()
      encoding.writeVarUint(reply, MESSAGE_SYNC)
      syncProtocol.readSyncMessage(decoder, reply, this.doc, this)
      if (encoding.length(reply) > 1) this.sendBinary(encoding.toUint8Array(reply))
    } else if (type === MESSAGE_AWARENESS) {
      applyAwarenessUpdate(this.awareness, decoding.readVarUint8Array(decoder), this)
      this.emitPeers()
    }
  }

  private emitPeers() {
    const out: Record<string, PeerPresence> = {}
    this.awareness.getStates().forEach((state) => {
      const u = (state as { user?: { user?: string; color?: string }; cursor?: unknown }).user
      if (u?.user && u.user !== this.user) {
        out[u.user] = { user: u.user, color: u.color, cursor: (state as { cursor?: unknown }).cursor }
      }
    })
    this.events.onPeers?.(out)
  }
}
