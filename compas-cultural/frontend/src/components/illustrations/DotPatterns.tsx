/**
 * Patrón decorativo de puntos para fondos — estilo puntillismo.
 * Genera un campo de dots con densidad variable.
 */
export function DotPattern({ className = '', density = 200 }: { className?: string; density?: number }) {
  return (
    <svg className={className} viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      {Array.from({ length: density }, (_, i) => (
        <circle
          key={i}
          cx={Math.random() * 400}
          cy={Math.random() * 400}
          r={0.5 + Math.random() * 1.5}
          fill="currentColor"
          opacity={0.03 + Math.random() * 0.06}
        />
      ))}
    </svg>
  )
}

/**
 * Dot divider — línea decorativa de puntos.
 */
export function DotDivider({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center gap-1 ${className}`} aria-hidden="true">
      {Array.from({ length: 40 }, (_, i) => (
        <span
          key={i}
          className="block rounded-full bg-current"
          style={{
            width: `${1.5 + Math.random() * 2}px`,
            height: `${1.5 + Math.random() * 2}px`,
            opacity: 0.1 + Math.random() * 0.15,
          }}
        />
      ))}
    </div>
  )
}

/**
 * Icono de zona cultural en estilo puntillismo
 */
const ZONE_ICONS: Record<string, JSX.Element> = {
  'arte': (
    <g>
      <circle cx="12" cy="8" r="3" fill="none" stroke="currentColor" strokeWidth="0.5" strokeDasharray="1 1" />
      <line x1="12" y1="11" x2="12" y2="20" stroke="currentColor" strokeWidth="0.5" strokeDasharray="1 2" />
      <line x1="8" y1="20" x2="16" y2="20" stroke="currentColor" strokeWidth="0.5" />
    </g>
  ),
  'musica': (
    <g>
      {[0, 1, 2, 3, 4].map(i => (
        <circle key={i} cx={6 + i * 3} cy={14 - Math.sin(i * 0.8) * 4} r="1" fill="currentColor" opacity={0.3 + i * 0.1} />
      ))}
      <path d="M6 10 Q12 4 18 10" fill="none" stroke="currentColor" strokeWidth="0.4" opacity="0.3" />
    </g>
  ),
  'teatro': (
    <g>
      <circle cx="12" cy="10" r="5" fill="none" stroke="currentColor" strokeWidth="0.5" strokeDasharray="1 1.5" />
      <path d="M9 9 Q12 12 15 9" fill="none" stroke="currentColor" strokeWidth="0.5" />
      <circle cx="10" cy="8" r="0.8" fill="currentColor" opacity="0.4" />
      <circle cx="14" cy="8" r="0.8" fill="currentColor" opacity="0.4" />
    </g>
  ),
  'urbano': (
    <g>
      {Array.from({ length: 12 }, (_, i) => (
        <circle key={i} cx={4 + (i % 4) * 5} cy={6 + Math.floor(i / 4) * 5} r="1.2" fill="currentColor" opacity={0.15 + Math.random() * 0.2} />
      ))}
    </g>
  ),
}

export function ZoneIcon({ type = 'arte', className = '' }: { type?: string; className?: string }) {
  const icon = ZONE_ICONS[type] ?? ZONE_ICONS.arte
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" xmlns="http://www.w3.org/2000/svg">
      {icon}
    </svg>
  )
}
