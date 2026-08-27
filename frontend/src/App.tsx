import { useState } from 'react'
import { AppShell } from './layouts/AppShell'
import { DashboardPreview } from './pages/DashboardPreview'
import { LandingPreview } from './pages/LandingPreview'
import { ProPreview } from './pages/ProPreview'
import type { PreviewView } from './types'

function App() {
  const [view, setView] = useState<PreviewView>('landing')
  const isLandingRoute = window.location.pathname === '/'

  if (isLandingRoute) {
    return (
      <AppShell activeView="landing" onViewChange={setView} previewMode={false}>
        <LandingPreview onNavigate={setView} realLanding />
      </AppShell>
    )
  }

  return (
    <AppShell activeView={view} onViewChange={setView}>
      {view === 'landing' && <LandingPreview onNavigate={setView} />}
      {view === 'dashboard' && <DashboardPreview onNavigate={setView} />}
      {view === 'pro' && <ProPreview onNavigate={setView} />}
    </AppShell>
  )
}

export default App
