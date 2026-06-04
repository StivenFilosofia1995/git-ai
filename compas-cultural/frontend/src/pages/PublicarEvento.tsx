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
  { value: 'otro', label: 'Otro' },
]

const MUNICIPIOS = [
  'medellin', 'bello', 'envigado', 'itagui', 'sabaneta',
  'caldas', 'la_estrella', 'copacabana', 'girardota', 'barbosa',
]

export default function PublicarEvento() {
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
      const fd = new FormData(); fd.append('file', file)
      const res = await fetch(`${API_BASE}/admin/eventos/extraer-de-imagen`, {
        method: 'POST',
        headers: { 'X-API-Key': '854596+44' },
        body: fd,
      })
      if (!res.ok) throw new Error(`Error ${res.status}`)
      const json = await res.json() as { ok: boolean; data: Record<string, unknown> }
      const d = json.data
      setForm(prev => ({
        ...prev,
        titulo: (d.titulo as string) ?? prev.titulo,
        fecha_inicio: (d.fecha_inicio as string) ?? prev.fecha_inicio,
        hora_inicio: (d.hora_inicio as string) ?? prev.hora_inicio,
        descripcion: (d.descripcion as string) ?? prev.descripcion,
        categoria_principal: (d.categoria_principal as string) ?? prev.categoria_principal,
        municipio: (d.municipio as string) ?? prev.municipio,
        barrio: (d.barrio as string) ?? prev.barrio,
        nombre_lugar: (d.nombre_lugar as string) ?? prev.nombre_lugar,
        precio: (d.precio as string) ?? prev.precio,
        es_gratuito: typeof d.es_gratuito === 'boolean' ? d.es_gratuito : prev.es_gratuito,
        contacto_instagram: (d.link_externo as string)?.includes('instagram') ? (d.link_externo as string) : prev.contacto_instagram,
      }))
      setExtractMsg('✨ Datos extraídos del afiche — revisa y ajusta antes de enviar')
    } catch { setExtractMsg('No se pudo leer el afiche. Llena el formulario manualmente.') }
    finally { setExtracting(false) }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setEnviando(true)
    setResultado(null)

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
    } finally {
      setEnviando(false)
    }
  }

  const inputClass = 'w-full border-2 border-black px-3 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-black'
  const labelClass = 'block font-mono font-bold text-xs uppercase tracking-wider mb-1'

  return (
    <>
      <Helmet>
        <title>Publicar evento - Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-2xl mx-auto px-4 py-8">
        <Link to="/" className="text-sm font-mono font-bold uppercase tracking-wider mb-8 inline-block hover:underline">
          ← VOLVER
        </Link>

        <h1 className="text-3xl font-mono font-bold mb-2 uppercase">Publicar evento</h1>
        <p className="font-mono text-sm text-neutral-600 mb-6">
          ¿Sos colectivo, artista o espacio cultural? Publicá tu evento y aparecerá en la agenda de Cultura ETÉREA.
          No necesitás cuenta.
        </p>

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
            <p className="text-xs text-neutral-500 mt-1 font-mono">Segunda imagen (galería, captura, etc.)</p>
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
      </div>
    </>
  )
}
