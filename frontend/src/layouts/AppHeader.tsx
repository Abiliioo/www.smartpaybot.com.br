import { BrandMark } from '../components/BrandMark'
import { PreviewNav } from '../components/PreviewNav'
import { UserBadge } from '../components/UserBadge'
import type { PreviewView } from '../types'

type AppHeaderProps = {
  activeView: PreviewView
  onViewChange: (view: PreviewView) => void
  previewMode?: boolean
}

export function AppHeader({ activeView, onViewChange, previewMode = true }: AppHeaderProps) {
  return (
    <header className="spb-app-header">
      <BrandMark />
      {previewMode && <PreviewNav activeView={activeView} onViewChange={onViewChange} />}
      {previewMode && <UserBadge />}
    </header>
  )
}
