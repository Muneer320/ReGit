import { navigate } from '../lib/router'
import { useState } from 'react'
import { useApp } from '../state/store'
import { Icon } from '../components/Icon'

const profileTabs = [
  { label: 'Overview' },
  { label: 'Repositories', count: 4 },
  { label: 'Projects', count: 3 },
  { label: 'Packages', count: 6 },
  { label: 'Stars', count: 18 },
]

const repositories = [
  {
    name: 'git-for-research',
    description: 'Research-native version control for complex, multi-document workflows.',
    language: 'TypeScript',
    languageColor: '#6ea0f6',
    stars: '1.3k',
    forks: '481',
  },
  {
    name: 'realtime-collab',
    description: 'Shared editing, presence, and merge coordination for collaborative research.',
    language: 'Python',
    languageColor: '#57c47a',
    stars: '820',
    forks: '210',
  },
  {
    name: 'retrieval-indexer',
    description: 'Semantic chunking, vector indexing, and provenance-aware retrieval flows.',
    language: 'Rust',
    languageColor: '#d9b03c',
    stars: '640',
    forks: '158',
  },
  {
    name: 'diff-visualizer',
    description: 'Inline comparison views for research artifacts and iterative drafts.',
    language: 'Go',
    languageColor: '#ab8ef2',
    stars: '420',
    forks: '95',
  },
]

const contributionLevels = Array.from({ length: 52 * 7 }, (_, index) => {
  const week = Math.floor(index / 7)
  const day = index % 7
  const value = (week * 13 + day * 7 + week * day) % 17
  return value < 5 ? 0 : value < 8 ? 1 : value < 11 ? 2 : value < 14 ? 3 : value < 16 ? 4 : 5
})

const activity = [
  'Updated the diff alignment model for research artifacts and notes.',
  'Reviewed a reindexing pipeline for better semantic chunking performance.',
  'Merged a collaborative workspace proposal for multi-user annotation sessions.',
]

const months = ['Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']

const history = [
  { repo: 'git-for-research', message: 'Refine GitHub-style research dashboard', branch: 'amrit', when: 'today', hash: 'a1e9324' },
  { repo: 'realtime-collab', message: 'Add presence indicators to shared editor', branch: 'main', when: '2 days ago', hash: 'ee4bf2e' },
  { repo: 'retrieval-indexer', message: 'Improve provenance metadata for search results', branch: 'main', when: '5 days ago', hash: 'c82d9af' },
  { repo: 'diff-visualizer', message: 'Show sentence-level change markers', branch: 'feature/markers', when: '1 week ago', hash: '7ab41c0' },
]

