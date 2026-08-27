import type { ReactNode } from 'react'
import { AppHeader } from './AppHeader'
import type { PreviewView } from '../types'

type AppShellProps = {
  activeView: PreviewView
  onViewChange: (view: PreviewView) => void
  previewMode?: boolean
  children: ReactNode
}

export function AppShell({ activeView, onViewChange, previewMode = true, children }: AppShellProps) {
  return (
    <div className={`spb-app-shell ${previewMode ? '' : 'spb-app-shell--landing'}`.trim()}>
      <AppHeader activeView={activeView} onViewChange={onViewChange} previewMode={previewMode} />
      {children}
    </div>
  )
}
