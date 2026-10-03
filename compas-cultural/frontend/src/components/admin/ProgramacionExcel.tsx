import { useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

interface Resultado {
  archivo: string
  reparado: boolean
  formatos: Record<string, string>
  eventos: number
  decisiones: Record<string, number>
  descartados: Record<string, number>
  sedes_sin_coordenadas: string[]
  muestra: { titulo: string; fecha_inicio: string; nombre_lugar: string }[]
}

const MOTIVOS: Record<string, string> = {
  grupo_cerrado: 'Grupo cerrado (no se publica)',
  no_abierto_al_publico: 'No abierto al público',
  fecha_pendiente: 'Fecha "pendiente"',
  fechas_pasadas: 'Fechas ya pasadas',
  fecha_no_reconocida: 'Fecha que no se pudo leer',
}

/**
 * Sube los Excel mensuales de la Fundación Grupo EPM (Parque de los Deseos, Museo del Agua,
 * UVA, Biblioteca EPM). Primero "Vista previa" (no guarda) y luego "Publicar".
 * Reimportar el mismo archivo es seguro: no crea duplicados.
 */
export default function ProgramacionExcel({ apiKey }: { apiKey: string }) {
  const [archivos, setArchivos] = useState<File[]>([])
  const [resultados, setResultados] = useState<Resultado[]>([])
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function enviar(aplicar: boolean) {
    setCargando(true)
    setError(null)
    const salida: Resultado[] = []
    for (const f of archivos) {
      const form = new FormData()
      form.append('archivo', f)
      try {
        const res = await fetch(`${API_BASE}/admin/programacion-excel?aplicar=${aplicar}`, {
          method: 'POST', headers: { 'X-API-Key': apiKey }, body: form,
        })
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || `Error ${res.status}`)
        salida.push(data)
      } catch (e) {
        setError(`${f.name}: ${e instanceof Error ? e.message : 'error'}`)
      }
    }
    setResultados(salida)
    setCargando(false)
  }

  return (
    <div className="space-y-5 max-w-3xl">
      <div>
        <h2 className="font-heading font-black text-lg">Programación en Excel (Fundación Grupo EPM)</h2>
        <p className="text-sm text-black/70 mt-1">
          Sube los Excel del mes (Parque de los Deseos, Museo del Agua, UVA, Biblioteca EPM). El sistema reconoce
          el formato, publica solo lo abierto al público y lo ubica en el mapa. Primero revisa con
          <strong> Vista previa</strong>; luego <strong>Publicar</strong>. Subir dos veces el mismo archivo no duplica nada.
        </p>
      </div>

      <label className="block border-2 border-dashed border-black p-5 text-center cursor-pointer hover:bg-black/5">
        <input type="file" accept=".xlsx" multiple className="hidden"
          onChange={e => { setArchivos(Array.from(e.target.files ?? [])); setResultados([]) }} />
        <span className="font-bold">{archivos.length ? `${archivos.length} archivo(s): ${archivos.map(a => a.name).join(', ')}` : 'Elegir archivos .xlsx'}</span>
      </label>

      <div className="flex gap-2">
        <button disabled={!archivos.length || cargando} onClick={() => enviar(false)}
          className="min-h-[44px] px-4 border-2 border-black font-bold disabled:opacity-40 hover:bg-black hover:text-white">
          {cargando ? 'Procesando…' : 'Vista previa'}
        </button>
        <button disabled={!archivos.length || cargando} onClick={() => enviar(true)}
          className="min-h-[44px] px-4 bg-black text-white border-2 border-black font-bold disabled:opacity-40">
          Publicar en la agenda
        </button>
      </div>

      {error && <p className="border-2 border-black bg-red-50 p-3 text-sm">{error}</p>}

      {resultados.map(r => (
        <div key={r.archivo} className="border-2 border-black p-4 space-y-2 text-sm">
          <p className="font-bold">{r.archivo}{r.reparado && ' · (archivo dañado: se reparó)'}</p>
          <p><strong>{r.eventos}</strong> actividades encontradas
            {Object.keys(r.decisiones).length > 0 && ' · ' + Object.entries(r.decisiones).map(([k, v]) => `${v} ${k}`).join(' · ')}</p>
          {Object.keys(r.descartados).length > 0 && (
            <ul className="text-black/70 list-disc pl-5">
              {Object.entries(r.descartados).map(([k, v]) => <li key={k}>{MOTIVOS[k] ?? k}: {v}</li>)}
            </ul>
          )}
          {r.sedes_sin_coordenadas.length > 0 && (
            <p className="bg-yellow-50 border border-yellow-400 p-2">
              Sin ubicación en el mapa (se publican igual): {r.sedes_sin_coordenadas.join(', ')}. Agrega sus coordenadas en
              <code> seeds/data/sedes_epm.json</code>.
            </p>
          )}
          <details>
            <summary className="cursor-pointer underline">Ver muestra</summary>
            <ul className="mt-2 space-y-1">
              {r.muestra.map((m, i) => (
                <li key={i}>{new Date(m.fecha_inicio).toLocaleString('es-CO', { timeZone: 'America/Bogota', dateStyle: 'medium', timeStyle: 'short' })} · {m.titulo} · {m.nombre_lugar}</li>
              ))}
            </ul>
          </details>
        </div>
      ))}
    </div>
  )
}
