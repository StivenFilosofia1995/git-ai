import { useState, useEffect, useCallback, useRef, lazy, Suspense } from 'react'
import { Helmet } from 'react-helmet-async'
import {
  getAdminDashboard, adminTriggerScraper, adminTriggerBlastTick, adminTriggerCleanup,
  adminUploadEventImage, adminCrearEvento, adminActualizarEvento, adminDeleteEvento,
  adminGetEventosManuales, adminGetModeloIA, adminReentrenarModelo,
  adminExtraerDeImagen, adminCrearMasivo, adminMasivoStatus,
  type AdminDashboard, type EventoAdminCreate, type ModeloIAStatus,
} from '../lib/api'

const CulturalMap = lazy(() => import('../components/map/CulturalMap'))
const KEY_STORAGE = 'admin:apikey'
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

type Tab = 'resumen' | 'eventos' | 'espacios' | 'usuarios' | 'logs' | 'mapa' | 'subir_evento' | 'modelo_ia' | 'buscar_web'

const CAT_LABEL: Record<string, string> = {
  teatro: 'Teatro', hip_hop: 'Hip Hop', jazz: 'Jazz', galeria: 'Galería',
  arte_contemporaneo: 'Arte', electronica: 'Electrónica', danza: 'Danza',
  musica_en_vivo: 'Música', poesia: 'Poesía', festival: 'Festival',
  cine: 'Cine', fotografia: 'Foto', filosofia: 'Filosofía', taller: 'Taller',
  circo: 'Circo', rock: 'Rock', punk: 'Punk', libreria: 'Librería',
  casa_cultura: 'Casa Cult.', centro_cultural: 'C. Cultural', otro: 'Otro',
  musica: 'Música', editorial: 'Editorial', radio_comunitaria: 'Radio',
}

// ── Shared helpers ─────────────────────────────────────────────────────────────

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="border-2 border-black p-4">
      <p className="text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-neutral-500 mb-1">{label}</p>
      <p className="text-3xl font-heading font-black leading-none">{value}</p>
      {sub && <p className="text-[10px] font-mono text-neutral-400 mt-1">{sub}</p>}
    </div>
  )
}

function MiniBar({ data, color = 'bg-black' }: { data: { fecha: string; nuevos: number }[]; color?: string }) {
  const max = Math.max(...data.map(x => x.nuevos), 1)
  return (
    <div className="flex items-end gap-1.5 h-20">
      {data.map(({ fecha, nuevos }) => (
        <div key={fecha} className="flex-1 flex flex-col items-center gap-1">
          <span className="text-[8px] font-mono font-black">{nuevos || ''}</span>
          <div className={`w-full ${color}`} style={{ height: `${Math.max((nuevos / max) * 56, nuevos > 0 ? 3 : 0)}px` }} />
          <span className="text-[7px] font-mono text-neutral-400">{fecha}</span>
        </div>
      ))}
    </div>
  )
}

function ActionBtn({ label, onClick, loading, variant = 'default' }: {
  label: string; onClick: () => void; loading?: boolean; variant?: 'default' | 'yellow' | 'red'
}) {
  const bg = variant === 'yellow' ? 'bg-yellow-300 hover:bg-yellow-400 border-black'
    : variant === 'red' ? 'bg-red-600 text-white hover:bg-red-700 border-red-600'
    : 'bg-white hover:bg-black hover:text-white border-black'
  return (
    <button onClick={onClick} disabled={loading}
      className={`px-4 py-2.5 border-2 font-mono text-[11px] font-bold uppercase tracking-widest transition-colors disabled:opacity-50 ${bg}`}>
      {loading ? '...' : label}
    </button>
  )
}

// ── DATA TABLE (generic) ───────────────────────────────────────────────────────

