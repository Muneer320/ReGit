import { useEffect, useState } from 'react'
import { api, currentUser } from '../lib/api'
import type { BranchRef } from '../lib/types'
import { navigate } from '../lib/router'

/** Branch selector backed by GET /branches?artifact_id=. */
export function BranchSelector({
  artifactId,
  value,
  onChange,
}: {
  artifactId: string
  value?: string
  onChange?: (name: string) => void
}) {
  const [branches, setBranches] = useState<BranchRef[]>([])
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    api
      .listBranches(artifactId)
      .then((bs) => alive && setBranches(bs))
      .catch(() => alive && setError(true))
    return () => {
      alive = false
    }
  }, [artifactId])

  if (error) return <span className="badge red">branches unavailable</span>
  if (branches.length === 0) return <span className="badge">no branches</span>

  const current = branches.find((b) => b.name === value) ?? branches[0]

  return (
    <select
      className="select mono"
      style={{ padding: '3px 8px', fontSize: 12 }}
      value={current.name}
      onChange={(e) => onChange?.(e.target.value)}
    >
      {branches.map((b) => (
        <option key={b.name} value={b.name}>
          {b.name}
        </option>
      ))}
    </select>
  )
}

export function branchListUrl(artifactId: string) {
  return `/art/${artifactId}`
}

export function useBranches(artifactId: string | undefined): BranchRef[] {
  const [branches, setBranches] = useState<BranchRef[]>([])
  useEffect(() => {
    if (!artifactId) return
    let alive = true
    api
      .listBranches(artifactId)
      .then((bs) => alive && setBranches(bs))
      .catch(() => {})
    return () => {
      alive = false
    }
  }, [artifactId])
  return branches
}

export function openArtifact(artifactId: string, branch?: string) {
  navigate(`/art/${artifactId}${branch ? `?branch=${encodeURIComponent(branch)}` : ''}`)
}

export { currentUser }
