import { useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { publicarEvento } from '../lib/api'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

const CATEGORIAS = [
  { value: 'teatro', label: 'Teatro' },
  { value: 'musica_en_vivo', label: 'Música en vivo' },
  { value: 'hip_hop', label: 'Hip Hop / Freestyle' },
  { value: 'jazz', label: 'Jazz' },
  { value: 'electronica', label: 'Electrónica / DJ' },
  { value: 'danza', label: 'Danza' },
  { value: 'cine', label: 'Cine' },
  { value: 'galeria', label: 'Galería / Arte visual' },
  { value: 'arte_contemporaneo', label: 'Arte contemporáneo' },
  { value: 'libreria', label: 'Literatura / Librería' },
  { value: 'poesia', label: 'Poesía' },
  { value: 'fotografia', label: 'Fotografía' },
  { value: 'festival', label: 'Festival' },
  { value: 'filosofia', label: 'Filosofía' },
  { value: 'taller', label: 'Taller' },
  { value: 'otro', label: 'Otro' },
]

const MUNICIPIOS = [
  'medellin', 'bello', 'envigado', 'itagui', 'sabaneta',
  'caldas', 'la_estrella', 'copacabana', 'girardota', 'barbosa',
]

type EventoExtraido = {
  titulo: string
  fecha_inicio: string
  fecha_fin?: string | null
  hora_inicio?: string | null
  hora_fin?: string | null
  nombre_lugar?: string | null
  municipio?: string
  barrio?: string | null
  categoria_principal?: string
  descripcion?: string | null
  precio?: string | null
  es_gratuito?: boolean
  contacto_instagram?: string | null
  contacto_email?: string | null
}

type BulkItem = {
  id: number
  file: File
  previewUrl: string
  status: 'pending' | 'extracting' | 'done' | 'error'
  data?: EventoExtraido
  error?: string
  selected: boolean
  submitStatus?: 'ok' | 'error' | 'sending'
}

let _id = 0

async function extractFromPoster(file: File): Promise<EventoExtraido> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(`${API_BASE}/eventos/extraer-afiche`, { method: 'POST', body: fd })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: string }).detail ?? `Error ${res.status}`)
  }
  const json = await res.json() as { ok: boolean; evento: EventoExtraido }
  return json.evento
}

// ─── Bulk upload mode ────────────────────────────────────────────────────────

