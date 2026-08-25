import type { ReactNode } from 'react'

type PillProps = {
  children: ReactNode
  tone?: 'blue' | 'green' | 'amber' | 'muted'
}

export function Pill({ children, tone = 'blue' }: PillProps) {
  return <span className={`spb-pill spb-pill--${tone}`}>{children}</span>
}
