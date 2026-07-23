import { useState, useEffect, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

interface IgColEvent {
  titulo: string
  fecha_inicio: string
  categoria_principal?: string
  municipio?: string
  nombre_lugar?: string
  descripcion?: string
  precio?: string
  es_gratuito?: boolean
  ig_usuario?: string
  fuente_url?: string
}

interface JobStatus {
  status: string
  progress?: number
  profiles_done?: number
  profiles_total?: number
  current_profile?: string
  events_count?: number
  events?: IgColEvent[]
  error?: string
}

const CAT_LABEL: Record<string, string> = {
  teatro: 'Teatro', hip_hop: 'Hip Hop', jazz: 'Jazz', galeria: 'Galería',
  arte_contemporaneo: 'Arte', electronica: 'Electrónica', danza: 'Danza',
  musica_en_vivo: 'Música', literatura: 'Literatura', festival: 'Festival',
  cine: 'Cine', fotografia: 'Foto', filosofia: 'Filosofía', taller: 'Taller',
  circo: 'Circo', conferencia: 'Charla', otro: 'Otro',
}

const STATUS_LABEL: Record<string, string> = {
  iniciando: 'Iniciando Playwright...',
  iniciando_sesion: 'Iniciando sesión en Instagram...',
  esperando_autenticacion: 'Verificando acceso...',
  escaneando_perfiles: 'Escaneando perfiles de colectivos...',
  done: 'Completado',
  error: 'Error',
}

const DEFAULT_HANDLES = [
  'platohedro', 'casakolacho', 'festivaldepoesiamedellin',
  'teatroelparque', 'lacasita.mde', 'elementosurbanos',
  'accionimpro', 'eltejarrafe', 'redculturalmedellin',
  'circuitoculturalestacion', 'culturaencomun', 'artesabiertos',
]

export default function IgColectivosScanner({ apiKey }: { apiKey: string }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [handlesText, setHandlesText] = useState(DEFAULT_HANDLES.join('\n'))
  const [maxPosts, setMaxPosts] = useState(12)
  const [scanning, setScanning] = useState(false)
  const [jobId, setJobId] = useState('')
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)
  const [events, setEvents] = useState<IgColEvent[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ nuevos: number; errores: number } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId) return
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/admin/ig-colectivos-scan/${jobId}`, {
          headers: { 'X-API-Key': apiKey },
        })
        if (!res.ok) return
        const data: JobStatus = await res.json()
        setJobStatus(data)
        if (data.status === 'done' || data.status === 'error') {
          clearInterval(pollRef.current!)
          setScanning(false)
          if (data.events) {
            setEvents(data.events)
            setSelected(new Set(data.events.map((_, i) => i)))
          }
        }
      } catch { /* ignore */ }
    }, 3000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [jobId, apiKey])

  const handles = handlesText.split(/[\n,\s]+/).map(h => h.trim().replace(/^@/, '')).filter(Boolean)

  const handleScan = async () => {
    if (!email || !password || handles.length === 0) return
    setScanning(true)
    setJobStatus(null)
    setEvents([])
    setSelected(new Set())
    setImportResult(null)
    try {
      const res = await fetch(`${API_BASE}/admin/ig-colectivos-scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify({ email, password, handles, max_posts_per_profile: maxPosts }),
      })
      const data = await res.json()
      if (data.job_id) {
        setJobId(data.job_id)
      } else {
        setScanning(false)
        setJobStatus({ status: 'error', error: data.detail || 'Error iniciando escaneo' })
      }
    } catch (e) {
      setScanning(false)
      setJobStatus({ status: 'error', error: String(e) })
    }
  }

  const handleImport = async () => {
    if (selected.size === 0) return
    setImporting(true)
    const toImport = [...selected].map(i => events[i])
    try {
      const res = await fetch(`${API_BASE}/admin/ig-colectivos-import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify({ eventos: toImport }),
      })
      const data = await res.json()
      setImportResult({ nuevos: data.nuevos, errores: data.errores })
    } catch {
      setImportResult({ nuevos: 0, errores: selected.size })
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Aviso */}
      <div className="border-2 border-yellow-400 bg-yellow-50 p-4 font-mono text-[11px] space-y-1">
        <p className="font-bold uppercase tracking-widest text-yellow-800">¿Cómo funciona?</p>
        <p className="text-yellow-700">
          Inicia sesión en Instagram y visita los perfiles de cada colectivo. Analiza sus posts
          más recientes con Claude Haiku Vision para detectar afiches de eventos con fechas.
          Mucho más potente que escanear solo tu propio feed.
        </p>
        <p className="text-yellow-700">
          Usá una cuenta secundaria dedicada con 2FA desactivado. Las credenciales nunca se almacenan.
        </p>
      </div>

      {/* Credenciales */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block font-mono text-[10px] uppercase tracking-widest mb-1 font-bold">
            Correo / usuario de Instagram
          </label>
          <input type="email" value={email} onChange={e => setEmail(e.target.value)}
            placeholder="cuenta@ejemplo.com" disabled={scanning}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm focus:outline-none" autoComplete="off" />
        </div>
        <div>
          <label className="block font-mono text-[10px] uppercase tracking-widest mb-1 font-bold">
            Contraseña de Instagram
          </label>
          <input type="password" value={password} onChange={e => setPassword(e.target.value)}
            placeholder="••••••••" disabled={scanning}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm focus:outline-none" autoComplete="new-password" />
        </div>
      </div>

      {/* Handles */}
      <div>
        <label className="block font-mono text-[10px] uppercase tracking-widest mb-1 font-bold">
          Perfiles a escanear — uno por línea o separados por coma ({handles.length} cargados)
        </label>
        <textarea
          rows={8}
          value={handlesText}
          onChange={e => setHandlesText(e.target.value)}
          disabled={scanning}
          placeholder="platohedro&#10;casakolacho&#10;teatroelparque"
          className="w-full border-2 border-black px-3 py-2 font-mono text-xs focus:outline-none resize-y"
        />
        <p className="font-mono text-[9px] text-neutral-400 mt-1">Sin @ · Se usa la lista almacenada en BD si está vacío</p>
      </div>

      {/* Config + botón */}
      <div className="flex items-center gap-6">
        <div>
          <label className="block font-mono text-[10px] uppercase tracking-widest mb-1 font-bold">Posts por perfil</label>
          <select value={maxPosts} onChange={e => setMaxPosts(Number(e.target.value))} disabled={scanning}
            className="border-2 border-black px-3 py-2 font-mono text-sm bg-white">
            <option value={6}>6 posts (rápido)</option>
            <option value={12}>12 posts</option>
            <option value={20}>20 posts (lento)</option>
          </select>
        </div>
        <div className="pt-5">
          <button onClick={handleScan} disabled={scanning || !email || !password || handles.length === 0}
            className="px-6 py-2.5 bg-black text-white font-mono text-[11px] font-bold uppercase tracking-widest disabled:opacity-40 hover:bg-yellow-400 hover:text-black transition-colors border-2 border-black">
            {scanning ? 'Escaneando...' : `Escanear ${handles.length} colectivos`}
          </button>
        </div>
      </div>

      {/* Progreso */}
      {(scanning || jobStatus) && (
        <div className="border-2 border-black p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[11px] font-bold uppercase tracking-widest">
              {STATUS_LABEL[jobStatus?.status ?? 'iniciando'] ?? jobStatus?.status}
            </p>
            {jobStatus?.current_profile && (
              <p className="font-mono text-[10px] text-neutral-500">{jobStatus.current_profile}</p>
            )}
          </div>

          {jobStatus?.progress !== undefined && (
            <div className="w-full bg-neutral-100 border border-black h-2">
              <div className="h-full bg-black transition-all duration-500" style={{ width: `${jobStatus.progress}%` }} />
            </div>
          )}

          {jobStatus?.profiles_total && (
            <p className="font-mono text-[10px] text-neutral-500">
              {jobStatus.profiles_done ?? 0} / {jobStatus.profiles_total} perfiles · {events.length} eventos detectados
            </p>
          )}

          {jobStatus?.status === 'error' && (
            <p className="font-mono text-[11px] text-red-600 border border-red-200 bg-red-50 px-3 py-2">
              {jobStatus.error}
            </p>
          )}
        </div>
      )}

      {/* Resultados */}
      {events.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-heading font-black text-xl">{events.length} eventos detectados</h3>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSelected(selected.size === events.length ? new Set() : new Set(events.map((_, i) => i)))}
                className="font-mono text-[10px] uppercase tracking-widest border border-black px-3 py-1.5 hover:bg-black hover:text-white transition-colors"
              >
                {selected.size === events.length ? 'Quitar todo' : 'Seleccionar todo'}
              </button>
              <button onClick={handleImport} disabled={selected.size === 0 || importing}
                className="px-5 py-2 bg-black text-white font-mono text-[11px] font-bold uppercase tracking-widest disabled:opacity-40 hover:bg-yellow-400 hover:text-black transition-colors border-2 border-black">
                {importing ? 'Importando...' : `Importar ${selected.size} eventos`}
              </button>
            </div>
          </div>

          {importResult && (
            <div className={`border-2 p-3 font-mono text-[11px] ${importResult.errores > 0 ? 'border-red-400 bg-red-50' : 'border-green-400 bg-green-50'}`}>
              ✅ Importados: <strong>{importResult.nuevos}</strong> nuevos
              {importResult.errores > 0 && ` · ${importResult.errores} errores`}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {events.map((ev, i) => (
              <div key={i}
                onClick={() => { const n = new Set(selected); n.has(i) ? n.delete(i) : n.add(i); setSelected(n) }}
                className={`border-2 p-3 cursor-pointer transition-colors ${selected.has(i) ? 'border-black bg-yellow-50' : 'border-neutral-300 hover:border-black/50'}`}
              >
                <div className="flex items-start gap-2 mb-2">
                  <div className={`mt-0.5 w-4 h-4 border-2 flex-shrink-0 flex items-center justify-center ${selected.has(i) ? 'border-black bg-black' : 'border-neutral-400'}`}>
                    {selected.has(i) && (
                      <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="font-mono text-[11px] font-bold leading-tight line-clamp-2">{ev.titulo}</p>
                    {ev.ig_usuario && <p className="font-mono text-[9px] text-neutral-400 mt-0.5">{ev.ig_usuario}</p>}
                  </div>
                </div>
                <div className="space-y-0.5 text-[10px] font-mono">
                  <p><span className="text-neutral-400">Fecha:</span> {ev.fecha_inicio?.slice(0, 10) || '—'}</p>
                  <p><span className="text-neutral-400">Lugar:</span> {ev.nombre_lugar || '—'}</p>
                  <p>
                    <span className="bg-black text-white px-1">{CAT_LABEL[ev.categoria_principal ?? ''] ?? ev.categoria_principal ?? 'otro'}</span>
                    {ev.es_gratuito && <span className="ml-1 bg-green-200 text-green-800 px-1">Gratis</span>}
                  </p>
                  {ev.descripcion && <p className="text-neutral-500 line-clamp-2 mt-1">{ev.descripcion}</p>}
                </div>
                {ev.fuente_url && (
                  <a href={ev.fuente_url} target="_blank" rel="noopener noreferrer"
                    onClick={e => e.stopPropagation()}
                    className="block mt-2 font-mono text-[9px] text-blue-600 hover:underline truncate">
                    Ver perfil →
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {jobStatus?.status === 'done' && events.length === 0 && (
        <div className="border-2 border-black p-6 text-center">
          <p className="font-mono text-sm text-neutral-500">No se detectaron eventos en los afiches de estos colectivos.</p>
          <p className="font-mono text-[10px] text-neutral-400 mt-1">Probá aumentando el número de posts por perfil o actualizando la lista.</p>
        </div>
      )}
    </div>
  )
}
