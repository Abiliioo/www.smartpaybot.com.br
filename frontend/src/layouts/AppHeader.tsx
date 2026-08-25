import { BrandMark } from '../components/BrandMark'
import { PreviewNav } from '../components/PreviewNav'
import { UserBadge } from '../components/UserBadge'
import type { PreviewView } from '../types'

type AppHeaderProps = {
  activeView: PreviewView
  onViewChange: (view: PreviewView) => void
}

export function AppHeader({ activeView, onViewChange }: AppHeaderProps) {
  return (
    <header className="spb-app-header">
      <BrandMark />
      <PreviewNav activeView={activeView} onViewChange={onViewChange} />
      <UserBadge />
    </header>
  )
}
