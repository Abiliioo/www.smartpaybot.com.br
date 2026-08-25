import type { ButtonHTMLAttributes, ReactNode } from 'react'
import type { ButtonVariant } from '../types'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode
  variant?: ButtonVariant
}

export function Button({ children, variant = 'primary', className = '', ...props }: ButtonProps) {
  return (
    <button className={`spb-button spb-button--${variant} ${className}`.trim()} type="button" {...props}>
      {children}
    </button>
  )
}
