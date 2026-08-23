// Minimal stroke icon set (14px grid) — replaces emoji/unicode glyphs.
// Consistent 1.5 stroke, currentColor, no fills except where noted.
import type { JSX } from 'react'

export type IconName =
  | 'repo'
  | 'branch'
  | 'commit'
  | 'history'
  | 'diff'
  | 'merge'
  | 'search'
  | 'upload'
  | 'user'
  | 'warning'
  | 'check'
  | 'x'
  | 'chevron-right'
  | 'chevron-down'
  | 'file'
  | 'chat'
  | 'pdf'
  | 'code'
  | 'graph'
  | 'dot'
  | 'star'

const PATHS: Record<IconName, JSX.Element> = {
  repo: (
    <path d="M3 2.5h8.5a1 1 0 0 1 1 1v9l-2.75-1.5L7 12.5V3.5a1 1 0 0 0-1-1H3Z" />
  ),
  branch: (
    <>
      <circle cx="4" cy="3.5" r="1.6" />
      <circle cx="4" cy="11.5" r="1.6" />
      <circle cx="11" cy="6" r="1.6" />
      <path d="M4 5.1v4.8M11 7.6c0 2-2 3.2-5.2 3.2" />
    </>
  ),
  commit: (
    <>
      <circle cx="7" cy="7" r="2.6" />
      <path d="M7 1v3.4M7 9.6V13" />
    </>
  ),
  history: (
    <>
      <path d="M2.5 7a4.5 4.5 0 1 1 1.3 3.2" />
      <path d="M2.3 7.2 2.5 10l2.6-.9M7 4.5V7l1.8 1.4" />
    </>
  ),
  diff: (
    <>
      <path d="M4 2.5v5M1.5 5h5M9 9.5h4M9 12h4" />
      <path d="M8.5 2.5h4v4h-4z" />
    </>
  ),
  merge: (
    <>
      <circle cx="4" cy="3" r="1.6" />
      <circle cx="4" cy="12" r="1.6" />
      <circle cx="11.5" cy="9.5" r="1.6" />
      <path d="M4 4.6v5.8M4 6.5c0 2.5 3 1.5 5.6 2.4" />
    </>
  ),
  search: (
    <>
      <circle cx="6" cy="6" r="3.8" />
      <path d="m9 9 3.6 3.6" />
    </>
  ),
  upload: (
    <>
      <path d="M7 9.5v-7M4.2 5 7 2.2 9.8 5" />
      <path d="M2 10v2.5h10V10" />
    </>
  ),
  user: (
    <>
      <circle cx="7" cy="4.6" r="2.4" />
      <path d="M2.5 12.5c.6-2.6 2.3-3.9 4.5-3.9s3.9 1.3 4.5 3.9" />
    </>
  ),
  warning: (
    <>
      <path d="M7 1.8 13 12H1L7 1.8Z" />
      <path d="M7 5.5v3M7 10.4v.2" />
    </>
  ),
  check: <path d="m2.5 7.5 3 3 6-6.5" />,
  x: <path d="m3 3 8 8M11 3l-8 8" />,
  'chevron-right': <path d="m5 3 4.5 4L5 11" />,
  'chevron-down': <path d="m3 5 4 4.5L11 5" />,
  file: (
    <>
      <path d="M4 1.5h4l3 3v8h-7z" />
      <path d="M8 1.5v3h3" />
    </>
  ),
  chat: (
    <>
      <path d="M2 2.5h10v7H6l-3 2.8V9.5H2z" />
      <path d="M4.5 5.2h5M4.5 7.2h3" />
    </>
  ),
  pdf: (
    <>
      <path d="M4 1.5h4l3 3v8h-7z" />
      <path d="M8 1.5v3h3" />
      <path d="M5.2 10.5c1-.8 2.4-2.6 3.6-2.4 1 .2-1.8 2.6-.6 3 .9.3 2-.8 2.6-1.6" />
    </>
  ),
  code: <path d="m4.5 4-3 3 3 3M9.5 4l3 3-3 3" />,
  graph: (
    <>
      <circle cx="3.5" cy="3" r="1.5" />
      <circle cx="11" cy="6.5" r="1.5" />
      <circle cx="5.5" cy="12" r="1.5" />
      <path d="M5 3.4c3 .5 4 1.5 4.6 2M9.7 7.6c-.8 2-2.2 3.3-3.4 3.8" />
    </>
  ),
  dot: <circle cx="7" cy="7" r="2.4" fill="currentColor" stroke="none" />,
  star: <path d="m7 1.7 1.65 3.35 3.7.54-2.68 2.61.63 3.69L7 10.15l-3.3 1.74.63-3.69-2.68-2.61 3.7-.54L7 1.7Z" />,
}

export function Icon({
  name,
  size = 14,
  className = '',
}: {
  name: IconName
  size?: number
  className?: string
}) {
  return (
    <svg
      className={`icon-svg ${className}`}
      width={size}
      height={size}
      viewBox="0 0 14 14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{ flexShrink: 0 }}
    >
      {PATHS[name]}
    </svg>
  )
}
