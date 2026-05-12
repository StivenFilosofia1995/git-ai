import { useState, useEffect, useCallback } from 'react'
import { Helmet } from 'react-helmet-async'
import {
  getAdminDashboard,
  adminTriggerScraper,
  adminTriggerBlastTick,
  adminTriggerCleanup,
  type AdminDashboard,
} from '../lib/api'

const KEY_STORAGE = 'admin:apikey'

const CAT_LABEL: Record<string, string> = {
  teatro: 'Teatro', hip_hop: 'Hip Hop', jazz: 'Jazz', galeria: 'Galería',
  arte_contemporaneo: 'Arte', electronica: 'Electrónica', danza: 'Danza',
  musica_en_vivo: 'Música en vivo', poesia: 'Poesía', festival: 'Festival',
  cine: 'Cine', fotografia: 'Foto', filosofia: 'Filosofía', taller: 'Taller',
  circo: 'Circo', rock: 'Rock', punk: 'Punk', libreria: 'Librería',
  casa_cultura: 'Casa Cultura', centro_cultural: 'Centro Cultural', otro: 'Otro',
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="border-2 border-black p-4">
      <p className="text-[9px] font-mono font-bold uppercase tracking-[0.2em] text-neutral-500 mb-1">{label}</p>
      <p className="text-3xl font-heading font-black leading-none">{value}</p>
      {sub && <p className="text-[10px] font-mono text-neutral-400 mt-1">{sub}</p>}
    </div>
  )
}

function ActionBtn({
  label, onClick, loading, variant = 'default',
}: {
  label: string
  onClick: () => void
  loading?: boolean
  variant?: 'default' | 'yellow' | 'red'
}) {
  const bg = variant === 'yellow' ? 'bg-yellow-300 hover:bg-yellow-400 border-yellow-400'
    : variant === 'red' ? 'bg-red-600 text-white hover:bg-red-700 border-red-600'
    : 'bg-white hover:bg-black hover:text-white'
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`px-4 py-2.5 border-2 border-black font-mono text-[11px] font-bold uppercase tracking-widest transition-colors duration-150 disabled:opacity-50 ${bg}`}
    >
      {loading ? '...' : label}
    </button>
  )
}

