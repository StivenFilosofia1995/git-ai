interface ChipProps {
  children: React.ReactNode
  active?: boolean
  onClick?: () => void
  className?: string
}

export default function Chip({ children, active = false, onClick, className = '' }: ChipProps) {
  const baseClasses = 'inline-block px-3 py-1 text-xs font-mono uppercase border transition-colors'
  const stateClasses = active
    ? 'border-black bg-black text-white'
    : 'border-black hover:bg-black hover:text-white'

  return (
    <span
      className={`${baseClasses} ${stateClasses} ${onClick ? 'cursor-pointer' : ''} ${className}`}
      onClick={onClick}
    >
      {children}
    </span>
  )
}