function BulkUploader() {
  const [items, setItems] = useState<BulkItem[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [globalResult, setGlobalResult] = useState<string | null>(null)
  const dropRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const addFiles = (files: FileList | File[]) => {
    const arr = Array.from(files).filter(f => f.type.startsWith('image/'))
    const newItems: BulkItem[] = arr.map(f => ({
      id: ++_id,
      file: f,
      previewUrl: URL.createObjectURL(f),
      status: 'pending',
      selected: true,
    }))
    setItems(prev => [...prev, ...newItems])
    // kick off extraction for each
    newItems.forEach(item => processItem(item))
  }

  const processItem = async (item: BulkItem) => {
    setItems(prev => prev.map(x => x.id === item.id ? { ...x, status: 'extracting' } : x))
    try {
      const data = await extractFromPoster(item.file)
      setItems(prev => prev.map(x => x.id === item.id ? { ...x, status: 'done', data } : x))
    } catch (e) {
      setItems(prev => prev.map(x => x.id === item.id ? { ...x, status: 'error', error: String(e) } : x))
    }
  }

  const toggleItem = (id: number) =>
    setItems(prev => prev.map(x => x.id === id ? { ...x, selected: !x.selected } : x))

  const removeItem = (id: number) => {
    setItems(prev => {
      const item = prev.find(x => x.id === id)
      if (item) URL.revokeObjectURL(item.previewUrl)
      return prev.filter(x => x.id !== id)
    })
  }

  const updateField = (id: number, field: keyof EventoExtraido, value: unknown) =>
    setItems(prev => prev.map(x => x.id === id && x.data ? { ...x, data: { ...x.data, [field]: value } } : x))

  const handleSubmitAll = async () => {
    const toSubmit = items.filter(x => x.selected && x.status === 'done' && x.data)
    if (!toSubmit.length) return
    setSubmitting(true)
    setGlobalResult(null)

    let ok = 0; let fail = 0
    for (const item of toSubmit) {
      setItems(prev => prev.map(x => x.id === item.id ? { ...x, submitStatus: 'sending' } : x))
      const d = item.data!
      try {
        const fechaISO = d.fecha_inicio?.includes('T') ? d.fecha_inicio : `${d.fecha_inicio}T${d.hora_inicio ?? '19:00'}:00`
        await publicarEvento({
          titulo: d.titulo,
          fecha_inicio: fechaISO,
          descripcion: d.descripcion ?? undefined,
          categoria_principal: d.categoria_principal ?? 'otro',
          municipio: d.municipio ?? 'medellin',
          barrio: d.barrio ?? undefined,
          nombre_lugar: d.nombre_lugar ?? undefined,
          precio: d.precio ?? undefined,
          es_gratuito: d.es_gratuito ?? false,
          hora_inicio: d.hora_inicio ?? undefined,
          hora_fin: d.hora_fin ?? undefined,
          contacto_instagram: d.contacto_instagram ?? undefined,
          contacto_email: d.contacto_email ?? undefined,
        })
        setItems(prev => prev.map(x => x.id === item.id ? { ...x, submitStatus: 'ok' } : x))
        ok++
      } catch {
        setItems(prev => prev.map(x => x.id === item.id ? { ...x, submitStatus: 'error' } : x))
        fail++
      }
    }
    setGlobalResult(`${ok} evento${ok !== 1 ? 's' : ''} enviado${ok !== 1 ? 's' : ''} para revisión${fail ? ` · ${fail} con error` : ''}`)
    setSubmitting(false)
  }

  const selectedDone = items.filter(x => x.selected && x.status === 'done').length
  const allSelected = items.length > 0 && items.every(x => x.selected)

  return (
    <div className="space-y-6">
      <div
        ref={dropRef}
        className="border-2 border-black border-dashed p-8 text-center cursor-pointer hover:bg-yellow-50 transition-colors"
        onClick={() => inputRef.current?.click()}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files) }}
      >
        <p className="font-mono text-sm font-bold">Arrastrá uno o varios afiches aquí</p>
        <p className="font-mono text-xs text-neutral-500 mt-1">o hacé clic para seleccionar archivos</p>
        <input ref={inputRef} type="file" accept="image/*" multiple className="hidden"
          onChange={e => { if (e.target.files?.length) { addFiles(e.target.files); e.target.value = '' } }} />
      </div>

      {items.length > 0 && (
        <>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setItems(prev => prev.map(x => ({ ...x, selected: !allSelected })))}
                className="font-mono text-[10px] uppercase tracking-widest border border-black px-3 py-1.5 hover:bg-black hover:text-white transition-colors"
              >
                {allSelected ? 'Quitar todo' : 'Seleccionar todo'}
              </button>
              <span className="font-mono text-xs text-neutral-500">{selectedDone} listos para publicar</span>
            </div>
            <button
              onClick={handleSubmitAll}
              disabled={submitting || selectedDone === 0}
              className="px-5 py-2 bg-black text-white font-mono text-[11px] font-bold uppercase tracking-widest disabled:opacity-40 hover:bg-yellow-400 hover:text-black transition-colors border-2 border-black"
            >
              {submitting ? 'Enviando...' : `📤 Publicar ${selectedDone} evento${selectedDone !== 1 ? 's' : ''}`}
            </button>
          </div>

          {globalResult && (
            <div className="border-2 border-green-400 bg-green-50 px-4 py-2 font-mono text-sm font-bold text-green-800">
              ✅ {globalResult}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {items.map(item => (
              <BulkCard
                key={item.id}
                item={item}
                onToggle={() => toggleItem(item.id)}
                onRemove={() => removeItem(item.id)}
                onFieldChange={(field, val) => updateField(item.id, field, val)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function BulkCard({
  item,
  onToggle,
  onRemove,
  onFieldChange,
}: {
  item: BulkItem
  onToggle: () => void
  onRemove: () => void
  onFieldChange: (field: keyof EventoExtraido, value: unknown) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const d = item.data

  const statusBorder = item.submitStatus === 'ok'
    ? 'border-green-400'
    : item.submitStatus === 'error'
    ? 'border-red-400'
    : item.selected && item.status === 'done'
    ? 'border-black'
    : 'border-neutral-300'

  return (
    <div className={`border-2 ${statusBorder} bg-white transition-colors`}>
      <div className="relative">
        <img src={item.previewUrl} alt="" className="w-full h-40 object-cover" />
        <div className="absolute top-2 left-2">
          {item.status !== 'error' && (
            <button
              onClick={onToggle}
              className={`w-5 h-5 border-2 flex items-center justify-center ${item.selected ? 'border-black bg-black' : 'border-white bg-white/80'}`}
            >
              {item.selected && (
                <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              )}
            </button>
          )}
        </div>
        <button
          onClick={onRemove}
          className="absolute top-2 right-2 w-5 h-5 bg-black/70 text-white font-mono text-[10px] flex items-center justify-center hover:bg-red-600 transition-colors"
        >×</button>
        {item.submitStatus === 'ok' && (
          <div className="absolute inset-0 bg-green-900/60 flex items-center justify-center">
            <span className="text-white font-mono text-xs font-bold">✓ Enviado</span>
          </div>
        )}
      </div>

      <div className="p-3 space-y-1.5">
        {item.status === 'extracting' && (
          <p className="font-mono text-[11px] text-neutral-500 animate-pulse">⏳ Analizando afiche...</p>
        )}
        {item.status === 'error' && (
          <p className="font-mono text-[11px] text-red-600">{item.error ?? 'Error'}</p>
        )}
        {item.status === 'done' && d && (
          <>
            <p className="font-mono text-[11px] font-bold leading-tight line-clamp-2">{d.titulo}</p>
            <div className="text-[10px] font-mono text-neutral-500 space-y-0.5">
              <p>{d.fecha_inicio?.slice(0, 10) || '—'} {d.hora_inicio ? `· ${d.hora_inicio}` : ''}</p>
              <p>{d.nombre_lugar || d.municipio || '—'}</p>
              <p>
                <span className="bg-black text-white px-1">{d.categoria_principal ?? 'otro'}</span>
                {d.es_gratuito && <span className="ml-1 bg-green-200 text-green-800 px-1">Gratis</span>}
              </p>
            </div>

            <button
              onClick={() => setExpanded(e => !e)}
              className="font-mono text-[9px] uppercase tracking-widest text-neutral-400 hover:text-black mt-1"
            >
              {expanded ? '▲ menos' : '▼ editar'}
            </button>

            {expanded && (
              <div className="pt-2 space-y-1.5 border-t border-neutral-200">
                {([
                  ['titulo', 'Título', 'text'],
                  ['fecha_inicio', 'Fecha (YYYY-MM-DD)', 'text'],
                  ['hora_inicio', 'Hora inicio', 'text'],
                  ['nombre_lugar', 'Lugar', 'text'],
                  ['municipio', 'Municipio', 'text'],
                  ['barrio', 'Barrio', 'text'],
                  ['precio', 'Precio', 'text'],
                  ['descripcion', 'Descripción', 'textarea'],
                ] as [keyof EventoExtraido, string, string][]).map(([field, lbl, type]) => (
                  <div key={field}>
                    <label className="block font-mono text-[8px] uppercase tracking-wider text-neutral-400">{lbl}</label>
                    {type === 'textarea' ? (
                      <textarea
                        rows={2}
                        value={(d[field] as string) ?? ''}
                        onChange={e => onFieldChange(field, e.target.value)}
                        className="w-full border border-neutral-300 px-2 py-1 font-mono text-[10px] focus:outline-none focus:border-black"
                      />
                    ) : (
                      <input
                        type="text"
                        value={(d[field] as string) ?? ''}
                        onChange={e => onFieldChange(field, e.target.value)}
                        className="w-full border border-neutral-300 px-2 py-1 font-mono text-[10px] focus:outline-none focus:border-black"
                      />
                    )}
                  </div>
                ))}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={d.es_gratuito ?? false}
                    onChange={e => onFieldChange('es_gratuito', e.target.checked)}
                    className="w-3.5 h-3.5 border border-black"
                  />
                  <label className="font-mono text-[10px]">Gratuito</label>
                </div>
                <div>
                  <label className="block font-mono text-[8px] uppercase tracking-wider text-neutral-400">Categoría</label>
                  <select
                    value={d.categoria_principal ?? 'otro'}
                    onChange={e => onFieldChange('categoria_principal', e.target.value)}
                    className="w-full border border-neutral-300 px-2 py-1 font-mono text-[10px] focus:outline-none focus:border-black bg-white"
                  >
                    {CATEGORIAS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                  </select>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ─── Single event form mode ──────────────────────────────────────────────────

function SingleForm() {
  const [form, setForm] = useState({
    titulo: '',
    fecha_inicio: '',
    hora_inicio: '19:00',
    hora_fin: '',
    descripcion: '',
    categoria_principal: 'otro',
    municipio: 'medellin',
    barrio: '',
    nombre_lugar: '',
    precio: '',
    es_gratuito: false,
    imagen_url: '',
    imagen_url_alternativa: '',
    aforo: '',
    sesion_numero: '',
    contacto_instagram: '',
    contacto_email: '',
  })
  const [enviando, setEnviando] = useState(false)
  const [resultado, setResultado] = useState<{ ok: boolean; mensaje: string } | null>(null)
  const [extracting, setExtracting] = useState(false)
  const [extractMsg, setExtractMsg] = useState<string | null>(null)
  const imgInputRef = useRef<HTMLInputElement>(null)

  const handleExtractFromPoster = async (file: File) => {
    setExtracting(true); setExtractMsg(null)
    try {
      const d = await extractFromPoster(file)
      setForm(prev => ({
        ...prev,
        titulo: d.titulo ?? prev.titulo,
        fecha_inicio: d.fecha_inicio?.slice(0, 10) ?? prev.fecha_inicio,
        hora_inicio: d.hora_inicio ?? prev.hora_inicio,
        hora_fin: d.hora_fin ?? prev.hora_fin,
        descripcion: d.descripcion ?? prev.descripcion,
        categoria_principal: d.categoria_principal ?? prev.categoria_principal,
        municipio: d.municipio ?? prev.municipio,
        barrio: d.barrio ?? prev.barrio,
        nombre_lugar: d.nombre_lugar ?? prev.nombre_lugar,
        precio: d.precio ?? prev.precio,
        es_gratuito: d.es_gratuito ?? prev.es_gratuito,
        contacto_instagram: d.contacto_instagram ?? prev.contacto_instagram,
        contacto_email: d.contacto_email ?? prev.contacto_email,
      }))
      setExtractMsg('✨ Datos extraídos del afiche — revisá y ajustá antes de enviar')
    } catch (e) {
      setExtractMsg(`No se pudo leer el afiche: ${e instanceof Error ? e.message : 'intenta manualmente.'}`)
    }
    finally { setExtracting(false) }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setEnviando(true); setResultado(null)
    try {
      const fechaISO = `${form.fecha_inicio}T${form.hora_inicio}:00`
      const res = await publicarEvento({
        titulo: form.titulo,
        fecha_inicio: fechaISO,
        descripcion: form.descripcion || undefined,
        categoria_principal: form.categoria_principal,
        municipio: form.municipio,
        barrio: form.barrio || undefined,
        nombre_lugar: form.nombre_lugar || undefined,
        precio: form.precio || undefined,
        es_gratuito: form.es_gratuito,
        hora_inicio: form.hora_inicio,
        hora_fin: form.hora_fin || undefined,
        imagen_url: form.imagen_url || undefined,
        imagen_url_alternativa: form.imagen_url_alternativa || undefined,
        aforo: form.aforo ? parseInt(form.aforo) : undefined,
        sesion_numero: form.sesion_numero ? parseInt(form.sesion_numero) : undefined,
        contacto_instagram: form.contacto_instagram || undefined,
        contacto_email: form.contacto_email || undefined,
      })
      setResultado(res)
      if (res.ok) {
        setForm({
          titulo: '', fecha_inicio: '', hora_inicio: '19:00', hora_fin: '', descripcion: '',
          categoria_principal: 'otro', municipio: 'medellin', barrio: '',
          nombre_lugar: '', precio: '', es_gratuito: false, imagen_url: '',
          imagen_url_alternativa: '', aforo: '', sesion_numero: '',
          contacto_instagram: '', contacto_email: '',
        })
      }
    } catch (err) {
      setResultado({ ok: false, mensaje: err instanceof Error ? err.message : 'Error desconocido' })
    } finally { setEnviando(false) }
  }

  const inputClass = 'w-full border-2 border-black px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-black'
  const labelClass = 'block font-mono font-bold text-xs uppercase tracking-wider mb-1'

  return (
    <>
      {/* AI poster extractor */}
      <div className="border-2 border-black border-dashed p-5 mb-8 bg-yellow-50">
        <p className="font-mono font-bold text-xs uppercase tracking-wider mb-3">✨ ¿Tenés el afiche? Súbelo y lo llenamos automáticamente</p>
        <div
          className="border-2 border-black p-4 text-center cursor-pointer hover:bg-yellow-100 transition-colors"
          onClick={() => imgInputRef.current?.click()}
          onDragOver={e => e.preventDefault()}
          onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f?.type.startsWith('image/')) void handleExtractFromPoster(f) }}
        >
          <p className="font-mono text-xs text-neutral-500">
            {extracting ? '⏳ Analizando afiche con IA...' : 'Arrastrá la imagen del evento aquí o hacé clic para seleccionar'}
          </p>
          <input ref={imgInputRef} type="file" accept="image/*" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) void handleExtractFromPoster(f) }} />
        </div>
        {extractMsg && (
          <p className={`font-mono text-xs mt-2 ${extractMsg.startsWith('✨') ? 'text-green-700 font-bold' : 'text-neutral-500'}`}>{extractMsg}</p>
        )}
      </div>

      {resultado && (
        <div className={`border-2 px-4 py-3 mb-6 font-mono text-sm ${resultado.ok ? 'border-green-600 bg-green-50 text-green-800' : 'border-red-600 bg-red-50 text-red-800'}`}>
          {resultado.mensaje}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className={labelClass}>Nombre del evento *</label>
          <input type="text" required maxLength={200} value={form.titulo}
            onChange={e => setForm({ ...form, titulo: e.target.value })}
            placeholder="Ej: Noche de Jazz en Otraparte" className={inputClass} />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className={labelClass}>Fecha *</label>
            <input type="date" required value={form.fecha_inicio}
              onChange={e => setForm({ ...form, fecha_inicio: e.target.value })}
              className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Hora inicio *</label>
            <input type="time" required value={form.hora_inicio}
              onChange={e => setForm({ ...form, hora_inicio: e.target.value })}
              className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Hora fin (opcional)</label>
            <input type="time" value={form.hora_fin}
              onChange={e => setForm({ ...form, hora_fin: e.target.value })}
              className={inputClass} />
          </div>
        </div>

        <div>
          <label className={labelClass}>Descripción</label>
          <textarea rows={3} maxLength={1000} value={form.descripcion}
            onChange={e => setForm({ ...form, descripcion: e.target.value })}
            placeholder="Cuéntanos de qué se trata..." className={inputClass} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Categoría *</label>
            <select value={form.categoria_principal}
              onChange={e => setForm({ ...form, categoria_principal: e.target.value })}
              className={inputClass}>
              {CATEGORIAS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <label className={labelClass}>Municipio *</label>
            <select value={form.municipio}
              onChange={e => setForm({ ...form, municipio: e.target.value })}
              className={inputClass}>
              {MUNICIPIOS.map(m => (
                <option key={m} value={m}>{m.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Barrio</label>
            <input type="text" value={form.barrio}
              onChange={e => setForm({ ...form, barrio: e.target.value })}
              placeholder="Ej: El Poblado" className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Lugar / Espacio</label>
            <input type="text" value={form.nombre_lugar}
              onChange={e => setForm({ ...form, nombre_lugar: e.target.value })}
              placeholder="Ej: Casa Tres Patios" className={inputClass} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Precio</label>
            <input type="text" value={form.precio}
              onChange={e => setForm({ ...form, precio: e.target.value })}
              placeholder="Ej: $20.000 o Entrada libre" className={inputClass} />
          </div>
          <div className="flex items-end pb-2">
            <label className="flex items-center gap-2 font-mono text-sm cursor-pointer">
              <input type="checkbox" checked={form.es_gratuito}
                onChange={e => setForm({ ...form, es_gratuito: e.target.checked })}
                className="w-5 h-5 border-2 border-black" />
              Es gratuito
            </label>
          </div>
        </div>

        <div>
          <label className={labelClass}>URL de imagen principal (opcional)</label>
          <input type="url" value={form.imagen_url}
            onChange={e => setForm({ ...form, imagen_url: e.target.value })}
            placeholder="https://..." className={inputClass} />
          <p className="text-xs text-neutral-500 mt-1 font-mono">Pega la URL de una imagen (flyer, poster, foto del evento, etc.)</p>
        </div>

        <div>
          <label className={labelClass}>URL de imagen alternativa (opcional)</label>
          <input type="url" value={form.imagen_url_alternativa}
            onChange={e => setForm({ ...form, imagen_url_alternativa: e.target.value })}
            placeholder="https://..." className={inputClass} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Aforo / Capacidad (opcional)</label>
            <input type="number" min="1" value={form.aforo}
              onChange={e => setForm({ ...form, aforo: e.target.value })}
              placeholder="Ej: 200" className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Número de sesión (opcional)</label>
            <input type="number" min="1" value={form.sesion_numero}
              onChange={e => setForm({ ...form, sesion_numero: e.target.value })}
              placeholder="Ej: 1, 2, 3..." className={inputClass} />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Instagram de contacto</label>
            <input type="text" value={form.contacto_instagram}
              onChange={e => setForm({ ...form, contacto_instagram: e.target.value })}
              placeholder="@tucolectivo" className={inputClass} />
          </div>
          <div>
            <label className={labelClass}>Email de contacto</label>
            <input type="email" value={form.contacto_email}
              onChange={e => setForm({ ...form, contacto_email: e.target.value })}
              placeholder="correo@ejemplo.com" className={inputClass} />
          </div>
        </div>

        <button type="submit" disabled={enviando}
          className="w-full py-3 bg-black text-white font-mono font-bold uppercase tracking-wider text-sm hover:bg-neutral-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
          {enviando ? 'Publicando...' : '📤 Publicar evento'}
        </button>
      </form>
    </>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function PublicarEvento() {
  const [mode, setMode] = useState<'single' | 'bulk'>('single')

  return (
    <>
      <Helmet>
        <title>Publicar evento - Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <Link to="/" className="text-sm font-mono font-bold uppercase tracking-wider mb-8 inline-block hover:underline">
          ← VOLVER
        </Link>

        <h1 className="text-3xl font-mono font-bold mb-2 uppercase">Publicar evento</h1>
        <p className="font-mono text-sm text-neutral-600 mb-6">
          ¿Sos colectivo, artista o espacio cultural? Publicá tu evento y aparecerá en la agenda de Cultura ETÉREA.
          No necesitás cuenta.
        </p>

        {/* Mode switcher */}
        <div className="flex border-2 border-black mb-8 w-fit">
          <button
            onClick={() => setMode('single')}
            className={`px-5 py-2 font-mono text-[11px] font-bold uppercase tracking-widest transition-colors ${mode === 'single' ? 'bg-black text-white' : 'bg-white text-black hover:bg-neutral-100'}`}
          >
            Un evento
          </button>
          <button
            onClick={() => setMode('bulk')}
            className={`px-5 py-2 font-mono text-[11px] font-bold uppercase tracking-widest transition-colors border-l-2 border-black ${mode === 'bulk' ? 'bg-black text-white' : 'bg-white text-black hover:bg-neutral-100'}`}
          >
            Varios afiches ✨
          </button>
        </div>

        {mode === 'single' ? <SingleForm /> : <BulkUploader />}
      </div>
    </>
  )
}