export default function Admin() {
  const [apiKey, setApiKey] = useState(() => sessionStorage.getItem(KEY_STORAGE) || '')
  const [inputKey, setInputKey] = useState('')
  const [data, setData] = useState<AdminDashboard | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [actionMsg, setActionMsg] = useState('')
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const load = useCallback(async (key: string) => {
    if (!key) return
    setLoading(true)
    setError('')
    try {
      const d = await getAdminDashboard(key)
      setData(d)
      sessionStorage.setItem(KEY_STORAGE, key)
      setApiKey(key)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg === '403' ? 'API key incorrecta' : `Error: ${msg}`)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (apiKey) load(apiKey)
  }, [apiKey, load])

  async function runAction(id: string, fn: () => Promise<unknown>) {
    setActionLoading(id)
    setActionMsg('')
    try {
      const res = await fn() as { ok: boolean; message?: string; stats?: Record<string, unknown> }
      const msg = res.message || JSON.stringify(res.stats || res)
      setActionMsg(`✓ ${msg}`)
      setTimeout(() => load(apiKey), 2000)
    } catch (e: unknown) {
      setActionMsg(`✗ Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setActionLoading(null)
    }
  }

  if (!apiKey && !data) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center px-4">
        <Helmet><title>Admin — Cultura ETÉREA</title></Helmet>
        <div className="border-2 border-black p-10 max-w-sm w-full">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.3em] mb-6">
            Cultura ETÉREA · Admin
          </p>
          <h1 className="text-2xl font-heading font-black uppercase mb-6">Dashboard</h1>
          <input
            type="password"
            placeholder="API key de admin"
            value={inputKey}
            onChange={e => setInputKey(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && load(inputKey)}
            className="w-full border-2 border-black px-3 py-2 font-mono text-sm mb-4 outline-none focus:border-yellow-400"
          />
          {error && <p className="text-red-600 font-mono text-xs mb-3">{error}</p>}
          <button
            onClick={() => load(inputKey)}
            disabled={!inputKey || loading}
            className="w-full py-3 bg-black text-white font-mono font-bold uppercase tracking-widest text-sm hover:bg-yellow-300 hover:text-black transition-colors disabled:opacity-50"
          >
            {loading ? 'Cargando...' : 'Entrar →'}
          </button>
        </div>
      </div>
    )
  }

  if (loading && !data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="font-mono text-sm animate-pulse">Cargando métricas...</p>
      </div>
    )
  }

  const d = data!

  const maxBar = Math.max(...d.eventos.por_dia.map(x => x.nuevos), 1)

  return (
    <>
      <Helmet><title>Admin Dashboard — Cultura ETÉREA</title></Helmet>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 border-b-2 border-black pb-4">
          <div>
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.3em] text-neutral-500">Cultura ETÉREA</p>
            <h1 className="text-2xl font-heading font-black uppercase">Admin Dashboard</h1>
          </div>
          <div className="flex items-center gap-3">
            <p className="text-[9px] font-mono text-neutral-400">
              {new Date(d.generado_en).toLocaleString('es-CO', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' })}
            </p>
            <button
              onClick={() => load(apiKey)}
              className="px-3 py-1.5 border-2 border-black font-mono text-[10px] font-bold uppercase hover:bg-black hover:text-white transition-colors"
            >
              Actualizar
            </button>
            <button
              onClick={() => { sessionStorage.removeItem(KEY_STORAGE); setApiKey(''); setData(null) }}
              className="px-3 py-1.5 border border-black/30 font-mono text-[10px] uppercase text-neutral-500 hover:border-black hover:text-black transition-colors"
            >
              Salir
            </button>
          </div>
        </div>

        {/* Acciones */}
        <section className="mb-8 border-2 border-black p-5">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-4">Acciones rápidas</p>
          <div className="flex flex-wrap gap-3">
            <ActionBtn
              label="▶ Correr Scraper"
              variant="yellow"
              loading={actionLoading === 'scraper'}
              onClick={() => runAction('scraper', () => adminTriggerScraper(apiKey))}
            />
            <ActionBtn
              label="📧 Enviar Blast Tick"
              loading={actionLoading === 'blast'}
              onClick={() => runAction('blast', () => adminTriggerBlastTick(apiKey))}
            />
            <ActionBtn
              label="🧹 Limpiar Eventos Pasados"
              loading={actionLoading === 'cleanup'}
              onClick={() => runAction('cleanup', () => adminTriggerCleanup(apiKey))}
            />
          </div>
          {actionMsg && (
            <p className={`mt-3 font-mono text-xs ${actionMsg.startsWith('✓') ? 'text-green-700' : 'text-red-600'}`}>
              {actionMsg}
            </p>
          )}
        </section>

        {/* Stats grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
          <Stat label="Eventos totales" value={d.eventos.total.toLocaleString()} />
          <Stat label="Eventos hoy" value={d.eventos.hoy} />
          <Stat label="Próxima semana" value={d.eventos.proxima_semana} />
          <Stat label="Nuevos (7 días)" value={d.eventos.nuevos_7d} />
          <Stat label="Espacios activos" value={d.espacios.activos} sub={`${d.espacios.total} total`} />
          <Stat label="Colectivos" value={d.espacios.colectivos} />
          <Stat label="Con Instagram" value={d.espacios.con_instagram} />
          <Stat label="Usuarios registrados" value={d.usuarios.auth_registrados} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Eventos por día (últimos 7) */}
          <div className="border-2 border-black p-5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-4">Eventos nuevos — últimos 7 días</p>
            <div className="flex items-end gap-2 h-28">
              {d.eventos.por_dia.map(({ fecha, nuevos }) => (
                <div key={fecha} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[9px] font-mono font-black">{nuevos || ''}</span>
                  <div
                    className="w-full bg-black"
                    style={{ height: `${Math.max((nuevos / maxBar) * 80, nuevos > 0 ? 4 : 0)}px` }}
                  />
                  <span className="text-[8px] font-mono text-neutral-400">{fecha}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Top categorías */}
          <div className="border-2 border-black p-5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-4">Top categorías (próxima semana)</p>
            <div className="space-y-2">
              {d.eventos.top_categorias.length === 0 && (
                <p className="font-mono text-xs text-neutral-400">Sin datos</p>
              )}
              {d.eventos.top_categorias.map(({ cat, n }) => {
                const pct = Math.round((n / (d.eventos.proxima_semana || 1)) * 100)
                return (
                  <div key={cat} className="flex items-center gap-2">
                    <span className="text-[10px] font-mono w-28 shrink-0">{CAT_LABEL[cat] ?? cat}</span>
                    <div className="flex-1 bg-neutral-100 h-3">
                      <div className="h-3 bg-black" style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-[10px] font-mono font-black w-6 text-right">{n}</span>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Email blast */}
          <div className="border-2 border-black p-5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-4">Email blast</p>
            <div className="space-y-3">
              <div className="flex justify-between items-center border-b border-black/10 pb-2">
                <span className="font-mono text-xs text-neutral-500">Campaña</span>
                <span className="font-mono text-xs font-black">{d.email.blast_key}</span>
              </div>
              <div className="flex justify-between items-center border-b border-black/10 pb-2">
                <span className="font-mono text-xs text-neutral-500">Cursor</span>
                <span className="font-mono text-xs font-black">{d.email.blast_cursor} / {d.email.destinatarios_estimados}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="font-mono text-xs text-neutral-500">Destinatarios</span>
                <span className="font-mono text-xs font-black">~{d.email.destinatarios_estimados}</span>
              </div>
              {d.email.destinatarios_estimados > 0 && (
                <div className="mt-2">
                  <div className="w-full bg-neutral-100 h-2">
                    <div
                      className="h-2 bg-black"
                      style={{ width: `${Math.min((d.email.blast_cursor / d.email.destinatarios_estimados) * 100, 100)}%` }}
                    />
                  </div>
                  <p className="text-[9px] font-mono text-neutral-400 mt-1">
                    {Math.round((d.email.blast_cursor / d.email.destinatarios_estimados) * 100)}% completado
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Scrapers */}
          <div className="border-2 border-black p-5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-4">Scrapers (7 días)</p>
            <div className="space-y-2 mb-4">
              <div className="flex justify-between">
                <span className="font-mono text-xs text-neutral-500">Runs</span>
                <span className="font-mono text-xs font-black">{d.scrapers.runs_7d}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-mono text-xs text-neutral-500">Eventos nuevos</span>
                <span className="font-mono text-xs font-black">{d.scrapers.nuevos_eventos_7d}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-mono text-xs text-neutral-500">Fuentes activas</span>
                <span className="font-mono text-xs font-black">{d.scrapers.fuentes_activas}</span>
              </div>
            </div>
            <p className="text-[9px] font-mono font-bold uppercase tracking-[0.1em] text-neutral-400 mb-2">Últimos runs</p>
            <div className="space-y-1 max-h-28 overflow-y-auto">
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

        {/* Interacciones + Top espacios */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Clicks por tipo */}
          <div className="border-2 border-black p-5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-1">Interacciones (7 días)</p>
            <p className="text-2xl font-heading font-black mb-4">{(d.interacciones?.total_7d ?? 0).toLocaleString()}</p>
            <div className="space-y-2">
              {Object.entries(d.interacciones?.por_tipo ?? {})
                .sort((a, b) => b[1] - a[1])
                .map(([tipo, n]) => {
                  const total = d.interacciones?.total_7d || 1
                  return (
                    <div key={tipo} className="flex items-center gap-2">
                      <span className="text-[10px] font-mono w-28 shrink-0 capitalize">{tipo.replace(/_/g, ' ')}</span>
                      <div className="flex-1 bg-neutral-100 h-3">
                        <div className="h-3 bg-yellow-300 border-r border-black/20" style={{ width: `${Math.round((n / total) * 100)}%` }} />
                      </div>
                      <span className="text-[10px] font-mono font-black w-8 text-right">{n}</span>
                    </div>
                  )
                })}
              {Object.keys(d.interacciones?.por_tipo ?? {}).length === 0 && (
                <p className="font-mono text-xs text-neutral-400">Sin datos de interacciones</p>
              )}
            </div>
          </div>

          {/* Top espacios más vistos */}
          <div className="border-2 border-black p-5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-4">Top espacios más visitados (7d)</p>
            <div className="space-y-2">
              {(d.interacciones?.top_espacios ?? []).length === 0 && (
                <p className="font-mono text-xs text-neutral-400">Sin datos todavía</p>
              )}
              {(d.interacciones?.top_espacios ?? []).map((e, i) => (
                <div key={e.slug} className="flex items-center gap-3 border-b border-black/5 pb-2">
                  <span className="text-[10px] font-mono font-black text-neutral-300 w-4">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-xs font-bold truncate">{e.nombre}</p>
                    <p className="font-mono text-[9px] text-neutral-400">{e.barrio} · {e.categoria?.replace(/_/g, ' ')}</p>
                  </div>
                  <span className="font-mono text-xs font-black shrink-0">{e.clicks} clicks</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Registros de usuarios por día */}
        <div className="border-2 border-black p-5 mb-8">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-4">
            Nuevos usuarios — últimos 7 días
            <span className="ml-3 text-neutral-400 font-normal normal-case">
              {d.usuarios.auth_registrados} total registrados
            </span>
          </p>
          <div className="flex items-end gap-2 h-20">
            {(d.usuarios.registros_por_dia ?? []).map(({ fecha, nuevos }) => {
              const maxU = Math.max(...(d.usuarios.registros_por_dia ?? []).map(x => x.nuevos), 1)
              return (
                <div key={fecha} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-[9px] font-mono font-black">{nuevos || ''}</span>
                  <div className="w-full bg-yellow-300" style={{ height: `${Math.max((nuevos / maxU) * 56, nuevos > 0 ? 4 : 0)}px` }} />
                  <span className="text-[8px] font-mono text-neutral-400">{fecha}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Calidad datos */}
        <div className="border-2 border-black p-5">
          <p className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] mb-4">Calidad de datos</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: 'Con imagen', value: d.eventos.con_imagen, total: d.eventos.total },
              { label: 'Verificados', value: d.eventos.verificados, total: d.eventos.total },
              { label: 'Colectivos con IG', value: d.espacios.con_instagram, total: d.espacios.total },
              { label: 'Espacios activos', value: d.espacios.activos, total: d.espacios.total },
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
    </>
  )
}
