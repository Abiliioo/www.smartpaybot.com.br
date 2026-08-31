import type { PreviewView } from '../types'

type PreviewNavProps = {
  activeView: PreviewView
  onViewChange: (view: PreviewView) => void
}

const items: Array<{ id: PreviewView; label: string }> = [
  { id: 'landing', label: 'Home' },
  { id: 'dashboard', label: 'Painel' },
  { id: 'pro', label: 'Pro' },
]

export function PreviewNav({ activeView, onViewChange }: PreviewNavProps) {
  return (
    <nav className="spb-preview-nav" aria-label="Navegação principal">
      {items.map((item) => (
        <button
          key={item.id}
          className={activeView === item.id ? 'is-active' : ''}
          aria-current={activeView === item.id ? 'page' : undefined}
          type="button"
          onClick={() => onViewChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  )
}
