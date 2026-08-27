import type { AnchorHTMLAttributes, ButtonHTMLAttributes, ReactNode } from 'react'
import type { ButtonVariant } from '../types'

type ButtonBaseProps = {
  children: ReactNode
  variant?: ButtonVariant
  className?: string
}

type ButtonProps = ButtonBaseProps & ButtonHTMLAttributes<HTMLButtonElement> & { href?: undefined }
type ButtonLinkProps = ButtonBaseProps & AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }

export function Button(props: ButtonProps | ButtonLinkProps) {
  const { children, variant = 'primary', className = '', href, ...rest } = props
  const classes = `spb-button spb-button--${variant} ${className}`.trim()

  if (href) {
    const linkProps = rest as AnchorHTMLAttributes<HTMLAnchorElement>
    return (
      <a className={classes} href={href} {...linkProps}>
        {children}
      </a>
    )
  }

  const buttonProps = rest as ButtonHTMLAttributes<HTMLButtonElement>
  return (
    <button className={classes} type="button" {...buttonProps}>
      {children}
    </button>
  )
}