export function DashboardPage() {
  const { connection } = useApp()
  const [historyOpen, setHistoryOpen] = useState(true)
  const [activeTab, setActiveTab] = useState('Overview')
  const branchCount = 18

  return (
    <div className="page profile-page">
      <section className="profile-header">
        <div className="profile-identity">
          <div className="profile-avatar-wrap">
            <img
              src="https://avatars.githubusercontent.com/u/39381448?v=4"
              alt="Muneer profile avatar"
            />
          </div>
          <div className="profile-meta">
            <span className="profile-status">
              <span className="status-dot" />
              Open to collaborate
            </span>
            <h1>Muneer</h1>
            <p>@muneer320</p>
          </div>
        </div>

        <div className="profile-actions">
          <button className="btn primary">Follow</button>
          <button className="btn">Sponsor</button>
        </div>
      </section>

      <nav className="profile-tabs" aria-label="Profile sections">
        {profileTabs.map((tab) => (
          <button key={tab.label} className={activeTab === tab.label ? 'active' : ''} type="button" onClick={() => setActiveTab(tab.label)}>
            {tab.label}
            {tab.count !== undefined && <span className="profile-tab-count">{tab.count}</span>}
          </button>
        ))}
      </nav>

      {activeTab !== 'Overview' && <ProfileTabView tab={activeTab} />}

      {activeTab === 'Overview' && <>
      <section className="panel profile-about-wide">
        <div className="panel-head">About</div>
        <div className="profile-about-content">
          <p>Building tools for human-centered research workflows, documentation, and open collaboration across code, notes, and experiments.</p>
          <div className="about-links"><span><Icon name="repo" size={12} /> Research-native version control</span><span><Icon name="branch" size={12} /> Open collaboration</span><span><Icon name="search" size={12} /> Provenance-aware retrieval</span></div>
        </div>
      </section>

      <div className="profile-details-row">
          <section className="panel profile-card">
            <div className="panel-head">Profile details</div>
            <div className="profile-card-body">
              <ul className="profile-list">
                <li>Research-native version control</li>
                <li>Realtime collaborative editor</li>
                <li>Semantic retrieval and indexing</li>
              </ul>
            </div>
          </section>

          <section className="panel profile-card compact">
            <div className="panel-head">Organizations</div>
            <div className="profile-card-body orgs">
              <span>RG</span>
              <span>AI</span>
              <span>CS</span>
            </div>
          </section>
      </div>

      <main className="profile-main profile-content">
          <section className="panel">
            <div className="panel-head">
              <span>Popular repositories</span>
              <div className="panel-head-spacer" />
              <button className="btn ghost sm" onClick={() => navigate('/repositories')} type="button">
                Customize your pins
              </button>
            </div>

            <div className="repo-grid">
              {repositories.map((repo) => (
                <article className="repo-card" key={repo.name}>
                  <div className="repo-topline">
                    <div className="repo-name-wrap">
                      <Icon name="repo" size={13} />
                      <h3>{repo.name}</h3>
                    </div>
                    <button className="btn sm" type="button">
                      <span className="star-mark">★</span>
                      Star
                    </button>
                  </div>

                  <p>{repo.description}</p>

                  <div className="repo-meta">
                    <span className="language-pill">
                      <i style={{ background: repo.languageColor }} />
                      {repo.language}
                    </span>
                    <span>
                      <span className="star-mark small">★</span>
                      {repo.stars}
                    </span>
                    <span>
                      <Icon name="branch" size={12} />
                      {repo.forks}
                    </span>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">Contribution activity</div>
            <div className="contrib-wrap">
              <div className="month-labels">
                {months.map((month) => <span key={month}>{month}</span>)}
              </div>
              <div className="contrib-chart-row">
                <div className="weekday-labels"><span>Mon</span><span>Wed</span><span>Fri</span></div>
                <div className="contrib-grid" aria-label="Contribution graph">
                  {contributionLevels.map((level, index) => <span key={`${level}-${index}`} className={`contrib-cell level-${level}`} title={`Contribution level ${level}`} />)}
                </div>
              </div>
              <p className="contrib-total"><b>186 contributions</b> in the last year</p>
              <div className="contrib-legend"><span>Less</span>{[0, 1, 2, 3, 4, 5].map((level) => <i key={level} className={`contrib-cell level-${level}`} />)}<span>More</span></div>
            </div>

            <div className="activity-list">
              {activity.map((item) => (
                <div className="activity-item" key={item}>
                  <span className="activity-tag">Commit</span>
                  <p>{item}</p>
                </div>
              ))}
            </div>
          </section>

          <details className="panel dashboard-history" open={historyOpen} onToggle={(event) => setHistoryOpen(event.currentTarget.open)}>
            <summary className="panel-head">
              <span>History</span>
              <span className="panel-head-note">Recent activity across repositories</span>
              <Icon name={historyOpen ? 'chevron-down' : 'chevron-right'} size={12} />
            </summary>
            <div className="history-list">
              {history.map((item) => (
                <button className="history-row" key={`${item.repo}-${item.hash}`} onClick={() => navigate('/repositories')}>
                  <span className="history-commit-icon"><Icon name="commit" size={13} /></span>
                  <span className="history-copy">
                    <b>{item.message}</b>
                    <span><strong>{item.repo}</strong> · <span className="history-branch">{item.branch}</span> · {item.when}</span>
                  </span>
                  <code>{item.hash}</code>
                  <Icon name="chevron-right" size={12} />
                </button>
              ))}
            </div>
            <button className="history-more" onClick={() => navigate('/repositories')}>Show more activity <Icon name="chevron-right" size={12} /></button>
          </details>
      </main>

      <div className="profile-summary-row">
        <div className="mini-stat-card">
          <span className="mini-stat-icon blue"><Icon name="repo" size={15} /></span>
          <div>
            <b>{repositories.length}</b>
            <small>repositories</small>
          </div>
        </div>
        <div className="mini-stat-card">
          <span className="mini-stat-icon violet"><Icon name="branch" size={15} /></span>
          <div>
            <b>{branchCount}</b>
            <small>branches</small>
          </div>
        </div>
        <div className="mini-stat-card">
          <span className={`mini-stat-icon ${connection === 'online' ? 'green' : 'amber'}`}>
            <span className="status-ring" />
          </span>
          <div>
            <b>{connection === 'online' ? 'Live' : 'Offline'}</b>
            <small>API connection</small>
          </div>
        </div>
      </div>
      </>}
    </div>
  )
}

const tabDemoData: Record<string, { title: string; detail: string; meta: string }[]> = {
  Projects: [
    { title: 'ReGit research workspace', detail: 'Track ingestion, semantic diff, and merge milestones.', meta: 'Active · 72% complete' },
    { title: 'Provenance-first retrieval', detail: 'Make every search result traceable to its source commit.', meta: 'Active · 4 contributors' },
    { title: 'Collaborative lab notes', detail: 'Shared editing and review flows for distributed teams.', meta: 'Planning' },
  ],
  Packages: [
    { title: '@regit/semantic-diff', detail: 'Sentence-level alignment for research prose.', meta: 'v0.8.2 · TypeScript' },
    { title: '@regit/merge-engine', detail: 'Three-way merge decisions with explicit conflicts.', meta: 'v0.6.1 · Python' },
    { title: '@regit/provenance', detail: 'Citation and content-addressed source metadata.', meta: 'v0.4.0 · Rust' },
  ],
  Stars: [
    { title: 'open-research/observable-notebooks', detail: 'Reproducible notebooks with reviewable history.', meta: 'TypeScript · starred 2 days ago' },
    { title: 'lab-tools/claim-mapper', detail: 'Map claims, evidence, and references across experiments.', meta: 'Python · starred 1 week ago' },
    { title: 'papertrail/markdown-diff', detail: 'Readable diffs for long-form technical writing.', meta: 'Go · starred 2 weeks ago' },
  ],
}

function ProfileTabView({ tab }: { tab: string }) {
  if (tab === 'Repositories') {
    return (
      <section className="panel tab-demo-panel">
        <div className="panel-head"><span>Repositories</span><span className="panel-head-note">4 repositories</span></div>
        <div className="tab-repo-list">
          {repositories.map((repo) => <button className="tab-repo-row" key={repo.name} onClick={() => navigate('/repositories')}><Icon name="repo" size={14} /><span><b>{repo.name}</b><small>{repo.description}</small></span><span className="tab-row-meta">{repo.language} · ★ {repo.stars}</span><Icon name="chevron-right" size={12} /></button>)}
        </div>
      </section>
    )
  }
  return (
    <section className="panel tab-demo-panel">
      <div className="panel-head"><span>{tab}</span><span className="panel-head-note">{tabDemoData[tab]?.length ?? 0} items</span></div>
      <div className="tab-demo-list">
        {(tabDemoData[tab] ?? []).map((item) => <button className="tab-demo-row" key={item.title}><span className="tab-demo-icon"><Icon name={tab === 'Projects' ? 'graph' : tab === 'Packages' ? 'file' : 'commit'} size={14} /></span><span><b>{item.title}</b><small>{item.detail}</small></span><em>{item.meta}</em><Icon name="chevron-right" size={12} /></button>)}
      </div>
    </section>
  )
}
