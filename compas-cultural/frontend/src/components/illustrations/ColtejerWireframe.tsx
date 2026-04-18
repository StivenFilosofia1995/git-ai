/**
 * Edificio Coltejer — wireframe puntillismo de datos.
 * Iconic needle-topped skyscraper of Medellín rendered
 * as a data-pointillism illustration with animated dots.
 */
export default function ColtejerWireframe({ className = '' }: { className?: string }) {
  // Seed-based pseudo-random for consistent renders
  const seed = (n: number) => ((Math.sin(n * 127.1 + 311.7) * 43758.5453) % 1 + 1) % 1

  // Building dimensions
  const W = 60 // body width
  const H = 260 // body height
  const needleH = 80 // needle height
  const totalH = needleH + H + 20
  const viewW = 160
  const viewH = totalH + 40
  const ox = viewW / 2 // center x
  const bodyTop = needleH + 20
  const bodyBot = bodyTop + H

  // Generate window grid dots
  const windowDots: { cx: number; cy: number; r: number; op: number; delay: number }[] = []
  const cols = 10
  const rows = 40
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const s = seed(row * cols + col + 1)
      const s2 = seed(row * cols + col + 500)
      windowDots.push({
        cx: ox - W / 2 + 4 + col * ((W - 8) / (cols - 1)),
        cy: bodyTop + 6 + row * ((H - 12) / (rows - 1)),
        r: 0.8 + s * 0.8,
        op: 0.15 + s2 * 0.45,
        delay: s * 6,
      })
    }
  }

  // Needle dots
  const needleDots: { cx: number; cy: number; r: number; op: number }[] = []
  for (let i = 0; i < 35; i++) {
    const t = i / 34
    needleDots.push({
      cx: ox,
      cy: 15 + t * needleH,
      r: 0.4 + (1 - t) * 0.6,
      op: 0.3 + t * 0.4,
    })
  }

  // Data stream dots (floating particles representing data flow)
  const dataDots: { cx: number; cy: number; r: number; delay: number }[] = []
  for (let i = 0; i < 50; i++) {
    const s = seed(i + 2000)
    const s2 = seed(i + 3000)
    const side = s > 0.5 ? 1 : -1
    dataDots.push({
      cx: ox + side * (W / 2 + 5 + s2 * 30),
      cy: bodyTop + s * H,
      r: 0.3 + s2 * 0.7,
      delay: s * 8,
    })
  }

  // Horizontal floor lines
  const floors: number[] = []
  for (let i = 0; i <= 8; i++) {
    floors.push(bodyTop + i * (H / 8))
  }

  return (
    <svg
      viewBox={`0 0 ${viewW} ${viewH}`}
      className={`w-40 h-auto text-black ${className}`}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Edificio Coltejer en estilo puntillismo de datos"
    >
      <defs>
        <style>{`
          @keyframes colt-pulse {
            0%, 100% { opacity: var(--base-op); }
            50% { opacity: 0.9; }
          }
          @keyframes colt-float {
            0% { transform: translateY(0); opacity: 0.15; }
            50% { opacity: 0.4; }
            100% { transform: translateY(-20px); opacity: 0; }
          }
        `}</style>
      </defs>

      {/* Building wireframe outline — very faint */}
      <g opacity="0.08" stroke="currentColor" strokeWidth="0.5">
        {/* Body */}
        <rect x={ox - W / 2} y={bodyTop} width={W} height={H} />
        {/* Needle */}
        <line x1={ox} y1={15} x2={ox} y2={bodyTop} />
        {/* Needle base triangle */}
        <line x1={ox - 8} y1={bodyTop} x2={ox} y2={bodyTop - 15} />
        <line x1={ox + 8} y1={bodyTop} x2={ox} y2={bodyTop - 15} />
        {/* Floor lines */}
        {floors.map((y, i) => (
          <line key={`fl${i}`} x1={ox - W / 2} y1={y} x2={ox + W / 2} y2={y} />
        ))}
      </g>

      {/* Needle dots */}
      <g>
        {needleDots.map((d, i) => (
          <circle
            key={`nd${i}`}
            cx={d.cx}
            cy={d.cy}
            r={d.r}
            fill="currentColor"
            opacity={d.op}
          />
        ))}
      </g>

      {/* Needle base — small triangle of dots */}
      {Array.from({ length: 12 }, (_, i) => {
        const t = i / 11
        const spread = t * 8
        return (
          <g key={`nb${i}`}>
            <circle cx={ox - spread} cy={bodyTop - 15 + t * 15} r={0.6} fill="currentColor" opacity={0.3} />
            <circle cx={ox + spread} cy={bodyTop - 15 + t * 15} r={0.6} fill="currentColor" opacity={0.3} />
          </g>
        )
      })}

      {/* Window grid — pointillism core */}
      <g>
        {windowDots.map((d, i) => (
          <circle
            key={`wd${i}`}
            cx={d.cx}
            cy={d.cy}
            r={d.r}
            fill="currentColor"
            style={{
              '--base-op': d.op,
              animation: `colt-pulse ${3 + d.delay}s ease-in-out infinite`,
              animationDelay: `${d.delay}s`,
            } as React.CSSProperties}
          />
        ))}
      </g>

      {/* Vertical edge emphasis dots */}
      {Array.from({ length: 25 }, (_, i) => {
        const y = bodyTop + i * (H / 24)
        return (
          <g key={`ve${i}`}>
            <circle cx={ox - W / 2} cy={y} r={1} fill="currentColor" opacity={0.2} />
            <circle cx={ox + W / 2} cy={y} r={1} fill="currentColor" opacity={0.2} />
          </g>
        )
      })}

      {/* Floating data particles */}
      <g>
        {dataDots.map((d, i) => (
          <circle
            key={`dd${i}`}
            cx={d.cx}
            cy={d.cy}
            r={d.r}
            fill="currentColor"
            style={{
              animation: `colt-float ${4 + d.delay}s ease-in-out infinite`,
              animationDelay: `${d.delay}s`,
            }}
          />
        ))}
      </g>

      {/* Ground line — dots */}
      <g>
        {Array.from({ length: 30 }, (_, i) => (
          <circle
            key={`gl${i}`}
            cx={ox - 60 + i * 4}
            cy={bodyBot + 2}
            r={0.5 + seed(i + 9000) * 0.5}
            fill="currentColor"
            opacity={0.12 + seed(i + 9500) * 0.1}
          />
        ))}
      </g>

      {/* Data label — small text */}
      <text
        x={ox}
        y={bodyBot + 16}
        textAnchor="middle"
        fill="currentColor"
        fontSize="5"
        fontFamily="monospace"
        opacity="0.2"
        letterSpacing="0.15em"
      >
        COLTEJER
      </text>
    </svg>
  )
}
