import { useState, useEffect, useCallback, lazy, Suspense } from 'react'
import { Helmet } from 'react-helmet-async'
import {
  getAdminDashboard, adminTriggerScraper, adminTriggerBlastTick, adminTriggerCleanup,
  type AdminDashboard,
} from '../lib/api'

const CulturalMap = lazy(() => import('../components/map/CulturalMap'))
const KEY_STORAGE = 'admin:apikey'
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

type Tab = 'resumen' | 'eventos' | 'espacios' | 'usuarios' | 'logs' | 'mapa'

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
          { key: 'verificado', label: 'Ver.', render: r => r.verificado ? '✓' : '—' },
          { key: 'reportado', label: 'Rep.', render: r => r.reportado ? <span className="text-red-600 font-bold">⚠</span> : '—' },
          { key: 'fuente', label: 'Fuente', render: r => (r.fuente as string)?.slice(0, 20) },
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
