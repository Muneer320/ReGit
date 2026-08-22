import { useState } from 'react'
import { api } from './lib/api'
import './App.css'

function App() {
  const [status, setStatus] = useState('not-checked')

  const ping = async () => {
    try {
      const res = await api.health()
      setStatus(res.status)
    } catch (e: any) {
      setStatus(`ERR ${e?.message ?? e}`)
    }
  }

  return (
    <div className="app">
      <h1>ReGit</h1>
      <p className="tagline">
        Research-native version control — what if Git had been designed for research instead of code?
      </p>
      <button onClick={ping}>Check backend</button>
      <pre className="status">backend: {status}</pre>
      <p className="hint">
        Screens to be built: Workspace · Editor (2-pane) · History · Diff · Conflicts · Search.
        See <code>docs/AMRIT-BRIEF.md</code>.
      </p>
    </div>
  )
}

export default App