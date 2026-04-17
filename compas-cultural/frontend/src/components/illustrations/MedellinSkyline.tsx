/**
 * Skyline de Medellín en estilo puntillismo/wireframe:
 * Coltejer, Palacio Rafael Uribe Uribe, montañas del Valle de Aburrá
 */
export default function MedellinSkyline({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 960 320"
      className={className}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Skyline de Medellín en estilo puntillismo"
    >
      {/* --- MONTAÑAS (puntos dispersos) --- */}
      <g opacity="0.12">
        {/* Montaña izquierda */}
        {Array.from({ length: 80 }, (_, i) => {
          const cx = 50 + Math.random() * 300
          const baseY = 320 - (cx - 50) * 0.5
          const cy = baseY - Math.random() * 120
          return cy > 100 ? <circle key={`ml${i}`} cx={cx} cy={cy} r={1 + Math.random() * 1.5} fill="currentColor" /> : null
        })}
        {/* Montaña derecha */}
        {Array.from({ length: 80 }, (_, i) => {
          const cx = 600 + Math.random() * 360
          const baseY = 320 - (960 - cx) * 0.45
          const cy = baseY - Math.random() * 100
          return cy > 120 ? <circle key={`mr${i}`} cx={cx} cy={cy} r={1 + Math.random() * 1.5} fill="currentColor" /> : null
        })}
        {/* Montaña central (fondo) */}
        {Array.from({ length: 60 }, (_, i) => {
          const cx = 300 + Math.random() * 360
          const dist = Math.abs(cx - 480) / 180
          const cy = 140 + dist * 80 + Math.random() * 60
          return <circle key={`mc${i}`} cx={cx} cy={cy} r={0.8 + Math.random()} fill="currentColor" />
        })}
      </g>

      {/* --- COLTEJER (torre icónica con aguja) --- */}
      <g transform="translate(420, 60)">
        {/* Cuerpo principal - puntos en grid */}
        {Array.from({ length: 24 }, (_, row) =>
          Array.from({ length: 6 }, (_, col) => (
            <circle
              key={`ct${row}_${col}`}
              cx={col * 5 + 2}
              cy={row * 10 + 40}
              r={1.2}
              fill="currentColor"
              opacity={0.35 + Math.random() * 0.3}
            />
          ))
        ).flat()}
        {/* Aguja superior */}
        {Array.from({ length: 15 }, (_, i) => (
          <circle
            key={`ca${i}`}
            cx={15}
            cy={i * 2.5}
            r={0.8}
            fill="currentColor"
            opacity={0.5}
          />
        ))}
        {/* Wireframe contorno */}
        <line x1="0" y1="40" x2="0" y2="280" stroke="currentColor" strokeWidth="0.5" opacity="0.15" />
        <line x1="30" y1="40" x2="30" y2="280" stroke="currentColor" strokeWidth="0.5" opacity="0.15" />
        <line x1="15" y1="0" x2="15" y2="40" stroke="currentColor" strokeWidth="0.3" opacity="0.15" strokeDasharray="2 3" />
      </g>

      {/* --- PALACIO RAFAEL URIBE URIBE --- */}
      <g transform="translate(240, 170)">
        {/* Cúpula central (arco de puntos) */}
        {Array.from({ length: 30 }, (_, i) => {
          const angle = Math.PI + (i / 29) * Math.PI
          const rx = 25
          const ry = 20
          return (
            <circle
              key={`pd${i}`}
              cx={40 + Math.cos(angle) * rx}
              cy={-5 + Math.sin(angle) * ry}
              r={1}
              fill="currentColor"
              opacity={0.4}
            />
          )
        })}
        {/* Torres laterales */}
        {[-8, 88].map(x =>
          Array.from({ length: 8 }, (_, i) => (
            <circle
              key={`pt${x}_${i}`}
              cx={x}
              cy={i * 8 + 15}
              r={1}
              fill="currentColor"
              opacity={0.3}
            />
          ))
        ).flat()}
        {/* Fachada - grid de puntos */}
        {Array.from({ length: 6 }, (_, row) =>
          Array.from({ length: 12 }, (_, col) => (
            <circle
              key={`pf${row}_${col}`}
              cx={col * 7 + 2}
              cy={row * 12 + 30}
              r={0.9}
              fill="currentColor"
              opacity={0.2 + row * 0.05}
            />
          ))
        ).flat()}
        {/* Ventanales (clusters más densos) */}
        {Array.from({ length: 4 }, (_, i) => (
          <g key={`pw${i}`}>
            <rect x={10 + i * 20} y={35} width={8} height={14} rx={4}
              stroke="currentColor" strokeWidth="0.4" opacity="0.2" fill="none" />
          </g>
        ))}
        {/* Base wireframe */}
        <line x1="-10" y1="100" x2="90" y2="100" stroke="currentColor" strokeWidth="0.5" opacity="0.15" />
      </g>

      {/* --- EDIFICIOS SECUNDARIOS (siluetas puntillismo) --- */}
      {/* Edificio izquierda */}
      <g transform="translate(160, 180)">
        {Array.from({ length: 10 }, (_, row) =>
          Array.from({ length: 3 }, (_, col) => (
            <circle
              key={`bl${row}_${col}`}
              cx={col * 6}
              cy={row * 14}
              r={0.8}
              fill="currentColor"
              opacity={0.15}
            />
          ))
        ).flat()}
      </g>

      {/* Edificios derechos */}
      <g transform="translate(530, 150)">
        {Array.from({ length: 14 }, (_, row) =>
          Array.from({ length: 4 }, (_, col) => (
            <circle
              key={`br${row}_${col}`}
              cx={col * 5}
              cy={row * 12}
              r={0.7}
              fill="currentColor"
              opacity={0.12 + row * 0.01}
            />
          ))
        ).flat()}
      </g>

      {/* Edificio EPM */}
      <g transform="translate(570, 120)">
        {Array.from({ length: 16 }, (_, row) =>
          Array.from({ length: 8 }, (_, col) => (
            <circle
              key={`epm${row}_${col}`}
              cx={col * 4}
              cy={row * 12.5}
              r={0.6}
              fill="currentColor"
              opacity={0.1 + (row % 3 === 0 ? 0.1 : 0)}
            />
          ))
        ).flat()}
      </g>

      {/* --- METROCABLE (línea de puntos diagonal) --- */}
      {Array.from({ length: 25 }, (_, i) => (
        <circle
          key={`metro${i}`}
          cx={700 + i * 8}
          cy={200 - i * 5}
          r={0.6}
          fill="currentColor"
          opacity={0.2}
        />
      ))}
      {/* Cabina */}
      <rect x="780" y="90" width="6" height="8" rx="1" stroke="currentColor" strokeWidth="0.5" opacity="0.25" fill="none" />

      {/* --- HORIZON LINE (puntos base) --- */}
      {Array.from({ length: 120 }, (_, i) => (
        <circle
          key={`hl${i}`}
          cx={i * 8 + Math.random() * 4}
          cy={318 - Math.random() * 2}
          r={0.5 + Math.random() * 0.5}
          fill="currentColor"
          opacity={0.08 + Math.random() * 0.07}
        />
      ))}
    </svg>
  )
}
