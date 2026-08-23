import { useState } from 'react'
import { navigate } from '../lib/router'
import { Icon } from '../components/Icon'

type FeedPost = {
  id: string
  person: string
  handle: string
  initials: string
  color: string
  action: string
  time: string
  title: string
  body: string
  repo: string
  tags: string[]
}

const posts: FeedPost[] = [
  {
    id: 'p1', person: 'Aisha Rahman', handle: '@aishar', initials: 'AR', color: '#8b7cf6', action: 'published a research note', time: '18 min ago',
    title: 'When a clean loss curve is hiding instability', body: 'A short note on why aggregate metrics can conceal a sharp divergence in one subgroup. Sharing the evidence trail and the failed runs alongside the result.', repo: 'training-dynamics', tags: ['research note', 'machine learning'],
  },
  {
    id: 'p2', person: 'Jon Bell', handle: '@jonbell', initials: 'JB', color: '#d9a441', action: 'opened a discussion', time: '2 hrs ago',
    title: 'How should we cite a moving dataset?', body: 'Looking for conventions that preserve the exact snapshot used in an analysis without making the citation unreadable. I collected three approaches here.', repo: 'reproducible-data', tags: ['discussion', 'provenance'],
  },
  {
    id: 'p3', person: 'Mina Okafor', handle: '@mina-o', initials: 'MO', color: '#57c47a', action: 'merged a change', time: 'Yesterday',
    title: 'Add uncertainty bands to the ablation report', body: 'The report now carries the raw run references and the commit that generated each figure. This makes review much easier than passing around exported PDFs.', repo: 'lab-notes', tags: ['merged', 'visualization'],
  },
]

const suggestions = [
  { name: 'Aisha Rahman', handle: '@aishar', initials: 'AR', color: '#8b7cf6', detail: 'ML systems · 12 repositories' },
  { name: 'Jon Bell', handle: '@jonbell', initials: 'JB', color: '#d9a441', detail: 'Open data · 8 repositories' },
  { name: 'Mina Okafor', handle: '@mina-o', initials: 'MO', color: '#57c47a', detail: 'Research tooling · 16 repositories' },
]

export function FeedPage() {
  const [following, setFollowing] = useState<string[]>(['@aishar', '@mina-o'])
  const [feedMode, setFeedMode] = useState<'following' | 'discover'>('following')
  const toggleFollow = (handle: string) => setFollowing((current) => current.includes(handle) ? current.filter((item) => item !== handle) : [...current, handle])

  const visiblePosts = feedMode === 'following' ? posts.filter((post) => following.includes(post.handle)) : posts

  return (
    <div className="page feed-page">
      <div className="page-head">
        <div><h1>Feed</h1><p className="page-sub">See what researchers you follow are publishing, discussing, and changing.</p></div>
        <button className="btn primary" onClick={() => navigate('/repositories')}><Icon name="repo" size={13} /> Share from a repository</button>
      </div>

      <div className="feed-layout">
        <main className="feed-main">
          <div className="feed-tabs" role="tablist">
            <button className={feedMode === 'following' ? 'active' : ''} onClick={() => setFeedMode('following')} role="tab" aria-selected={feedMode === 'following'}>Following <span>{following.length}</span></button>
            <button className={feedMode === 'discover' ? 'active' : ''} onClick={() => setFeedMode('discover')} role="tab" aria-selected={feedMode === 'discover'}>Discover</button>
          </div>
          {visiblePosts.map((post) => <FeedCard key={post.id} post={post} isFollowing={following.includes(post.handle)} onFollow={() => toggleFollow(post.handle)} />)}
          {visiblePosts.length === 0 && <div className="panel state-block"><div className="state-title">Your following feed is empty</div><p>Discover researchers to see their activity here.</p><button className="btn sm" onClick={() => setFeedMode('discover')} style={{ marginTop: 10 }}>Discover people</button></div>}
        </main>

        <aside className="feed-sidebar">
          <section className="panel feed-profile-card">
            <div className="feed-profile-top"><span className="feed-avatar self">M</span><div><b>Muneer</b><small>@muneer320</small></div></div>
            <div className="feed-counts"><span><b>4</b> repositories</span><span><b>18</b> branches</span></div>
            <div className="feed-counts"><span><b>24</b> followers</span><span><b>{following.length}</b> following</span></div>
          </section>
          <section className="panel suggestions-card">
            <div className="panel-head">People to follow</div>
            {suggestions.map((person) => <div className="suggestion-row" key={person.handle}><span className="feed-avatar" style={{ background: person.color }}>{person.initials}</span><span className="suggestion-copy"><b>{person.name}</b><small>{person.handle} · {person.detail}</small></span><button className={`btn sm ${following.includes(person.handle) ? 'following' : ''}`} onClick={() => toggleFollow(person.handle)}>{following.includes(person.handle) ? 'Following' : 'Follow'}</button></div>)}
          </section>
          <p className="feed-disclaimer">Activity is shared manually from public research repositories. No private drafts are exposed.</p>
        </aside>
      </div>
    </div>
  )
}

function FeedCard({ post, isFollowing, onFollow }: { post: FeedPost; isFollowing: boolean; onFollow: () => void }) {
  return (
    <article className="feed-post panel">
      <div className="feed-post-head"><span className="feed-avatar" style={{ background: post.color }}>{post.initials}</span><div className="feed-author"><b>{post.person}</b><span>{post.handle} · {post.action} · {post.time}</span></div><button className={`btn ghost sm ${isFollowing ? 'following' : ''}`} onClick={onFollow}>{isFollowing ? 'Following' : 'Follow'}</button></div>
      <div className="feed-post-body"><h2>{post.title}</h2><p>{post.body}</p><button className="feed-repo-link" onClick={() => navigate('/repositories')}><Icon name="repo" size={12} /> {post.repo} <Icon name="chevron-right" size={11} /></button><div className="feed-tags">{post.tags.map((tag) => <span key={tag}>{tag}</span>)}</div></div>
      <div className="feed-post-actions"><button><Icon name="chat" size={12} /> Discuss</button><button><Icon name="star" size={12} /> Star</button><button><Icon name="branch" size={12} /> Follow repository</button></div>
    </article>
  )
}
