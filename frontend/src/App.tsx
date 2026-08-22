import { AppProvider } from './state/store'
import { AppShell } from './components/AppShell'
import { Toasts } from './components/ui'
import { useRoute } from './lib/router'
import { WorkspacePage } from './pages/WorkspacePage'
import { ArtifactPage } from './pages/ArtifactPage'
import { HistoryPage } from './pages/HistoryPage'
import { DiffPage } from './pages/DiffPage'
import { MergePage } from './pages/MergePage'
import { SearchPage } from './pages/SearchPage'

function Routes() {
  const route = useRoute()
  const [first, second] = route.segments

  if (first === 'search') return <SearchPage />
  if (first === 'art' && second) {
    const id = decodeURIComponent(second)
    switch (route.segments[2]) {
      case 'history':
        return <HistoryPage artifactId={id} />
      case 'diff':
        return <DiffPage artifactId={id} />
      case 'merge':
        return <MergePage artifactId={id} />
      default:
        return <ArtifactPage artifactId={id} />
    }
  }
  return <WorkspacePage />
}

function App() {
  return (
    <AppProvider>
      <AppShell>
        <Routes />
      </AppShell>
      <Toasts />
    </AppProvider>
  )
}

export default App