function DataTable<T extends Record<string, unknown>>({
  columns, data, total, page, perPage, onPage, loading, onDelete, deleteLabel,
}: {
  columns: { key: string; label: string; render?: (row: T) => React.ReactNode }[]
  data: T[]; total: number; page: number; perPage: number
  onPage: (p: number) => void; loading: boolean
  onDelete?: (row: T) => void; deleteLabel?: string
}) {
  const pages = Math.ceil(total / perPage)
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="font-mono text-[10px] text-neutral-500">{total.toLocaleString()} registros · pág {page}/{pages || 1}</p>
        <div className="flex gap-1">
          <button onClick={() => onPage(Math.max(1, page - 1))} disabled={page <= 1 || loading}
            className="px-2 py-1 border border-black font-mono text-[10px] disabled:opacity-30 hover:bg-black hover:text-white transition-colors">←</button>
          <button onClick={() => onPage(Math.min(pages, page + 1))} disabled={page >= pages || loading}
            className="px-2 py-1 border border-black font-mono text-[10px] disabled:opacity-30 hover:bg-black hover:text-white transition-colors">→</button>
        </div>
      </div>
      <div className="overflow-x-auto border-2 border-black">
        <table className="w-full text-[11px] font-mono">
          <thead>
            <tr className="bg-black text-white">
              {columns.map(c => (
                <th key={c.key} className="text-left px-3 py-2 font-bold uppercase tracking-wider whitespace-nowrap">{c.label}</th>
              ))}
              {onDelete && <th className="px-3 py-2 w-16" />}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={columns.length + (onDelete ? 1 : 0)} className="px-3 py-8 text-center text-neutral-400 animate-pulse">Cargando...</td></tr>
            )}
            {!loading && data.length === 0 && (
              <tr><td colSpan={columns.length + (onDelete ? 1 : 0)} className="px-3 py-8 text-center text-neutral-400">Sin resultados</td></tr>
            )}
            {!loading && data.map((row, i) => (
              <tr key={i} className="border-b border-black/10 hover:bg-yellow-50 transition-colors">
                {columns.map(c => (
                  <td key={c.key} className="px-3 py-2 max-w-[200px] truncate">
                    {c.render ? c.render(row) : String(row[c.key] ?? '—')}
                  </td>
                ))}
                {onDelete && (
                  <td className="px-3 py-2">
                    <button onClick={() => onDelete(row)}
                      className="text-red-600 hover:text-red-800 font-bold text-[10px] uppercase tracking-wider transition-colors">
                      {deleteLabel ?? 'Borrar'}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── TAB: RESUMEN ──────────────────────────────────────────────────────────────

function TabResumen({ d, apiKey }: { d: AdminDashboard; apiKey: string }) {
  const [actionMsg, setActionMsg] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  async function runAction(id: string, fn: () => Promise<unknown>) {
    setActionLoading(id)
    setActionMsg('')
    try {
      const res = await fn() as { ok: boolean; message?: string; stats?: Record<string, unknown> }
      setActionMsg(`✓ ${res.message || JSON.stringify(res.stats || res)}`)
    } catch (e: unknown) {
      setActionMsg(`✗ Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <div className="space-y-6">
      {/* Acciones */}
      <div className="border-2 border-black p-5">
        <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-3">Acciones rápidas</p>
        <div className="flex flex-wrap gap-3">
          <ActionBtn label="▶ Correr Scraper" variant="yellow" loading={actionLoading === 'scraper'}
            onClick={() => runAction('scraper', () => adminTriggerScraper(apiKey))} />
          <ActionBtn label="📧 Blast Tick" loading={actionLoading === 'blast'}
            onClick={() => runAction('blast', () => adminTriggerBlastTick(apiKey))} />
          <ActionBtn label="🧹 Limpiar Pasados" loading={actionLoading === 'cleanup'}
            onClick={() => runAction('cleanup', () => adminTriggerCleanup(apiKey))} />
        </div>
        {actionMsg && (
          <p className={`mt-3 font-mono text-xs ${actionMsg.startsWith('✓') ? 'text-green-700' : 'text-red-600'}`}>{actionMsg}</p>
        )}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Stat label="Eventos totales" value={d.eventos.total.toLocaleString()} />
        <Stat label="Eventos hoy" value={d.eventos.hoy} />
        <Stat label="Proxima semana" value={d.eventos.proxima_semana} />
        <Stat label="Nuevos 7d" value={d.eventos.nuevos_7d} />
        <Stat label="Espacios activos" value={d.espacios.activos} sub={`${d.espacios.total} total`} />
        <Stat label="Colectivos" value={d.espacios.colectivos} />
        <Stat label="Con Instagram" value={d.espacios.con_instagram} />
        <Stat label="Usuarios" value={d.usuarios.auth_registrados} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Eventos por día */}
        <div className="border-2 border-black p-5">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-3">Eventos nuevos / día (7d)</p>
          <MiniBar data={d.eventos.por_dia} color="bg-black" />
        </div>
        {/* Top categorías */}
        <div className="border-2 border-black p-5">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-3">Top categorías (próx. semana)</p>
          <div className="space-y-1.5">
            {d.eventos.top_categorias.map(({ cat, n }) => (
              <div key={cat} className="flex items-center gap-2">
                <span className="text-[10px] font-mono w-24 shrink-0">{CAT_LABEL[cat] ?? cat}</span>
                <div className="flex-1 bg-neutral-100 h-3">
                  <div className="h-3 bg-black" style={{ width: `${Math.round((n / (d.eventos.proxima_semana || 1)) * 100)}%` }} />
                </div>
                <span className="text-[10px] font-mono font-black w-5 text-right">{n}</span>
              </div>
            ))}
          </div>
        </div>
        {/* Email */}
        <div className="border-2 border-black p-5">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-3">Email blast</p>
          <div className="space-y-2 text-xs font-mono">
            <div className="flex justify-between"><span className="text-neutral-500">Campaña</span><span className="font-black">{d.email.blast_key}</span></div>
            <div className="flex justify-between"><span className="text-neutral-500">Cursor</span><span className="font-black">{d.email.blast_cursor} / {d.email.destinatarios_estimados}</span></div>
          </div>
          {d.email.destinatarios_estimados > 0 && (
            <div className="mt-3">
              <div className="w-full bg-neutral-100 h-2">
                <div className="h-2 bg-black" style={{ width: `${Math.min((d.email.blast_cursor / d.email.destinatarios_estimados) * 100, 100)}%` }} />
              </div>
              <p className="text-[9px] font-mono text-neutral-400 mt-1">{Math.round((d.email.blast_cursor / d.email.destinatarios_estimados) * 100)}% completado</p>
            </div>
          )}
        </div>
        {/* Scrapers */}
        <div className="border-2 border-black p-5">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-3">Scrapers (7d)</p>
          <div className="space-y-1.5 text-xs font-mono mb-3">
            <div className="flex justify-between"><span className="text-neutral-500">Runs</span><span className="font-black">{d.scrapers.runs_7d}</span></div>
            <div className="flex justify-between"><span className="text-neutral-500">Eventos nuevos</span><span className="font-black">{d.scrapers.nuevos_eventos_7d}</span></div>
            <div className="flex justify-between"><span className="text-neutral-500">Fuentes activas</span><span className="font-black">{d.scrapers.fuentes_activas}</span></div>
          </div>
          <div className="space-y-1 max-h-24 overflow-y-auto">
            {d.scrapers.ultimas_fuentes.map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-[9px] font-mono">
                <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${(f.errores || 0) > 0 ? 'bg-red-500' : 'bg-green-500'}`} />
                <span className="truncate flex-1 text-neutral-600">{f.fuente}</span>
                <span className="font-black shrink-0">+{f.registros_nuevos ?? 0}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Interacciones */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="border-2 border-black p-5">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-1">Interacciones (7d)</p>
          <p className="text-2xl font-heading font-black mb-3">{(d.interacciones?.total_7d ?? 0).toLocaleString()}</p>
          <div className="space-y-1.5">
            {Object.entries(d.interacciones?.por_tipo ?? {}).sort((a, b) => b[1] - a[1]).map(([tipo, n]) => (
              <div key={tipo} className="flex items-center gap-2">
                <span className="text-[10px] font-mono w-24 shrink-0 capitalize">{tipo.replace(/_/g, ' ')}</span>
                <div className="flex-1 bg-neutral-100 h-3">
                  <div className="h-3 bg-yellow-300 border-r border-black/20" style={{ width: `${Math.round((n / (d.interacciones?.total_7d || 1)) * 100)}%` }} />
                </div>
                <span className="text-[10px] font-mono font-black w-7 text-right">{n}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="border-2 border-black p-5">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-3">Top espacios visitados (7d)</p>
          <div className="space-y-2">
            {(d.interacciones?.top_espacios ?? []).map((e, i) => (
              <div key={e.slug} className="flex items-center gap-3 border-b border-black/5 pb-1.5">
                <span className="text-[10px] font-mono font-black text-neutral-300 w-4">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <p className="font-mono text-xs font-bold truncate">{e.nombre}</p>
                  <p className="font-mono text-[9px] text-neutral-400">{e.barrio} · {CAT_LABEL[e.categoria] ?? e.categoria}</p>
                </div>
                <span className="font-mono text-xs font-black shrink-0">{e.clicks}</span>
              </div>
            ))}
            {(d.interacciones?.top_espacios ?? []).length === 0 && <p className="font-mono text-xs text-neutral-400">Sin datos</p>}
          </div>
        </div>
      </div>

      {/* Usuarios por día */}
      <div className="border-2 border-black p-5">
        <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-3">
          Nuevos usuarios / día (7d) <span className="font-normal text-neutral-400 normal-case ml-2">{d.usuarios.auth_registrados} total</span>
        </p>
        <MiniBar data={d.usuarios.registros_por_dia ?? []} color="bg-yellow-300" />
      </div>

      {/* Calidad */}
      <div className="border-2 border-black p-5">
        <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-4">Calidad de datos</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            { label: 'Con imagen', value: d.eventos.con_imagen, total: d.eventos.total },
            { label: 'Verificados', value: d.eventos.verificados, total: d.eventos.total },
            { label: 'Con Instagram', value: d.espacios.con_instagram, total: d.espacios.total },
            { label: 'Activos', value: d.espacios.activos, total: d.espacios.total },
          ].map(({ label, value, total }) => {
            const pct = total > 0 ? Math.round((value / total) * 100) : 0
            return (
              <div key={label}>
                <p className="text-[9px] font-mono text-neutral-500 mb-1">{label}</p>
                <p className="text-xl font-heading font-black">{pct}%</p>
                <p className="text-[9px] font-mono text-neutral-400">{value.toLocaleString()} / {total.toLocaleString()}</p>
                <div className="mt-1.5 w-full bg-neutral-100 h-1.5">
                  <div className="h-1.5 bg-black" style={{ width: `${pct}%` }} />
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

// ── EDIT EVENTO PANEL ─────────────────────────────────────────────────────────

function EditEventoPanel({ row, apiKey, onClose, onSaved }: {
  row: Record<string, unknown>; apiKey: string; onClose: () => void; onSaved: () => void
}) {
  const [form, setForm] = useState({
    titulo: String(row.titulo ?? ''),
    fecha_inicio: String(row.fecha_inicio ?? '').slice(0, 10),
    fecha_fin: String(row.fecha_fin ?? '').slice(0, 10),
    hora_inicio: row.hora_confirmada ? String(row.fecha_inicio ?? '').slice(11, 16) : '',
    categoria_principal: String(row.categoria_principal ?? 'otro'),
    municipio: String(row.municipio ?? 'medellin'),
    barrio: String(row.barrio ?? ''),
    nombre_lugar: String(row.nombre_lugar ?? ''),
    descripcion: String(row.descripcion ?? ''),
    precio: String(row.precio ?? ''),
    es_gratuito: Boolean(row.es_gratuito),
    imagen_url: String(row.imagen_url ?? ''),
    fuente_url: String(row.fuente_url ?? ''),
    oculto: Boolean(row.oculto),
  })
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const inp = 'w-full border-2 border-black px-2 py-1.5 font-mono text-xs outline-none focus:border-yellow-400'
  const lbl = 'font-mono text-[10px] font-bold uppercase tracking-wider mb-1 block'

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setMsg(null)
    try {
      let fechaInicio = form.fecha_inicio
      if (form.hora_inicio && form.fecha_inicio) fechaInicio = `${form.fecha_inicio}T${form.hora_inicio}:00`
      const body: Record<string, unknown> = {
        titulo: form.titulo, fecha_inicio: fechaInicio,
        categoria_principal: form.categoria_principal, municipio: form.municipio,
        es_gratuito: form.es_gratuito, oculto: form.oculto,
        hora_confirmada: Boolean(form.hora_inicio),
      }
      if (form.fecha_fin) body.fecha_fin = form.fecha_fin
      if (form.barrio) body.barrio = form.barrio
      if (form.nombre_lugar) body.nombre_lugar = form.nombre_lugar
      if (form.descripcion) body.descripcion = form.descripcion
      if (form.precio) body.precio = form.precio
      if (form.imagen_url) body.imagen_url = form.imagen_url
      if (form.fuente_url) body.fuente_url = form.fuente_url
      const res = await fetch(`${API_BASE}/admin/eventos/${row.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
        body: JSON.stringify(body),
      })
      const json = await res.json() as { detail?: string }
      if (!res.ok) throw new Error(json.detail ?? String(res.status))
      setMsg({ text: '✓ Guardado correctamente', ok: true }); onSaved()
    } catch (e: unknown) {
      setMsg({ text: `Error: ${e instanceof Error ? e.message : String(e)}`, ok: false })
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-[100] flex">
      <div className="flex-1 bg-black/40" onClick={onClose} />
      <div className="w-full max-w-lg bg-white border-l-2 border-black overflow-y-auto flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b-2 border-black bg-black text-white sticky top-0">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-widest opacity-60">Editar evento</p>
            <p className="font-mono text-sm font-bold truncate max-w-[280px]">{form.titulo}</p>
          </div>
          <button onClick={onClose} className="text-white hover:opacity-60 text-lg font-black">✕</button>
        </div>
        <form onSubmit={handleSave} className="p-5 space-y-3 flex-1">
          <div><label className={lbl}>Título *</label>
            <input value={form.titulo} onChange={e => setForm(p => ({...p, titulo: e.target.value}))} required className={inp} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={lbl}>Fecha inicio *</label>
              <input type="date" value={form.fecha_inicio} onChange={e => setForm(p => ({...p, fecha_inicio: e.target.value}))} required className={inp} /></div>
            <div><label className={lbl}>Hora</label>
              <input type="time" value={form.hora_inicio} onChange={e => setForm(p => ({...p, hora_inicio: e.target.value}))} className={inp} /></div>
          </div>
          <div><label className={lbl}>Fecha fin</label>
            <input type="date" value={form.fecha_fin} onChange={e => setForm(p => ({...p, fecha_fin: e.target.value}))} className={inp} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={lbl}>Categoría</label>
              <select value={form.categoria_principal} onChange={e => setForm(p => ({...p, categoria_principal: e.target.value}))} className={inp}>
                {CATS_ADMIN.map(c => <option key={c} value={c}>{CAT_LABEL[c] ?? c}</option>)}</select></div>
            <div><label className={lbl}>Municipio</label>
              <select value={form.municipio} onChange={e => setForm(p => ({...p, municipio: e.target.value}))} className={inp}>
                {MUNICIPIOS_ADMIN.map(m => <option key={m} value={m}>{m}</option>)}</select></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={lbl}>Barrio</label>
              <input value={form.barrio} onChange={e => setForm(p => ({...p, barrio: e.target.value}))} className={inp} /></div>
            <div><label className={lbl}>Lugar</label>
              <input value={form.nombre_lugar} onChange={e => setForm(p => ({...p, nombre_lugar: e.target.value}))} className={inp} /></div>
          </div>
          <div><label className={lbl}>Descripción</label>
            <textarea value={form.descripcion} onChange={e => setForm(p => ({...p, descripcion: e.target.value}))} rows={3} className={`${inp} resize-none`} /></div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className={lbl}>Precio</label>
              <input value={form.precio} onChange={e => setForm(p => ({...p, precio: e.target.value}))} placeholder="$20.000" className={inp} /></div>
            <div className="flex flex-col justify-end gap-2 pb-1">
              <label className="flex items-center gap-2 cursor-pointer font-mono text-xs">
                <input type="checkbox" checked={form.es_gratuito} onChange={e => setForm(p => ({...p, es_gratuito: e.target.checked}))} />Gratuito</label>
              <label className="flex items-center gap-2 cursor-pointer font-mono text-xs">
                <input type="checkbox" checked={form.oculto} onChange={e => setForm(p => ({...p, oculto: e.target.checked}))} />Ocultar</label>
            </div>
          </div>
          <div><label className={lbl}>URL imagen</label>
            <input value={form.imagen_url} onChange={e => setForm(p => ({...p, imagen_url: e.target.value}))} placeholder="https://..." className={inp} /></div>
          <div><label className={lbl}>Link / más info</label>
            <input value={form.fuente_url} onChange={e => setForm(p => ({...p, fuente_url: e.target.value}))} placeholder="https://..." className={inp} /></div>
          {msg && <p className={`font-mono text-xs ${msg.ok ? 'text-green-700' : 'text-red-600'}`}>{msg.text}</p>}
          <div className="flex gap-3 pt-2">
            <button type="submit" disabled={saving}
              className="flex-1 py-2.5 bg-black text-white font-mono font-bold uppercase tracking-widest text-xs hover:bg-yellow-300 hover:text-black transition-colors disabled:opacity-50">
              {saving ? 'Guardando...' : '✓ Guardar cambios'}</button>
            <button type="button" onClick={onClose}
              className="px-4 py-2.5 border-2 border-black font-mono text-xs font-bold uppercase tracking-wider hover:bg-neutral-100 transition-colors">Cancelar</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── TAB: EVENTOS ──────────────────────────────────────────────────────────────

function TabEventos({ apiKey }: { apiKey: string }) {
  const [data, setData] = useState<Record<string, unknown>[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [categoria, setCategoria] = useState('')
  const [reportados, setReportados] = useState(false)
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)
  const [editing, setEditing] = useState<Record<string, unknown> | null>(null)

  const fetchData = useCallback(async (p: number) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(p), per_page: '50' })
      if (search) params.set('search', search)
      if (categoria) params.set('categoria', categoria)
      if (reportados) params.set('reportados', 'true')
      const res = await fetch(`${API_BASE}/admin/eventos?${params}`, { headers: { 'X-API-Key': apiKey } })
      const json = await res.json()
      setData(json.data || []); setTotal(json.total || 0)
    } catch { setData([]) } finally { setLoading(false) }
  }, [apiKey, search, categoria, reportados])

  useEffect(() => { setPage(1); fetchData(1) }, [search, categoria, reportados, fetchData])
  useEffect(() => { fetchData(page) }, [page, fetchData])

  async function handleDelete(row: Record<string, unknown>) {
    if (!confirm(`¿Borrar "${row.titulo}"?`)) return
    setDeleting(row.id as string)
    try {
      await fetch(`${API_BASE}/eventos/${row.id}`, { method: 'DELETE', headers: { 'X-Scraper-Key': apiKey } })
      fetchData(page)
    } finally { setDeleting(null) }
  }

  return (
    <div className="space-y-4">
      {editing && <EditEventoPanel row={editing} apiKey={apiKey} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void fetchData(page) }} />}
      <div className="flex flex-wrap gap-3">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar título..."
          className="border-2 border-black px-3 py-2 font-mono text-xs outline-none focus:border-yellow-400 w-48" />
        <input value={categoria} onChange={e => setCategoria(e.target.value)} placeholder="Categoría..."
          className="border-2 border-black px-3 py-2 font-mono text-xs outline-none focus:border-yellow-400 w-36" />
        <label className="flex items-center gap-2 font-mono text-xs cursor-pointer border-2 border-black px-3 py-2">
          <input type="checkbox" checked={reportados} onChange={e => setReportados(e.target.checked)} />
          Solo reportados
        </label>
      </div>
      <DataTable
        columns={[
          { key: 'titulo', label: 'Título' },
          { key: 'fecha_inicio', label: 'Fecha', render: r => (r.fecha_inicio as string)?.slice(0, 10) },
          { key: 'categoria_principal', label: 'Categoría', render: r => CAT_LABEL[r.categoria_principal as string] ?? String(r.categoria_principal) },
          { key: 'municipio', label: 'Municipio' },
          { key: 'oculto', label: '', render: r => r.oculto ? <span className="text-orange-400 text-[10px] font-bold">●OC</span> : '—' },
          { key: 'fuente', label: 'Fuente', render: r => (r.fuente as string)?.slice(0, 16) },
          { key: '_edit', label: '', render: r => (
            <button onClick={e => { e.stopPropagation(); setEditing(r) }}
              className="px-2 py-0.5 border border-black font-mono text-[9px] font-bold uppercase hover:bg-black hover:text-white transition-colors">
              ✎
            </button>
          )},
        ]}
        data={data} total={total} page={page} perPage={50} onPage={setPage}
        loading={loading || deleting !== null}
        onDelete={handleDelete} deleteLabel="✕"
      />
    </div>
  )
}

// ── TAB: ESPACIOS ─────────────────────────────────────────────────────────────

function TabEspacios({ apiKey }: { apiKey: string }) {
  const [data, setData] = useState<Record<string, unknown>[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [tipo, setTipo] = useState('')
  const [loading, setLoading] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  const fetchData = useCallback(async (p: number) => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ page: String(p), per_page: '50' })
      if (search) params.set('search', search)
      if (tipo) params.set('tipo', tipo)
      const res = await fetch(`${API_BASE}/admin/espacios?${params}`, { headers: { 'X-API-Key': apiKey } })
      const json = await res.json()
      setData(json.data || []); setTotal(json.total || 0)
    } catch { setData([]) } finally { setLoading(false) }
  }, [apiKey, search, tipo])

  useEffect(() => { setPage(1); fetchData(1) }, [search, tipo, fetchData])
  useEffect(() => { fetchData(page) }, [page, fetchData])

  async function handleDelete(row: Record<string, unknown>) {
    if (!confirm(`¿Borrar "${row.nombre}" y todos sus eventos?`)) return
    setDeleting(row.id as string)
    try {
      await fetch(`${API_BASE}/espacios/${row.id}`, { method: 'DELETE', headers: { 'X-Scraper-Key': apiKey } })
      fetchData(page)
    } finally { setDeleting(null) }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3">
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar nombre..."
          className="border-2 border-black px-3 py-2 font-mono text-xs outline-none focus:border-yellow-400 w-48" />
        <select value={tipo} onChange={e => setTipo(e.target.value)}
          className="border-2 border-black px-3 py-2 font-mono text-xs outline-none focus:border-yellow-400">
          <option value="">Todos los tipos</option>
          {['colectivo', 'espacio_cultural', 'teatro', 'galeria', 'libreria', 'equipamiento_publico'].map(t =>
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
        </select>
      </div>
      <DataTable
        columns={[
          { key: 'nombre', label: 'Nombre' },
          { key: 'tipo', label: 'Tipo', render: r => (r.tipo as string)?.replace(/_/g, ' ') },
          { key: 'categoria_principal', label: 'Categoría', render: r => CAT_LABEL[r.categoria_principal as string] ?? String(r.categoria_principal) },
          { key: 'municipio', label: 'Municipio' },
          { key: 'barrio', label: 'Barrio' },
          { key: 'instagram_handle', label: 'Instagram', render: r => r.instagram_handle ? <span className="text-blue-600">{String(r.instagram_handle)}</span> : '—' },
          { key: 'nivel_actividad', label: 'Actividad' },
          { key: 'verificado', label: 'Ver.', render: r => r.verificado ? '✓' : '—' },
        ]}
        data={data} total={total} page={page} perPage={50} onPage={setPage}
        loading={loading || deleting !== null}
        onDelete={handleDelete} deleteLabel="✕"
      />
    </div>
  )
}

// ── TAB: USUARIOS ─────────────────────────────────────────────────────────────

function TabUsuarios({ apiKey }: { apiKey: string }) {
  const [data, setData] = useState<Record<string, unknown>[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const fetchData = useCallback(async (p: number) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/admin/usuarios?page=${p}&per_page=50`, { headers: { 'X-API-Key': apiKey } })
      const json = await res.json()
      setData(json.data || []); setTotal(json.total || 0)
    } catch { setData([]) } finally { setLoading(false) }
  }, [apiKey])

  useEffect(() => { fetchData(page) }, [page, fetchData])

  return (
    <DataTable
      columns={[
        { key: 'email', label: 'Email' },
        { key: 'nombre', label: 'Nombre' },
        { key: 'municipio', label: 'Municipio' },
        { key: 'categoria', label: 'Categoría favorita', render: r => r.categoria ? CAT_LABEL[r.categoria as string] ?? String(r.categoria) : '—' },
        { key: 'created_at', label: 'Registro', render: r => (r.created_at as string)?.slice(0, 10) },
      ]}
      data={data} total={total} page={page} perPage={50} onPage={setPage} loading={loading}
    />
  )
}

// ── TAB: LOGS ─────────────────────────────────────────────────────────────────

function TabLogs({ apiKey }: { apiKey: string }) {
  const [data, setData] = useState<Record<string, unknown>[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const perPage = 50

  useEffect(() => {
    setLoading(true)
    fetch(`${API_BASE}/admin/logs?limit=200`, { headers: { 'X-API-Key': apiKey } })
      .then(r => r.json())
      .then(j => setData(j.data || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }, [apiKey])

  const total = data.length
  const pageData = data.slice((page - 1) * perPage, page * perPage)

  return (
    <DataTable
      columns={[
        { key: 'created_at', label: 'Fecha', render: r => (r.created_at as string)?.slice(0, 16).replace('T', ' ') },
        { key: 'fuente', label: 'Fuente' },
        { key: 'registros_nuevos', label: 'Nuevos' },
        { key: 'duplicados', label: 'Dupl.' },
        { key: 'errores', label: 'Err.', render: r => (r.errores as number) > 0 ? <span className="text-red-600 font-bold">{String(r.errores)}</span> : '0' },
        { key: 'duracion_segundos', label: 'Seg.', render: r => r.duracion_segundos ? `${Number(r.duracion_segundos).toFixed(0)}s` : '—' },
      ]}
      data={pageData} total={total} page={page} perPage={perPage} onPage={setPage} loading={loading}
    />
  )
}

// ── TAB: SUBIR EVENTO ────────────────────────────────────────────────────────

const CATS_ADMIN = [
  'teatro','musica_en_vivo','rock','jazz','hip_hop','electronica','danza','cine',
  'galeria','arte_contemporaneo','poesia','festival','taller','conferencia',
  'filosofia','circo','fotografia','libreria','editorial','otro',
]
const MUNICIPIOS_ADMIN = [
  'medellin','bello','itagui','envigado','sabaneta','caldas',
  'la_estrella','copacabana','girardota','barbosa',
]

const BLANK_FORM: EventoAdminCreate = {
  titulo: '', fecha_inicio: '', hora_inicio: '', fecha_fin: '',
  duracion_minutos: undefined, descripcion: '', link_externo: '',
  categoria_principal: 'otro', municipio: 'medellin',
  barrio: '', nombre_lugar: '', precio: '',
  es_gratuito: true, imagen_url: '', oculto: false,
}

function TabSubirEvento({ apiKey }: { apiKey: string }) {
  const [form, setForm] = useState<EventoAdminCreate>({ ...BLANK_FORM })
  const [imgPreview, setImgPreview] = useState('')
  const [uploading, setUploading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)
  const [manuales, setManuales] = useState<import('../lib/api').Evento[]>([])
  const [loadingList, setLoadingList] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [lastFile, setLastFile] = useState<File | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const loadManuales = useCallback(async () => {
    setLoadingList(true)
    try {
      const res = await adminGetEventosManuales(apiKey)
      setManuales(res.data)
    } catch { /* ignore */ } finally { setLoadingList(false) }
  }, [apiKey])

  useEffect(() => { void loadManuales() }, [loadManuales])

  function f(k: keyof EventoAdminCreate) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      const v = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked
        : e.target.type === 'number' ? (e.target.value ? Number(e.target.value) : undefined)
        : e.target.value
      setForm(prev => ({ ...prev, [k]: v }))
    }
  }

  async function handleFile(file: File) {
    if (!file.type.startsWith('image/')) { setMsg({ text: 'Solo se aceptan imágenes', ok: false }); return }
    setUploading(true); setMsg(null); setLastFile(file)
    try {
      const slug = form.titulo ? form.titulo.toLowerCase().replace(/\s+/g, '-').slice(0, 40) : 'evento'
      const res = await adminUploadEventImage(apiKey, file, slug)
      setForm(prev => ({ ...prev, imagen_url: res.url }))
      setImgPreview(res.url)
      setMsg({ text: '✓ Imagen subida — usa "✨ Extraer con IA" para llenar el formulario automáticamente', ok: true })
    } catch (e: unknown) {
      setMsg({ text: `Error: ${e instanceof Error ? e.message : String(e)}`, ok: false })
    } finally { setUploading(false) }
  }

  async function handleExtractAI() {
    if (!lastFile) { setMsg({ text: 'Primero sube una imagen', ok: false }); return }
    setExtracting(true); setMsg(null)
    try {
      const res = await adminExtraerDeImagen(apiKey, lastFile)
      const d = res.data
      setForm(prev => ({
        ...prev,
        titulo: d.titulo ?? prev.titulo,
        fecha_inicio: d.fecha_inicio ?? prev.fecha_inicio,
        fecha_fin: d.fecha_fin ?? prev.fecha_fin,
        hora_inicio: d.hora_inicio ?? prev.hora_inicio,
        descripcion: d.descripcion ?? prev.descripcion,
        categoria_principal: d.categoria_principal ?? prev.categoria_principal,
        municipio: d.municipio ?? prev.municipio,
        barrio: d.barrio ?? prev.barrio,
        nombre_lugar: d.nombre_lugar ?? prev.nombre_lugar,
        precio: d.precio ?? prev.precio,
        es_gratuito: d.es_gratuito ?? prev.es_gratuito,
        link_externo: d.link_externo ?? prev.link_externo,
      }))
      setMsg({ text: '✨ Campos extraídos con IA — revisa y ajusta antes de publicar', ok: true })
    } catch (e: unknown) {
      setMsg({ text: `Error IA: ${e instanceof Error ? e.message : String(e)}`, ok: false })
    } finally { setExtracting(false) }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.titulo || !form.fecha_inicio) { setMsg({ text: 'Título y fecha son obligatorios', ok: false }); return }
    setSubmitting(true); setMsg(null)
    try {
      await adminCrearEvento(apiKey, form)
      setMsg({ text: '✓ Evento creado correctamente', ok: true })
      setForm({ ...BLANK_FORM }); setImgPreview('')
      void loadManuales()
    } catch (e: unknown) {
      setMsg({ text: `Error: ${e instanceof Error ? e.message : String(e)}`, ok: false })
    } finally { setSubmitting(false) }
  }

  async function toggleOculto(ev: import('../lib/api').Evento) {
    try {
      await adminActualizarEvento(apiKey, ev.id, { oculto: !ev.oculto })
      void loadManuales()
    } catch { /* ignore */ }
  }

  async function handleDelete(ev: import('../lib/api').Evento) {
    if (!confirm(`¿Eliminar "${ev.titulo}"?`)) return
    try { await adminDeleteEvento(apiKey, ev.id); void loadManuales() } catch { /* ignore */ }
  }

  return (
    <div className="space-y-8">
      {/* Form */}
      <form onSubmit={handleSubmit} className="border-2 border-black p-6">
        <h2 className="font-mono font-bold uppercase tracking-widest text-xs mb-6">Subir evento manualmente</h2>

        {/* Image upload */}
        <div
          className={`border-2 ${isDragging ? 'border-yellow-400 bg-yellow-50' : 'border-black border-dashed'} p-6 text-center cursor-pointer mb-6 transition-colors`}
          onClick={() => fileRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={e => { e.preventDefault(); setIsDragging(false); const f = e.dataTransfer.files[0]; if (f) void handleFile(f) }}
        >
          {imgPreview ? (
            <img src={imgPreview} alt="preview" className="max-h-40 mx-auto object-contain" />
          ) : (
            <p className="font-mono text-xs text-neutral-400 uppercase tracking-wider">
              {uploading ? 'Subiendo imagen...' : 'Arrastra un poster/imagen aquí o haz clic para seleccionar'}
            </p>
          )}
          <input ref={fileRef} type="file" accept="image/*" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) void handleFile(f) }} />
        </div>

        {/* AI extract button */}
        {lastFile && (
          <div className="mb-4 flex items-center gap-3">
            <button type="button" onClick={handleExtractAI} disabled={extracting || uploading}
              className="px-4 py-2 bg-yellow-300 text-black font-mono font-bold text-xs uppercase tracking-widest border-2 border-black hover:bg-yellow-400 transition-colors disabled:opacity-50 flex items-center gap-2">
              {extracting ? <><span className="w-3 h-3 border-2 border-black border-t-transparent rounded-full animate-spin inline-block" /> Analizando...</> : '✨ Extraer datos con IA'}
            </button>
            <span className="text-[10px] font-mono opacity-50">Claude Haiku leerá el afiche y llenará el formulario</span>
          </div>
        )}

        {/* URL manual override */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">URL de imagen (opcional)</span>
            <input value={form.imagen_url ?? ''} onChange={f('imagen_url')}
              placeholder="https://... o dejar vacío si subiste archivo"
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
          </label>
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Título *</span>
            <input value={form.titulo} onChange={f('titulo')} required
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Fecha inicio *</span>
            <input type="date" value={form.fecha_inicio} onChange={f('fecha_inicio')} required
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
          </label>
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Hora inicio</span>
            <input type="time" value={form.hora_inicio ?? ''} onChange={f('hora_inicio')}
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
          </label>
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Duración (min)</span>
            <input type="number" min={1} max={1440} value={form.duracion_minutos ?? ''} onChange={f('duracion_minutos')}
              placeholder="ej: 90"
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Fecha fin (opcional)</span>
            <input type="date" value={form.fecha_fin ?? ''} onChange={f('fecha_fin')}
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
          </label>
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Categoría</span>
            <select value={form.categoria_principal} onChange={f('categoria_principal')}
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400">
              {CATS_ADMIN.map(c => <option key={c} value={c}>{CAT_LABEL[c] ?? c}</option>)}
            </select>
          </label>
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Municipio</span>
            <select value={form.municipio} onChange={f('municipio')}
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400">
              {MUNICIPIOS_ADMIN.map(m => <option key={m} value={m}>{m.replace(/_/g, ' ')}</option>)}
            </select>
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Barrio</span>
            <input value={form.barrio ?? ''} onChange={f('barrio')}
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
          </label>
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Nombre del lugar</span>
            <input value={form.nombre_lugar ?? ''} onChange={f('nombre_lugar')}
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
          </label>
          <label className="block">
            <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Precio</span>
            <input value={form.precio ?? ''} onChange={f('precio')} placeholder="ej: $25.000 o Gratis"
              className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
          </label>
        </div>

        <label className="block mb-4">
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Descripción</span>
          <textarea value={form.descripcion ?? ''} onChange={f('descripcion')} rows={3}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400 resize-none" />
        </label>

        <label className="block mb-4">
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider">Link / Más información (opcional)</span>
          <input value={form.link_externo ?? ''} onChange={f('link_externo')}
            placeholder="https://... (registro, web del evento, redes sociales)"
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm mt-1 outline-none focus:border-yellow-400" />
        </label>

        <div className="flex flex-wrap items-center gap-6 mb-6">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.es_gratuito} onChange={f('es_gratuito')}
              className="w-4 h-4 border-2 border-black accent-black" />
            <span className="font-mono text-xs uppercase tracking-wider font-bold">Gratuito</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.oculto} onChange={f('oculto')}
              className="w-4 h-4 border-2 border-black accent-black" />
            <span className="font-mono text-xs uppercase tracking-wider font-bold">Ocultar (no publicar)</span>
          </label>
        </div>

        {msg && (
          <p className={`font-mono text-xs mb-4 ${msg.ok ? 'text-green-700' : 'text-red-600'}`}>{msg.text}</p>
        )}

        <button type="submit" disabled={submitting || uploading}
          className="px-6 py-3 bg-black text-white font-mono font-bold uppercase tracking-widest text-sm hover:bg-yellow-300 hover:text-black transition-colors disabled:opacity-50">
          {submitting ? 'Guardando...' : 'Publicar evento →'}
        </button>
      </form>

      {/* List of manual events */}
      <div className="border-2 border-black p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-mono font-bold uppercase tracking-widest text-xs">Eventos subidos manualmente</h2>
          <button onClick={loadManuales} className="font-mono text-[10px] uppercase tracking-wider hover:underline">↺ Actualizar</button>
        </div>
        {loadingList ? (
          <p className="font-mono text-xs text-neutral-400 animate-pulse">Cargando...</p>
        ) : manuales.length === 0 ? (
          <p className="font-mono text-xs text-neutral-400">No hay eventos subidos manualmente aún.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] font-mono border-collapse">
              <thead>
                <tr className="bg-black text-white">
                  {['Título','Fecha','Categoría','Lugar','Visible','Acciones'].map(h => (
                    <th key={h} className="text-left px-3 py-2 font-bold uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {manuales.map(ev => (
                  <tr key={ev.id} className={`border-b border-black/10 ${ev.oculto ? 'opacity-50' : ''}`}>
                    <td className="px-3 py-2 max-w-[180px] truncate font-medium">{ev.titulo}</td>
                    <td className="px-3 py-2 whitespace-nowrap">{(ev.fecha_inicio ?? '').slice(0, 10)}</td>
                    <td className="px-3 py-2">{CAT_LABEL[ev.categoria_principal] ?? ev.categoria_principal}</td>
                    <td className="px-3 py-2 max-w-[140px] truncate">{ev.nombre_lugar ?? ev.barrio ?? '—'}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => void toggleOculto(ev)}
                        className={`px-2 py-0.5 border font-bold text-[9px] uppercase tracking-wider transition-colors ${ev.oculto ? 'border-red-400 text-red-600 hover:bg-red-50' : 'border-green-500 text-green-700 hover:bg-green-50'}`}>
                        {ev.oculto ? 'Oculto' : 'Visible'}
                      </button>
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap space-x-2">
                      {ev.imagen_url && (
                        <img src={ev.imagen_url} alt="" className="w-8 h-8 object-cover inline-block border border-black/20" />
                      )}
                      <button onClick={() => void handleDelete(ev)}
                        className="text-red-600 hover:text-red-800 font-bold text-[10px] uppercase tracking-wider">
                        Borrar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Bulk upload section ── */}
      <BulkUpload apiKey={apiKey} onDone={loadManuales} />
    </div>
  )
}

// ── BULK UPLOAD ───────────────────────────────────────────────────────────────

function BulkUpload({ apiKey, onDone }: { apiKey: string; onDone: () => void }) {
  const [files, setFiles] = useState<File[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [progress, setProgress] = useState<{ status: string; total: number; done: number; errors: number; created: { id: string; titulo: string }[] } | null>(null)
  const [running, setRunning] = useState(false)
  const [isDrag, setIsDrag] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function addFiles(newFiles: FileList | null) {
    if (!newFiles) return
    const imgs = Array.from(newFiles).filter(f => f.type.startsWith('image/'))
    setFiles(prev => [...prev, ...imgs].slice(0, 100))
  }

  async function handleStart() {
    if (!files.length) return
    setRunning(true); setProgress(null)
    try {
      const res = await adminCrearMasivo(apiKey, files)
      setJobId(res.job_id)
      // Poll progress
      const poll = setInterval(async () => {
        try {
          const s = await adminMasivoStatus(apiKey, res.job_id)
          setProgress(s)
          if (s.status === 'done') {
            clearInterval(poll)
            setRunning(false)
            setFiles([])
            onDone()
          }
        } catch { clearInterval(poll); setRunning(false) }
      }, 3000)
    } catch (e: unknown) {
      alert(`Error: ${e instanceof Error ? e.message : String(e)}`)
      setRunning(false)
    }
  }

  return (
    <div className="border-2 border-black p-6 border-dashed">
      <h2 className="font-mono font-bold uppercase tracking-widest text-xs mb-2">✨ Carga masiva con IA</h2>
      <p className="font-mono text-[10px] text-neutral-500 mb-4">
        Sube varios afiches a la vez. Claude Haiku extrae los datos de cada uno y crea los eventos automáticamente. (~$0.002 USD por imagen)
      </p>

      {/* Drop zone */}
      <div
        className={`border-2 ${isDrag ? 'border-yellow-400 bg-yellow-50' : 'border-black border-dashed'} p-8 text-center cursor-pointer mb-4 transition-colors`}
        onClick={() => inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setIsDrag(true) }}
        onDragLeave={() => setIsDrag(false)}
        onDrop={e => { e.preventDefault(); setIsDrag(false); addFiles(e.dataTransfer.files) }}
      >
        <p className="font-mono text-xs text-neutral-400 uppercase tracking-wider">
          {files.length > 0
            ? `${files.length} imagen${files.length > 1 ? 'es' : ''} seleccionada${files.length > 1 ? 's' : ''} — arrastra más o haz clic`
            : 'Arrastra afiches aquí o haz clic (máx. 100 imágenes)'}
        </p>
        <input ref={inputRef} type="file" accept="image/*" multiple className="hidden"
          onChange={e => addFiles(e.target.files)} />
      </div>

      {/* Preview thumbnails */}
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-4">
          {files.map((f, i) => (
            <div key={i} className="relative">
              <img src={URL.createObjectURL(f)} alt="" className="w-16 h-16 object-cover border-2 border-black" />
              <button onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))}
                className="absolute -top-1 -right-1 bg-black text-white text-[9px] w-4 h-4 flex items-center justify-center font-bold">✕</button>
            </div>
          ))}
        </div>
      )}

      {/* Progress */}
      {progress && (
        <div className="border-2 border-black p-4 mb-4 font-mono text-xs">
          <div className="flex items-center gap-4 mb-2">
            <span className="font-bold uppercase tracking-wider">
              {progress.status === 'done' ? '✓ Completado' : '⏳ Procesando...'}
            </span>
            <span>{progress.done}/{progress.total} imágenes</span>
            {progress.errors > 0 && <span className="text-red-600">{progress.errors} errores</span>}
          </div>
          <div className="w-full bg-neutral-200 h-2 mb-3">
            <div className="bg-black h-2 transition-all" style={{ width: `${(progress.done / progress.total) * 100}%` }} />
          </div>
          {progress.created.length > 0 && (
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {progress.created.map(ev => (
                <div key={ev.id} className="text-green-700">✓ {ev.titulo}</div>
              ))}
            </div>
          )}
          {progress.status === 'done' && (
            <p className="mt-2 text-green-700 font-bold">
              {progress.created.length} eventos creados correctamente.
            </p>
          )}
        </div>
      )}

      <button onClick={handleStart} disabled={!files.length || running}
        className="px-6 py-3 bg-yellow-300 text-black font-mono font-bold uppercase tracking-widest text-sm border-2 border-black hover:bg-yellow-400 transition-colors disabled:opacity-40 flex items-center gap-2">
        {running
          ? <><span className="w-3 h-3 border-2 border-black border-t-transparent rounded-full animate-spin inline-block" /> Procesando con IA...</>
          : `✨ Crear ${files.length || 0} evento${files.length !== 1 ? 's' : ''} con IA`}
      </button>
      {jobId && <p className="font-mono text-[10px] text-neutral-400 mt-2">Job ID: {jobId}</p>}
    </div>
  )
}

// ── TAB: BUSCAR WEB (Google de Cultura) ──────────────────────────────────────

const WEB_PRESETS = [
  'teatro medellin junio 2026',
  'comfama agenda cultural junio 2026',
  'fundacion epm eventos junio 2026',
  'bibliotecas medellin agenda junio 2026',
  'festival cultural medellin 2026',
  'danza contemporanea medellin junio 2026',
  'conciertos jazz medellin 2026',
  'colectivos culturales medellin eventos',
  'exposicion arte medellin junio 2026',
  'museo arte medellin eventos 2026',
  'teatro pablo tobón uribe agenda',
  'tango medellin junio 2026',
]

function TabBuscarWeb({ apiKey }: { apiKey: string }) {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [results, setResults] = useState<{ message: string; nuevos: number; duplicados: number; found: number } | null>(null)
  const [log, setLog] = useState<string[]>([])
  const [autoAdd, setAutoAdd] = useState(true)

  async function runSearch(q: string) {
    if (!q.trim() || searching) return
    setSearching(true); setResults(null)
    setLog(prev => [`🔍 Buscando: "${q}"...`, ...prev.slice(0, 19)])
    try {
      const params = new URLSearchParams({
        texto: q, max_queries: '4', max_results_per_query: '6',
        days_ahead: '60', strict_categoria: 'false',
        auto_insert: String(autoAdd),
      })
      const res = await fetch(`${API_BASE}/scraper/discover-events/publico?${params}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey }, body: '{}',
        signal: AbortSignal.timeout(90000),
      })
      const json = await res.json() as { message?: string; result?: { nuevos?: number; duplicados?: number; encontrados?: number; candidatos?: unknown[] } }
      const r = json.result ?? {}
      const nuevos = r.nuevos ?? 0
      const dups = r.duplicados ?? 0
      const found = r.encontrados ?? (r.candidatos as unknown[])?.length ?? 0
      setResults({ message: json.message ?? '', nuevos, duplicados: dups, found })
      setLog(prev => [
        nuevos > 0 ? `✅ "${q}" → ${nuevos} eventos nuevos agregados` : `ℹ️ "${q}" → ${found} encontrados, ${dups} ya existían`,
        ...prev,
      ])
    } catch {
      setLog(prev => [`❌ Error buscando "${q}" — intenta de nuevo`, ...prev])
    } finally { setSearching(false) }
  }

  async function runAllPresets() {
    for (const preset of WEB_PRESETS) {
      await runSearch(preset)
      await new Promise(r => setTimeout(r, 2000)) // polite delay
    }
  }

  return (
    <div className="space-y-6">
      <div className="border-2 border-black p-5">
        <h2 className="font-mono font-bold uppercase tracking-widest text-xs mb-1">🌐 Google de Cultura</h2>
        <p className="font-mono text-[10px] text-neutral-500 mb-4">
          Busca eventos culturales en internet con DuckDuckGo + IA. Los eventos nuevos se agregan automáticamente al sistema.
        </p>

        {/* Custom search */}
        <div className="flex gap-2 mb-4">
          <input value={query} onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && void runSearch(query)}
            placeholder="teatro medellin junio 2026, comfama agenda..."
            className="flex-1 border-2 border-black px-3 py-2 font-mono text-sm outline-none focus:border-yellow-400" />
          <button onClick={() => void runSearch(query)} disabled={searching || !query.trim()}
            className="px-4 py-2 bg-black text-white font-mono font-bold text-xs uppercase tracking-wider hover:bg-yellow-300 hover:text-black transition-colors disabled:opacity-50">
            {searching ? <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin inline-block" /> : 'Buscar →'}
          </button>
        </div>

        <div className="flex items-center gap-4 mb-4">
          <label className="flex items-center gap-2 font-mono text-xs cursor-pointer">
            <input type="checkbox" checked={autoAdd} onChange={e => setAutoAdd(e.target.checked)} />
            Agregar automáticamente al sistema
          </label>
          <button onClick={() => void runAllPresets()} disabled={searching}
            className="px-4 py-2 bg-yellow-300 text-black border-2 border-black font-mono font-bold text-xs uppercase tracking-wider hover:bg-yellow-400 transition-colors disabled:opacity-50">
            ✨ Barrer todas las fuentes ({WEB_PRESETS.length})
          </button>
        </div>

        {/* Preset chips */}
        <div className="flex flex-wrap gap-2 mb-4">
          {WEB_PRESETS.map(p => (
            <button key={p} onClick={() => { setQuery(p); void runSearch(p) }} disabled={searching}
              className="text-[10px] font-mono border border-black px-2 py-1 hover:bg-black hover:text-white transition-all disabled:opacity-40">
              {p}
            </button>
          ))}
        </div>

        {/* Result */}
        {results && (
          <div className={`border-2 p-3 font-mono text-xs mb-4 ${results.nuevos > 0 ? 'border-green-500 bg-green-50' : 'border-black/20'}`}>
            <p className="font-bold">{results.nuevos > 0 ? `✅ ${results.nuevos} eventos nuevos agregados` : `ℹ️ Sin eventos nuevos`}</p>
            <p className="text-neutral-500 mt-1">{results.found} encontrados · {results.duplicados} ya existían en el sistema</p>
            <p className="text-neutral-400 mt-1 text-[10px]">{results.message}</p>
          </div>
        )}
      </div>

      {/* Activity log */}
      {log.length > 0 && (
        <div className="border-2 border-black p-4">
          <p className="font-mono text-[10px] font-bold uppercase tracking-wider mb-3">Log de búsquedas</p>
          <div className="space-y-1 max-h-48 overflow-y-auto">
            {log.map((l, i) => (
              <p key={i} className="font-mono text-[10px] text-neutral-600">{l}</p>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ── TAB: MODELO IA ────────────────────────────────────────────────────────────

function TabModeloIA({ apiKey }: { apiKey: string }) {
  const [status, setStatus] = useState<ModeloIAStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [training, setTraining] = useState(false)
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try { setStatus(await adminGetModeloIA(apiKey)) }
    catch { /* ignore */ } finally { setLoading(false) }
  }, [apiKey])

  useEffect(() => { void load() }, [load])

  async function retrain() {
    setTraining(true); setMsg(null)
    try {
      const res = await adminReentrenarModelo(apiKey)
      setMsg({ text: `✓ Modelo entrenado — F1: ${res.metrics.f1 ?? '?'}`, ok: true })
      void load()
    } catch (e: unknown) {
      setMsg({ text: `Error: ${e instanceof Error ? e.message : String(e)}`, ok: false })
    } finally { setTraining(false) }
  }

  if (loading) return <p className="font-mono text-sm animate-pulse">Cargando estado del modelo...</p>
  if (!status) return <p className="font-mono text-sm text-red-600">No se pudo cargar el estado del modelo.</p>

  const m = status.metrics
  const isTrained = status.status === 'trained'

  return (
    <div className="space-y-8">
      {/* Status header */}
      <div className="border-2 border-black p-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-neutral-500 mb-1">Estado del modelo</p>
          <div className="flex items-center gap-3">
            <span className={`text-xs font-mono font-bold uppercase tracking-wider px-2 py-0.5 border-2 ${isTrained ? 'border-green-500 text-green-700' : 'border-red-400 text-red-600'}`}>
              {isTrained ? '● Entrenado' : '○ Sin entrenar'}
            </span>
            {isTrained && status.trained_at && (
              <span className="text-[10px] font-mono text-neutral-400">
                {new Date(status.trained_at).toLocaleString('es-CO', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
          {isTrained && (
            <p className="text-[10px] font-mono text-neutral-500 mt-2">
              {status.training_count} ejemplos de entrenamiento · {status.n_positivos} positivos · {status.n_negativos} negativos
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          <ActionBtn label={training ? 'Entrenando...' : 'Reentrenar modelo'} onClick={() => void retrain()} loading={training} variant="yellow" />
          <p className="text-[9px] font-mono text-neutral-400 text-right max-w-[200px]">
            Extrae eventos de fuentes confiables de la BD y mejora la precisión del clasificador.
          </p>
        </div>
      </div>

      {msg && <p className={`font-mono text-xs ${msg.ok ? 'text-green-700' : 'text-red-600'}`}>{msg.text}</p>}

      {/* Metrics */}
      {isTrained && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Stat label="Exactitud" value={m.accuracy != null ? `${(m.accuracy * 100).toFixed(1)}%` : '—'} sub="accuracy" />
          <Stat label="Precisión" value={m.precision != null ? `${(m.precision * 100).toFixed(1)}%` : '—'} sub="precision" />
          <Stat label="Recall" value={m.recall != null ? `${(m.recall * 100).toFixed(1)}%` : '—'} sub="recall" />
          <Stat label="F1 Score" value={m.f1 != null ? `${(m.f1 * 100).toFixed(1)}%` : '—'} sub="f1" />
        </div>
      )}

      {/* Feature importances */}
      {isTrained && status.feature_importances.length > 0 && (
        <div className="border-2 border-black p-4">
          <p className="text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-neutral-500 mb-4">Importancia de características</p>
          <div className="space-y-2">
            {status.feature_importances.slice(0, 8).map(feat => {
              const maxW = Math.max(...status.feature_importances.map(f => Math.abs(f.weight)))
              const pct = Math.round((Math.abs(feat.weight) / (maxW || 1)) * 100)
              const isPos = feat.weight > 0
              return (
                <div key={feat.name} className="flex items-center gap-3">
                  <span className="font-mono text-[10px] w-40 shrink-0 text-neutral-600 truncate">{feat.name.replace(/_/g, ' ')}</span>
                  <div className="flex-1 h-4 bg-neutral-100 border border-black/10 overflow-hidden">
                    <div
                      className={`h-full ${isPos ? 'bg-green-500' : 'bg-red-400'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className={`font-mono text-[10px] w-12 text-right font-bold ${isPos ? 'text-green-700' : 'text-red-600'}`}>
                    {feat.weight > 0 ? '+' : ''}{feat.weight.toFixed(2)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Recent predictions */}
      {isTrained && status.recent_predictions.length > 0 && (
        <div className="border-2 border-black p-4">
          <p className="text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-neutral-500 mb-4">Últimas clasificaciones</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] font-mono">
              <thead>
                <tr className="bg-black text-white">
                  <th className="text-left px-3 py-2 font-bold uppercase tracking-wider">Título</th>
                  <th className="text-left px-3 py-2 font-bold uppercase tracking-wider w-20">Prob.</th>
                  <th className="text-left px-3 py-2 font-bold uppercase tracking-wider w-24">Resultado</th>
                  <th className="text-left px-3 py-2 font-bold uppercase tracking-wider w-32">Hora</th>
                </tr>
              </thead>
              <tbody>
                {status.recent_predictions.slice().reverse().map((p, i) => (
                  <tr key={i} className="border-b border-black/10 hover:bg-yellow-50">
                    <td className="px-3 py-1.5 max-w-[250px] truncate">{p.titulo}</td>
                    <td className="px-3 py-1.5">
                      <div className="flex items-center gap-1.5">
                        <div className="flex-1 h-2 bg-neutral-100 border border-black/10">
                          <div className={`h-full ${p.prob >= 0.5 ? 'bg-green-400' : 'bg-red-300'}`} style={{ width: `${p.prob * 100}%` }} />
                        </div>
                        <span className="text-[9px]">{(p.prob * 100).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="px-3 py-1.5">
                      <span className={`text-[9px] font-bold uppercase px-1.5 py-0.5 ${p.result ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'}`}>
                        {p.result ? '✓ Evento' : '✗ No evento'}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-neutral-400">{p.ts.slice(11, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!isTrained && (
        <div className="border-2 border-black/20 border-dashed p-8 text-center">
          <p className="font-mono text-sm text-neutral-400 uppercase tracking-wider">
            El modelo no ha sido entrenado aún.
          </p>
          <p className="font-mono text-xs text-neutral-300 mt-2">
            Haz clic en "Reentrenar modelo" para entrenar con los eventos actuales de la BD.
          </p>
        </div>
      )}
    </div>
  )
}

// ── MAIN ──────────────────────────────────────────────────────────────────────

export default function Admin() {
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem(KEY_STORAGE) || '')
  const [inputKey, setInputKey] = useState('')
  const [dashData, setDashData] = useState<AdminDashboard | null>(null)
  const [dashLoading, setDashLoading] = useState(false)
  const [dashError, setDashError] = useState('')
  const [activeTab, setActiveTab] = useState<Tab>('resumen')

  const loadDash = useCallback(async (key: string) => {
    setDashLoading(true); setDashError('')
    try {
      const d = await getAdminDashboard(key)
      setDashData(d); sessionStorage.setItem(KEY_STORAGE, key); setApiKey(key)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setDashError(msg === '403' ? 'API key incorrecta' : `Error: ${msg}`)
      setDashData(null)
    } finally { setDashLoading(false) }
  }, [])

  useEffect(() => { if (apiKey) loadDash(apiKey) }, [apiKey, loadDash])

  // Login screen
  if (!apiKey) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-4">
        <Helmet><title>Admin — Cultura ETÉREA</title></Helmet>
        <div className="border-2 border-black p-10 max-w-sm w-full">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.3em] mb-6">Cultura ETÉREA · Admin</p>
          <h1 className="text-2xl font-heading font-black uppercase mb-6">Panel de Control</h1>
          <input type="password" placeholder="API key de admin" value={inputKey}
            onChange={e => setInputKey(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && loadDash(inputKey)}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm mb-4 outline-none focus:border-yellow-400" />
          {dashError && <p className="text-red-600 font-mono text-xs mb-3">{dashError}</p>}
          <button onClick={() => loadDash(inputKey)} disabled={!inputKey || dashLoading}
            className="w-full py-3 bg-black text-white font-mono font-bold uppercase tracking-widest text-sm hover:bg-yellow-300 hover:text-black transition-colors disabled:opacity-50">
            {dashLoading ? 'Cargando...' : 'Entrar →'}
          </button>
        </div>
      </div>
    )
  }

  const TABS: { id: Tab; label: string }[] = [
    { id: 'resumen', label: 'Resumen' },
    { id: 'eventos', label: 'Eventos' },
    { id: 'espacios', label: 'Espacios' },
    { id: 'usuarios', label: 'Usuarios' },
    { id: 'logs', label: 'Logs' },
    { id: 'subir_evento', label: '+ Subir Evento' },
    { id: 'buscar_web', label: '🌐 Buscar Web' },
    { id: 'modelo_ia', label: 'Modelo IA' },
    { id: 'mapa', label: 'Mapa' },
  ]

  return (
    <>
      <Helmet><title>Admin — Cultura ETÉREA</title></Helmet>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6 border-b-2 border-black pb-4">
          <div>
            <p className="text-[9px] font-mono font-bold uppercase tracking-[0.3em] text-neutral-500">Cultura ETÉREA</p>
            <h1 className="text-xl font-heading font-black uppercase">Panel de Control</h1>
          </div>
          <div className="flex items-center gap-2">
            {dashData && (
              <p className="text-[9px] font-mono text-neutral-400 hidden sm:block">
                {new Date(dashData.generado_en).toLocaleString('es-CO', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}
              </p>
            )}
            <button onClick={() => loadDash(apiKey)}
              className="px-3 py-1.5 border-2 border-black font-mono text-[10px] font-bold uppercase hover:bg-black hover:text-white transition-colors">
              ↺ Actualizar
            </button>
            <button onClick={() => { sessionStorage.removeItem(KEY_STORAGE); setApiKey(''); setDashData(null) }}
              className="px-3 py-1.5 border border-black/30 font-mono text-[10px] text-neutral-500 hover:border-black hover:text-black transition-colors">
              Salir
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 border-b-2 border-black mb-6 overflow-x-auto">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2.5 font-mono text-[11px] font-bold uppercase tracking-wider whitespace-nowrap border-r border-black/20 transition-colors
                ${activeTab === t.id ? 'bg-black text-white' : 'hover:bg-yellow-50'}`}>
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'resumen' && (
          dashLoading ? <p className="font-mono text-sm animate-pulse">Cargando...</p>
          : dashError ? <p className="font-mono text-sm text-red-600">{dashError}</p>
          : dashData ? <TabResumen d={dashData} apiKey={apiKey} />
          : null
        )}
        {activeTab === 'eventos' && <TabEventos apiKey={apiKey} />}
        {activeTab === 'espacios' && <TabEspacios apiKey={apiKey} />}
        {activeTab === 'usuarios' && <TabUsuarios apiKey={apiKey} />}
        {activeTab === 'logs' && <TabLogs apiKey={apiKey} />}
        {activeTab === 'subir_evento' && <TabSubirEvento apiKey={apiKey} />}
        {activeTab === 'buscar_web' && <TabBuscarWeb apiKey={apiKey} />}
        {activeTab === 'modelo_ia' && <TabModeloIA apiKey={apiKey} />}
        {activeTab === 'mapa' && (
          <div className="border-2 border-black overflow-hidden">
            <Suspense fallback={<div className="h-[600px] flex items-center justify-center font-mono text-sm text-neutral-400 animate-pulse">Cargando mapa...</div>}>
              <CulturalMap />
            </Suspense>
          </div>
        )}
      </div>
    </>
  )
}
