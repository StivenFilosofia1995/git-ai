import { useState, useEffect, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

interface IgEvent {
  titulo: string
  fecha_inicio: string
  fecha_fin?: string
  categoria_principal: string
  municipio: string
  nombre_lugar?: string
  descripcion?: string
  imagen_url?: string
  precio?: string
  es_gratuito?: boolean
  fuente_url?: string
  ig_usuario?: string
  caption_original?: string
}

interface JobStatus {
  status: string
  progress?: number
  posts_captured?: number
  posts_scanned?: number
  events_count?: number
  events?: IgEvent[]
  error?: string
}

const STATUS_LABEL: Record<string, string> = {
  iniciando: 'Iniciando Playwright...',
  navegando: 'Navegando a Instagram...',
  iniciando_sesion: 'Completando formulario de login...',
  esperando_autenticacion: 'Esperando autenticación...',
  escaneando_feed: 'Escaneando el feed...',
  procesando: 'Extrayendo eventos culturales...',
  done: 'Completado',
  error: 'Error',
}

const CAT_LABEL: Record<string, string> = {
  teatro: 'Teatro', hip_hop: 'Hip Hop', jazz: 'Jazz', galeria: 'Galería',
  arte_contemporaneo: 'Arte', electronica: 'Electrónica', danza: 'Danza',
  musica_en_vivo: 'Música', literatura: 'Literatura', festival: 'Festival',
  cine: 'Cine', fotografia: 'Foto', filosofia: 'Filosofía', taller: 'Taller',
  circo: 'Circo', conferencia: 'Charla', otro: 'Otro',
}

export default function IgFeedScanner({ apiKey }: { apiKey: string }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [maxPosts, setMaxPosts] = useState(60)
  const [scanning, setScanning] = useState(false)
  const [jobId, setJobId] = useState('')
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)
  const [events, setEvents] = useState<IgEvent[]>([])
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ nuevos: number; errores: number } | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Polling
  useEffect(() => {
    if (!jobId) return
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/admin/ig-feed-scan/${jobId}`, {
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
      } catch {
        // ignore poll errors
      }
    }, 2000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [jobId, apiKey])

  const handleScan = async () => {
    if (!email || !password) return
    setScanning(true)
    setJobStatus(null)
    setEvents([])
    setSelected(new Set())
    setImportResult(null)
    try {
      const res = await fetch(`${API_BASE}/admin/ig-feed-scan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify({ email, password, max_posts: maxPosts }),
      })
      const data = await res.json()
      if (data.job_id) {
        setJobId(data.job_id)
      } else {
        setScanning(false)
        setJobStatus({ status: 'error', error: data.detail || 'Error iniciando scan' })
      }
    } catch (e) {
      setScanning(false)
      setJobStatus({ status: 'error', error: String(e) })
    }
  }

  const toggleAll = () => {
    if (selected.size === events.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(events.map((_, i) => i)))
    }
  }

  const handleImport = async () => {
    if (selected.size === 0) return
    setImporting(true)
    const toImport = [...selected].map(i => events[i])
    try {
      const res = await fetch(`${API_BASE}/admin/ig-feed-import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify({ eventos: toImport }),
      })
      const data = await res.json()
      setImportResult({ nuevos: data.nuevos, errores: data.errores })
    } catch (e) {
      setImportResult({ nuevos: 0, errores: selected.size })
    } finally {
      setImporting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Aviso de seguridad */}
      <div className="border-2 border-yellow-400 bg-yellow-50 p-4 font-mono text-[11px] space-y-1">
        <p className="font-bold uppercase tracking-widest text-yellow-800">Aviso de seguridad</p>
        <p className="text-yellow-700">
          Las credenciales se transmiten cifradas (HTTPS) y se usan ÚNICAMENTE en memoria
          durante la sesión de scraping. Nunca se almacenan en la base de datos ni en logs.
        </p>
        <p className="text-yellow-700">
          Recomendamos usar una cuenta secundaria de Instagram dedicada a esta plataforma,
          no tu cuenta personal principal. Esta cuenta debe tener el 2FA desactivado.
        </p>
      </div>

      {/* Formulario */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label className="block font-mono text-[10px] uppercase tracking-widest mb-1 font-bold">
            Correo o usuario de Instagram
          </label>
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="correo@ejemplo.com"
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm focus:outline-none focus:border-yellow-400"
            disabled={scanning}
            autoComplete="off"
          />
        </div>
        <div>
          <label className="block font-mono text-[10px] uppercase tracking-widest mb-1 font-bold">
            Contraseña de Instagram
          </label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm focus:outline-none focus:border-yellow-400"
            disabled={scanning}
            autoComplete="new-password"
          />
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div>
          <label className="block font-mono text-[10px] uppercase tracking-widest mb-1 font-bold">
            Posts a revisar
          </label>
          <select
            value={maxPosts}
            onChange={e => setMaxPosts(Number(e.target.value))}
            disabled={scanning}
            className="border-2 border-black px-3 py-2 font-mono text-sm focus:outline-none bg-white"
          >
            <option value={30}>30 posts</option>
            <option value={60}>60 posts</option>
            <option value={90}>90 posts</option>
            <option value={120}>120 posts (lento)</option>
          </select>
        </div>
        <div className="pt-5">
          <button
            onClick={handleScan}
            disabled={scanning || !email || !password}
            className="px-6 py-2.5 bg-black text-white font-mono text-[11px] font-bold uppercase tracking-widest disabled:opacity-40 hover:bg-yellow-400 hover:text-black transition-colors border-2 border-black"
          >
            {scanning ? 'Escaneando...' : 'Escanear Feed'}
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
            {jobStatus?.progress !== undefined && (
              <p className="font-mono text-[10px] text-neutral-500">{jobStatus.progress}%</p>
            )}
          </div>

          {jobStatus?.progress !== undefined && (
            <div className="w-full bg-neutral-100 border border-black h-2">
              <div
                className="h-full bg-black transition-all duration-500"
                style={{ width: `${jobStatus.progress}%` }}
              />
            </div>
          )}

          {jobStatus?.status === 'escaneando_feed' && jobStatus.posts_captured !== undefined && (
            <p className="font-mono text-[10px] text-neutral-500">
              {jobStatus.posts_captured} posts capturados
            </p>
          )}

          {jobStatus?.status === 'done' && (
            <p className="font-mono text-[11px] text-black">
              {jobStatus.posts_scanned} posts analizados →{' '}
              <strong>{jobStatus.events_count ?? events.length} eventos detectados</strong>
            </p>
          )}

          {jobStatus?.status === 'error' && (
            <p className="font-mono text-[11px] text-red-600 border border-red-200 bg-red-50 px-3 py-2">
              {jobStatus.error}
            </p>
          )}
        </div>
      )}

      {/* Eventos encontrados */}
      {events.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="font-heading font-black text-xl">
              {events.length} eventos detectados
            </h3>
            <div className="flex items-center gap-3">
              <button
                onClick={toggleAll}
                className="font-mono text-[10px] uppercase tracking-widest border border-black px-3 py-1.5 hover:bg-black hover:text-white transition-colors"
              >
                {selected.size === events.length ? 'Deseleccionar todo' : 'Seleccionar todo'}
              </button>
              <button
                onClick={handleImport}
                disabled={selected.size === 0 || importing}
                className="px-5 py-2 bg-black text-white font-mono text-[11px] font-bold uppercase tracking-widest disabled:opacity-40 hover:bg-yellow-400 hover:text-black transition-colors border-2 border-black"
              >
                {importing ? 'Importando...' : `Importar ${selected.size} eventos`}
              </button>
            </div>
          </div>

          {importResult && (
            <div className={`border-2 p-3 font-mono text-[11px] ${importResult.errores > 0 ? 'border-red-400 bg-red-50' : 'border-green-400 bg-green-50'}`}>
              Importados: <strong>{importResult.nuevos}</strong> nuevos
              {importResult.errores > 0 && ` · ${importResult.errores} errores`}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {events.map((ev, i) => (
              <div
                key={i}
                onClick={() => {
                  const next = new Set(selected)
                  next.has(i) ? next.delete(i) : next.add(i)
                  setSelected(next)
                }}
                className={`border-2 p-3 cursor-pointer transition-colors ${
                  selected.has(i)
                    ? 'border-black bg-yellow-50'
                    : 'border-neutral-300 bg-white hover:border-black/50'
                }`}
              >
                <div className="flex items-start gap-2 mb-2">
                  <div className={`mt-0.5 w-4 h-4 border-2 flex-shrink-0 flex items-center justify-center ${
                    selected.has(i) ? 'border-black bg-black' : 'border-neutral-400'
                  }`}>
                    {selected.has(i) && (
                      <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="font-mono text-[11px] font-bold leading-tight line-clamp-2">{ev.titulo}</p>
                    {ev.ig_usuario && (
                      <p className="font-mono text-[9px] text-neutral-400 mt-0.5">{ev.ig_usuario}</p>
                    )}
                  </div>
                </div>

                {ev.imagen_url && (
                  <img
                    src={ev.imagen_url}
                    alt=""
                    className="w-full h-28 object-cover border border-black/10 mb-2"
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }}
                  />
                )}

                <div className="space-y-0.5 text-[10px] font-mono">
                  <p><span className="text-neutral-400">Fecha:</span> {ev.fecha_inicio?.slice(0, 10) || '—'}</p>
                  <p><span className="text-neutral-400">Lugar:</span> {ev.nombre_lugar || '—'}</p>
                  <p>
                    <span className="text-neutral-400">Cat:</span>{' '}
                    <span className="bg-black text-white px-1">{CAT_LABEL[ev.categoria_principal] ?? ev.categoria_principal}</span>
                    {ev.es_gratuito && <span className="ml-1 bg-green-200 text-green-800 px-1">Gratis</span>}
                  </p>
                  {ev.descripcion && (
                    <p className="text-neutral-500 line-clamp-2 mt-1">{ev.descripcion}</p>
                  )}
                </div>

                {ev.fuente_url && (
                  <a
                    href={ev.fuente_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={e => e.stopPropagation()}
                    className="block mt-2 font-mono text-[9px] text-blue-600 hover:underline truncate"
                  >
                    Ver post original →
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {jobStatus?.status === 'done' && events.length === 0 && (
        <div className="border-2 border-black p-6 text-center">
          <p className="font-mono text-sm text-neutral-500">
            No se detectaron eventos culturales en este feed.
          </p>
          <p className="font-mono text-[10px] text-neutral-400 mt-1">
            Prueba siguiendo más colectivos culturales de Medellín en Instagram.
          </p>
        </div>
      )}
    </div>
  )
}
