import { navigate } from '../lib/router'
import { useApp } from '../state/store'
import { Icon } from '../components/Icon'

const profileTabs = ['Overview', 'Repositories', 'Projects', 'Packages', 'Stars']

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

const contributionLevels = [
  0, 0, 0, 0, 1, 0, 2, 3, 2, 1, 3, 0, 2, 4, 0, 1, 2, 5, 2, 0, 1, 3, 0, 2, 1, 4,
  2, 0, 3, 2, 1, 0, 2, 4, 1, 0, 3, 2, 0, 1, 2, 4, 3, 1, 0, 2, 3, 4, 2, 1, 1, 0,
  2, 4, 1, 0, 3, 1,
]

const activity = [
  'Updated the diff alignment model for research artifacts and notes.',
  'Reviewed a reindexing pipeline for better semantic chunking performance.',
  'Merged a collaborative workspace proposal for multi-user annotation sessions.',
]

export function DashboardPage() {
  const { connection } = useApp()
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
        {profileTabs.map((tab, index) => (
          <button key={tab} className={index === 0 ? 'active' : ''} type="button">
            {tab}
          </button>
        ))}
      </nav>

      <div className="profile-grid">
        <aside className="profile-sidebar">
          <section className="panel profile-card">
            <div className="panel-head">About</div>
            <div className="profile-card-body">
              <p>
                Building tools for human-centered research workflows, documentation, and open
                collaboration across code, notes, and experiments.
              </p>
            </div>
          </section>

          <section className="panel profile-card">
            <div className="panel-head">Highlights</div>
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
        </aside>

        <main className="profile-main">
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
              <div className="day-labels">
                <span>Mon</span>
                <span>Wed</span>
                <span>Fri</span>
              </div>
              <div className="contrib-grid" aria-label="Contribution graph">
                {contributionLevels.map((level, index) => (
                  <span
                    key={`${level}-${index}`}
                    className={`contrib-cell level-${level}`}
                    title={`Contribution level ${level}`}
                  />
                ))}
              </div>
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
        </main>
      </div>

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
    </div>
  )
}
