import { useEffect, useRef } from 'react'

/**
 * Ícono vivo de ETÉREA: un icosaedro en wireframe que gira y se dibuja arista por arista,
 * con puntos de datos sobre las aristas (puntillismo) y una nube de partículas orbitando.
 * Canvas 2D (nítido en cualquier pantalla, ~3 KB). Toma el color del texto del contenedor
 * (`currentColor`), así se invierte con el hover del botón. Con `prefers-reduced-motion`
 * queda quieto en un cuadro completo.
 */

const PHI = (1 + Math.sqrt(5)) / 2
const VERTICES: [number, number, number][] = [
  [-1, PHI, 0], [1, PHI, 0], [-1, -PHI, 0], [1, -PHI, 0],
  [0, -1, PHI], [0, 1, PHI], [0, -1, -PHI], [0, 1, -PHI],
  [PHI, 0, -1], [PHI, 0, 1], [-PHI, 0, -1], [-PHI, 0, 1],
].map(([x, y, z]) => {
  const n = Math.hypot(x, y, z)
  return [x / n, y / n, z / n] as [number, number, number]
})

// Aristas: pares de vértices a distancia mínima (30 en total), en un orden que "recorre" la figura
const ARISTAS: [number, number][] = (() => {
  const out: [number, number][] = []
  for (let i = 0; i < VERTICES.length; i++) {
    for (let j = i + 1; j < VERTICES.length; j++) {
      const [a, b] = [VERTICES[i], VERTICES[j]]
      if (Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]) < 1.1) out.push([i, j])
    }
  }
  return out
})()

// Nube de datos: puntos fijos sobre una esfera mayor (espiral de Fibonacci)
const NUBE: [number, number, number][] = Array.from({ length: 46 }, (_, i) => {
  const y = 1 - (i / 45) * 2
  const r = Math.sqrt(1 - y * y)
  const th = i * 2.399963
  return [Math.cos(th) * r * 1.38, y * 1.38, Math.sin(th) * r * 1.38]
})

const CICLO = 7 // segundos: dibujar → sostener → disolver en puntos → volver a dibujar

function rotar([x, y, z]: [number, number, number], ax: number, ay: number): [number, number, number] {
  const cy = Math.cos(ay), sy = Math.sin(ay)
  const x1 = x * cy + z * sy, z1 = -x * sy + z * cy
  const cx = Math.cos(ax), sx = Math.sin(ax)
  return [x1, y * cx - z1 * sx, y * sx + z1 * cx]
}

const suave = (t: number) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2)

interface Props {
  size?: number
  className?: string
  /** Multiplicador de velocidad de giro (p. ej. más rápido en hover). */
  velocidad?: number
  /** Dibujar también la nube de partículas exterior. */
  nube?: boolean
}

export default function IcosaedroEterea({ size = 48, className = '', velocidad = 1, nube = true }: Props) {
  const ref = useRef<HTMLCanvasElement>(null)
  const velRef = useRef(velocidad)
  velRef.current = velocidad

  useEffect(() => {
    const canvas = ref.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const dpr = Math.min(window.devicePixelRatio || 1, 3)
    canvas.width = size * dpr
    canvas.height = size * dpr
    ctx.scale(dpr, dpr)

    const quieto = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const escala = size * 0.3
    const centro = size / 2
    const D = 3.2 // distancia de la cámara (perspectiva)
    let raf = 0
    let t0 = performance.now()
    let giro = 0.6

    const proyectar = (p: [number, number, number]) => {
      const k = D / (D - p[2])
      return { x: centro + p[0] * escala * k, y: centro + p[1] * escala * k, z: p[2] }
    }

    const dibujar = (ahora: number) => {
      const dt = Math.min(0.05, (ahora - t0) / 1000)
      t0 = ahora
      giro += dt * 0.55 * velRef.current
      const t = quieto ? CICLO * 0.6 : (ahora / 1000) % CICLO
      const fase = t / CICLO
      // 0–0.45 se dibuja · 0.45–0.8 completo · 0.8–1 las líneas se disuelven y quedan los puntos
      const trazado = quieto ? 1 : fase < 0.45 ? suave(fase / 0.45) : 1
      const lineas = quieto ? 1 : fase < 0.8 ? 1 : 1 - suave((fase - 0.8) / 0.2)

      const color = getComputedStyle(canvas).color || '#fff'
      ctx.clearRect(0, 0, size, size)
      ctx.fillStyle = color
      ctx.strokeStyle = color
      ctx.lineCap = 'round'

      const ax = quieto ? 0.5 : giro * 0.62
      const ay = quieto ? 0.7 : giro
      const pts = VERTICES.map(v => proyectar(rotar(v, ax, ay)))
      const prof = (z: number) => 0.35 + 0.65 * ((z + 1) / 2) // atrás tenue, adelante pleno

      // Nube de datos alrededor (gira más lento y al revés)
      if (nube) {
        for (const p of NUBE) {
          const q = proyectar(rotar(p, -ax * 0.4, -ay * 0.5))
          ctx.globalAlpha = 0.12 + 0.28 * ((q.z + 1.4) / 2.8)
          ctx.fillRect(q.x - 0.5, q.y - 0.5, 1, 1)
        }
      }

      // Aristas: se dibujan una tras otra según `trazado`
      const total = ARISTAS.length
      ARISTAS.forEach(([i, j], n) => {
        const a = pts[i], b = pts[j]
        const z = (a.z + b.z) / 2
        const parcial = Math.max(0, Math.min(1, trazado * total - n))
        if (parcial > 0 && lineas > 0) {
          ctx.globalAlpha = prof(z) * lineas * 0.9
          ctx.lineWidth = Math.max(0.6, size / 64)
          ctx.beginPath()
          ctx.moveTo(a.x, a.y)
          ctx.lineTo(a.x + (b.x - a.x) * parcial, a.y + (b.y - a.y) * parcial)
          ctx.stroke()
        }
        // Puntillismo: datos sobre cada arista (siempre visibles, tenues)
        for (let s = 1; s < 4; s++) {
          const f = s / 4
          ctx.globalAlpha = prof(z) * (0.25 + 0.5 * (1 - lineas))
          const r = Math.max(0.5, size / 90)
          ctx.beginPath()
          ctx.arc(a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f, r, 0, Math.PI * 2)
          ctx.fill()
        }
      })

      // Vértices: nodos
      for (const p of pts) {
        ctx.globalAlpha = prof(p.z)
        ctx.beginPath()
        ctx.arc(p.x, p.y, Math.max(1, size / 34) * (0.7 + 0.3 * prof(p.z)), 0, Math.PI * 2)
        ctx.fill()
      }
      ctx.globalAlpha = 1
      if (!quieto) raf = requestAnimationFrame(dibujar)
    }

    raf = requestAnimationFrame(dibujar)
    return () => cancelAnimationFrame(raf)
  }, [size, nube])

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      className={className}
      style={{ width: size, height: size, display: 'block' }}
    />
  )
}
