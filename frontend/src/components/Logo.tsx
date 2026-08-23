export function Logo() {
  return (
    <span className="regit-logo" aria-label="ReGit">
      <svg className="regit-logo-mark" width="24" height="24" viewBox="0 0 24 24" fill="none" role="img" aria-hidden>
        <rect x="0.75" y="0.75" width="22.5" height="22.5" rx="5" fill="#161B22" stroke="#30363D" strokeWidth="1.5" />
        <path d="M7.5 5.5v13M7.5 8.5h5.2c2.1 0 3.8 1.35 3.8 3.3s-1.7 3.2-3.8 3.2H7.5" stroke="#57C47A" strokeWidth="1.8" strokeLinecap="round" />
        <path d="M12.2 12h4.3M16.5 12v-2.6M16.5 12v2.8" stroke="#6EA0F6" strokeWidth="1.8" strokeLinecap="round" />
        <circle cx="16.5" cy="9.2" r="1.35" fill="#6EA0F6" />
        <circle cx="16.5" cy="14.8" r="1.35" fill="#6EA0F6" />
      </svg>
      <span className="regit-logo-word">ReGit</span>
    </span>
  )
}
