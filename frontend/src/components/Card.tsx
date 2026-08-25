import type { HTMLAttributes, ReactNode } from 'react'

type CardProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode
  tone?: 'default' | 'accent' | 'quiet'
}

export function Card({ children, tone = 'default', className = '', ...props }: CardProps) {
  return (
    <div className={`spb-card spb-card--${tone} ${className}`.trim()} {...props}>
      {children}
    </div>
  )
}
