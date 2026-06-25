import type { ReactNode } from 'react'

interface BadgeProps {
  children: ReactNode
  variant?: 'default' | 'outline'
  className?: string
}

export default function Badge({ children, variant = 'outline', className = '' }: Readonly<BadgeProps>) {
  const baseClasses = 'inline-block px-2 py-1 text-xs font-mono uppercase tracking-wide'
  const variantClasses = variant === 'outline' ? 'border' : 'bg-black text-white'

  return (
    <span className={`${baseClasses} ${variantClasses} ${className}`}>
      {children}
    </span>
  )
}