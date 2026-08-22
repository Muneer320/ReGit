import { useEffect, useState } from 'react'

export interface Route {
  path: string // e.g. "/art/art_123/diff"
  segments: string[]
  query: URLSearchParams
}

function parse(): Route {
  const raw = window.location.hash.replace(/^#/, '') || '/'
  const [pathPart, queryPart] = raw.split('?')
  const path = pathPart.startsWith('/') ? pathPart : `/${pathPart}`
  return {
    path,
    segments: path.split('/').filter(Boolean),
    query: new URLSearchParams(queryPart ?? ''),
  }
}

export function useRoute(): Route {
  const [route, setRoute] = useState(parse)
  useEffect(() => {
    const onChange = () => setRoute(parse())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export function navigate(to: string) {
  window.location.hash = to.startsWith('#') ? to : `#${to}`
}
