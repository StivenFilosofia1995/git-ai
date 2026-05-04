const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'
import { supabase } from './supabase'

export interface Coordenadas {
  lat: number
  lng: number
}

export interface Espacio {
  id: string
  slug: string
  nombre: string
  tipo?: string | null
  categoria_principal: string
  categorias?: string[]
  barrio?: string | null
  direccion?: string | null
  municipio: string
  descripcion_corta?: string | null
  descripcion?: string | null
  instagram_handle?: string | null
  sitio_web?: string | null
  imagen_url?: string | null
  nivel_actividad: string
  es_underground?: boolean | null
  coordenadas?: Coordenadas | null
  lat?: number | null
  lng?: number | null
  es_equipamiento_publico?: boolean | null
  facebook_url?: string | null
}

export interface Evento {
  id: string
  slug: string
  titulo: string
  fecha_inicio: string
  fecha_fin?: string | null
  categoria_principal: string
  categorias?: string[]
  barrio?: string | null
  municipio?: string | null
  nombre_lugar?: string | null
  espacio_id?: string | null
  descripcion?: string | null
  imagen_url?: string | null
  precio?: string | null
  es_gratuito?: boolean
  es_recurrente?: boolean
  fuente?: string | null
  fuente_url?: string | null
  lat?: number | null
  lng?: number | null
  hora_confirmada?: boolean | null
}

export interface Zona {
  id: number
  slug: string
  nombre: string
  descripcion?: string | null
  vocacion?: string | null
  municipio: string
}

export interface ResultadoBusqueda {
  tipo: 'espacio' | 'evento'
  item: Espacio | Evento
  similitud?: number
}

export interface BusquedaResponse {
  resultados: ResultadoBusqueda[]
  total: number
  query: string
}

export interface ChatMessage {
  rol: 'usuario' | 'compas'
  contenido: string
  timestamp?: string
}

export interface ChatResponse {
  respuesta: string
  fuentes: Array<{
    tipo: string
    id: string
    nombre: string
    categoria: string
    barrio?: string | null
    url?: string | null
    instagram?: string | null
    sitio_web?: string | null
    imagen_url?: string | null
  }>
}

/** Race a Supabase (or any) promise against a timeout so blocked networks fail fast */
function withTimeout<T>(promise: PromiseLike<T>, ms = 2500): Promise<T> {
  return Promise.race([
    Promise.resolve(promise),
    new Promise<T>((_, reject) =>
      setTimeout(() => reject(new Error('supabase_timeout')), ms)
    ),
  ])
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Error API (${response.status}): ${text}`)
  }

  return response.json() as Promise<T>
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(`Error API (${response.status}): ${text}`)
  }

  return response.json() as Promise<T>
}

export async function getEspacios(params?: {
  limit?: number
  offset?: number
  municipio?: string
  categoria?: string
  tipo?: string
}): Promise<Espacio[]> {
  try {
    let query = supabase
      .from('lugares')
      .select('*')
      .neq('nivel_actividad', 'cerrado')
      .order('nombre')
      .range(params?.offset ?? 0, (params?.offset ?? 0) + (params?.limit ?? 500) - 1)

    if (params?.municipio) query = query.ilike('municipio', `%${params.municipio}%`)
    if (params?.categoria) query = query.eq('categoria_principal', params.categoria)
    if (params?.tipo) query = query.eq('tipo', params.tipo)

    const { data, error } = await withTimeout(query)
    if (error) throw error
    return (data ?? []) as Espacio[]
  } catch {
    const search = new URLSearchParams()
    if (params?.limit) search.set('limit', String(params.limit))
    if (params?.offset) search.set('offset', String(params.offset))
    if (params?.municipio) search.set('municipio', params.municipio)
    if (params?.categoria) search.set('categoria', params.categoria)
    if (params?.tipo) search.set('tipo', params.tipo)
    const qs = search.toString()
    const path = qs ? `/espacios/?${qs}` : '/espacios/'
    return apiGet<Espacio[]>(path)
  }
}

export async function getEspacio(slugOrId: string): Promise<Espacio> {
  const value = (slugOrId || '').trim()
  if (!value) throw new Error('Espacio no encontrado')
  try {
    const bySlug = await withTimeout(
      supabase.from('lugares').select('*').eq('slug', value).maybeSingle()
    )

    if (bySlug.data) return bySlug.data as Espacio

    const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    if (!UUID_RE.test(value)) {
      throw new Error(bySlug.error?.message || 'Espacio no encontrado')
    }

    const byId = await withTimeout(
      supabase.from('lugares').select('*').eq('id', value).maybeSingle()
    )

    if (byId.data) return byId.data as Espacio

    throw new Error(bySlug.error?.message || byId.error?.message || 'Espacio no encontrado')
  } catch {
    return apiGet<Espacio>(`/espacios/${encodeURIComponent(value)}`)
  }
}

type EventosTemporalFilters = {
  municipio?: string
  barrio?: string
  categoria?: string
  es_gratuito?: boolean
}

function buildTemporalFiltersQS(filters?: EventosTemporalFilters): string {
  const search = new URLSearchParams()
  if (filters?.municipio) search.set('municipio', filters.municipio)
  if (filters?.barrio) search.set('barrio', filters.barrio)
  if (filters?.categoria) search.set('categoria', filters.categoria)
  if (typeof filters?.es_gratuito === 'boolean') search.set('es_gratuito', String(filters.es_gratuito))
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export async function getEventosHoy(filters?: EventosTemporalFilters): Promise<Evento[]> {
  const hoy = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
  const manana = (() => {
    const d = new Date()
    d.setDate(d.getDate() + 1)
    return d.toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
  })()
  const hace2dias = (() => {
    const d = new Date()
    d.setDate(d.getDate() - 2)
    return d.toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
  })()

  // Consulta directa a Supabase — más rápido y no depende de Railway
  let q = supabase
    .from('eventos')
    .select('*')
    .gte('fecha_inicio', hoy)
    .lt('fecha_inicio', manana)
    .order('fecha_inicio')
    .limit(200)
  if (filters?.municipio) q = q.ilike('municipio', `%${filters.municipio}%`)
  if (filters?.categoria) q = q.eq('categoria_principal', filters.categoria)
  if (typeof filters?.es_gratuito === 'boolean') q = q.eq('es_gratuito', filters.es_gratuito)
  const { data: dataHoy, error: errorHoy } = await q
  if (errorHoy) throw errorHoy
  const eventosHoy = (dataHoy ?? []) as Evento[]

  // Eventos multi-día en curso: empezaron en los últimos 2 días y terminan hoy o después
  let q2 = supabase
    .from('eventos')
    .select('*')
    .gte('fecha_inicio', hace2dias)
    .lt('fecha_inicio', hoy)
    .gte('fecha_fin', hoy)
    .order('fecha_inicio')
    .limit(50)
  if (filters?.municipio) q2 = q2.ilike('municipio', `%${filters.municipio}%`)
  if (filters?.categoria) q2 = q2.eq('categoria_principal', filters.categoria)
  if (typeof filters?.es_gratuito === 'boolean') q2 = q2.eq('es_gratuito', filters.es_gratuito)
  const { data: dataEnCurso } = await q2
  const seenIds = new Set(eventosHoy.map(e => e.id))
  for (const ev of (dataEnCurso ?? []) as Evento[]) {
    if (!seenIds.has(ev.id)) eventosHoy.push(ev)
  }
  return eventosHoy
}

export async function getEventosFeed(limit = 20): Promise<Evento[]> {
  return apiGet<Evento[]>(`/eventos/feed?limit=${limit}`)
}

export async function getEventosSemana(filters?: EventosTemporalFilters): Promise<Evento[]> {
  // Usa endpoint backend que cubre hasta el domingo de la próxima semana
  // (7-14 días). Antes usaba Supabase directo con ventana fija de 7 días,
  // lo que dejaba fuera vie-sáb-dom al consultar miércoles-jueves.
  const qs = buildTemporalFiltersQS(filters)
  return apiGet<Evento[]>(`/eventos/semana${qs}`)
}

export async function getEventosProximasSemanas(
  dias = 21,
  filters?: EventosTemporalFilters,
  desdeDias = 1,
): Promise<Evento[]> {
  const search = new URLSearchParams()
  search.set('dias', String(dias))
  search.set('desde_dias', String(desdeDias))
  if (filters?.municipio) search.set('municipio', filters.municipio)
  if (filters?.barrio) search.set('barrio', filters.barrio)
  if (filters?.categoria) search.set('categoria', filters.categoria)
  if (typeof filters?.es_gratuito === 'boolean') search.set('es_gratuito', String(filters.es_gratuito))
  return apiGet<Evento[]>(`/eventos/proximas-semanas?${search.toString()}`)
}

export async function getEventosTodos(params?: {
  categoria?: string
  municipio?: string
  barrio?: string
  es_gratuito?: boolean
  maxRows?: number
}): Promise<Evento[]> {
  // Use backend directly with high limit — it has no date filter
  const search = new URLSearchParams()
  search.set('limit', String(params?.maxRows ?? 5000))
  search.set('offset', '0')
  if (params?.categoria) search.set('categoria', params.categoria)
  if (params?.municipio) search.set('municipio', params.municipio)
  if (params?.barrio) search.set('barrio', params.barrio)
  if (typeof params?.es_gratuito === 'boolean') search.set('es_gratuito', String(params.es_gratuito))
  try {
    return await apiGet<Evento[]>(`/eventos/?${search.toString()}`)
  } catch {
    // Supabase fallback — paginate all
    const pageSize = 500
    const maxRows = Math.max(500, params?.maxRows ?? 5000)
    const all: Evento[] = []
    let offset = 0
    while (all.length < maxRows) {
      const chunk = await getEventos({ limit: pageSize, offset, ...params })
      all.push(...chunk)
      if (chunk.length < pageSize) break
      offset += pageSize
    }
    return all
  }
}

export async function getEvento(slug: string): Promise<Evento> {
  try {
    const { data, error } = await withTimeout(
      supabase.from('eventos').select('*').eq('slug', slug).single()
    )
    if (error) throw error
    return data as Evento
  } catch {
    return apiGet<Evento>(`/eventos/${encodeURIComponent(slug)}`)
  }
}

export async function getEventosByEspacio(espacioId: string): Promise<Evento[]> {
  try {
    const { data, error } = await withTimeout(
      supabase.from('eventos').select('*').eq('espacio_id', espacioId).order('fecha_inicio', { ascending: false })
    )
    if (error) throw error
    return (data ?? []) as Evento[]
  } catch {
    return apiGet<Evento[]>(`/eventos/?espacio_id=${encodeURIComponent(espacioId)}&limit=100`)
  }
}

export async function scrapeLugar(lugarId: string): Promise<{ status: string; message: string }> {
  return apiPost<{ status: string; message: string }>(`/scraper/lugar/${lugarId}/publico`, {})
}

export async function scrapeZona(municipio: string, limit = 10): Promise<{ status: string; message: string; result: Record<string, unknown> }> {
  return apiPost<{ status: string; message: string; result: Record<string, unknown> }>(`/scraper/zona/${encodeURIComponent(municipio)}/publico?limit=${limit}`, {})
}

export interface DiscoverEventosParams {
  municipio?: string
  categoria?: string
  es_gratuito?: boolean
  colectivo_slug?: string
  texto?: string
  max_queries?: number
  max_results_per_query?: number
  days_from?: number
  days_ahead?: number
  strict_categoria?: boolean
  auto_insert?: boolean
}

export interface DescubiertoEvento {
  titulo: string
  slug: string
  fecha_inicio: string
  fecha_fin?: string | null
  categoria_principal: string
  categorias?: string[]
  municipio?: string | null
  barrio?: string | null
  nombre_lugar?: string | null
  descripcion?: string | null
  imagen_url?: string | null
  precio?: string | null
  es_gratuito?: boolean
  fuente_url?: string | null
}

export interface DiscoverEventosResponse {
  status: string
  message: string
  result: {
    nuevos?: number
    duplicados?: number
    encontrados?: number
    candidatos?: DescubiertoEvento[]
    variables?: {
      tipo_evento?: string
      zona?: string
      fecha_actual?: string
      texto_usuario?: string
    }
  }
}

export interface CommitEventosResponse {
  status: string
  message: string
  result: {
    nuevos: number
    duplicados: number
    errores: number
  }
}

export async function discoverEventosAI(params: DiscoverEventosParams): Promise<DiscoverEventosResponse> {
  const search = new URLSearchParams()
  if (params.municipio) search.set('municipio', params.municipio)
  if (params.categoria) search.set('categoria', params.categoria)
  if (typeof params.es_gratuito === 'boolean') search.set('es_gratuito', String(params.es_gratuito))
  if (params.colectivo_slug) search.set('colectivo_slug', params.colectivo_slug)
  if (params.texto) search.set('texto', params.texto)
  if (params.max_queries) search.set('max_queries', String(params.max_queries))
  if (params.max_results_per_query) search.set('max_results_per_query', String(params.max_results_per_query))
  if (typeof params.days_from === 'number') search.set('days_from', String(params.days_from))
  if (typeof params.days_ahead === 'number') search.set('days_ahead', String(params.days_ahead))
  if (typeof params.strict_categoria === 'boolean') search.set('strict_categoria', String(params.strict_categoria))
  const shouldAutoInsert = typeof params.auto_insert === 'boolean' ? params.auto_insert : true
  search.set('auto_insert', String(shouldAutoInsert))

  const qs = search.toString()
  const path = '/scraper/discover-events/publico' + (qs ? `?${qs}` : '')
  return apiPost<DiscoverEventosResponse>(path, {})
}

export async function commitEventosDescubiertos(candidatos: DescubiertoEvento[]): Promise<CommitEventosResponse> {
  return apiPost<CommitEventosResponse>('/scraper/discover-events/publico/commit', { candidatos })
}

export async function getEventos(params?: {
  limit?: number
  offset?: number
  categoria?: string
  municipio?: string
  barrio?: string
  es_gratuito?: boolean
}): Promise<Evento[]> {
  const limit = params?.limit ?? 500
  const offset = params?.offset ?? 0
  try {
    // Supabase primary — all events, exclude rechazado
    let query = supabase
      .from('eventos')
      .select('*')
      .neq('estado_moderacion', 'rechazado')
      .order('fecha_inicio')
      .range(offset, offset + limit - 1)
    if (params?.categoria) query = query.eq('categoria_principal', params.categoria)
    if (params?.municipio) query = query.ilike('municipio', `%${params.municipio}%`)
    if (params?.barrio) query = query.ilike('barrio', `%${params.barrio}%`)
    if (typeof params?.es_gratuito === 'boolean') query = query.eq('es_gratuito', params.es_gratuito)
    const { data, error } = await withTimeout(query)
    if (error) throw error
    return (data ?? []) as Evento[]
  } catch {
    // Fallback to backend REST API
    const search = new URLSearchParams()
    search.set('limit', String(limit))
    search.set('offset', String(offset))
    if (params?.categoria) search.set('categoria', params.categoria)
    if (params?.municipio) search.set('municipio', params.municipio)
    if (params?.barrio) search.set('barrio', params.barrio)
    if (typeof params?.es_gratuito === 'boolean') search.set('es_gratuito', String(params.es_gratuito))
    return apiGet<Evento[]>(`/eventos/?${search.toString()}`)
  }
}

export async function buscar(q: string): Promise<BusquedaResponse> {
  try {
    const term = `%${q}%`
    const bogotaNow = new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString().slice(0, 19)
    const [espaciosRes, eventosRes] = await withTimeout(Promise.all([
      supabase.from('lugares').select('*').neq('nivel_actividad', 'cerrado').or(`nombre.ilike.${term},descripcion_corta.ilike.${term},barrio.ilike.${term},municipio.ilike.${term},categoria_principal.ilike.${term}`).limit(50),
      supabase.from('eventos').select('*').gte('fecha_inicio', bogotaNow).neq('estado_moderacion', 'rechazado').or(`titulo.ilike.${term},descripcion.ilike.${term},nombre_lugar.ilike.${term},municipio.ilike.${term},categoria_principal.ilike.${term},barrio.ilike.${term}`).order('fecha_inicio').limit(50),
    ]))

    const resultados: ResultadoBusqueda[] = [
      ...((espaciosRes.data ?? []) as Espacio[]).map(item => ({ tipo: 'espacio' as const, item })),
      ...((eventosRes.data ?? []) as Evento[]).map(item => ({ tipo: 'evento' as const, item })),
    ]
    return { resultados, total: resultados.length, query: q }
  } catch {
    return apiGet<BusquedaResponse>(`/busqueda/?q=${encodeURIComponent(q)}&limit=50`)
  }
}

export async function getZonas(): Promise<Zona[]> {
  try {
    const { data, error } = await withTimeout(
      supabase.from('zonas_culturales').select('*').order('nombre')
    )
    if (error) throw error
    return (data ?? []) as Zona[]
  } catch {
    return apiGet<Zona[]>('/zonas/')
  }
}

export interface StatsResponse {
  espacios: number
  eventos: number
  zonas: number
  colectivos: number
}

export async function getStats(): Promise<StatsResponse> {
  try {
    // Backend first (cached 5min in Railway) — faster and more reliable than direct Supabase count
    return await apiGet<StatsResponse>('/espacios/stats')
  } catch {
    // Fallback: direct Supabase count queries
    try {
      const [esp, ev, z, col] = await withTimeout(Promise.all([
        supabase.from('lugares').select('id', { count: 'exact', head: true }).neq('nivel_actividad', 'cerrado'),
        supabase.from('eventos').select('id', { count: 'exact', head: true }),
        supabase.from('zonas_culturales').select('id', { count: 'exact', head: true }),
        supabase.from('lugares').select('id', { count: 'exact', head: true }).eq('tipo', 'colectivo'),
      ]), 5000)
      return {
        espacios: esp.count ?? 0,
        eventos: ev.count ?? 0,
        zonas: z.count ?? 0,
        colectivos: col.count ?? 0,
      }
    } catch {
      return { espacios: 0, eventos: 0, zonas: 0, colectivos: 0 }
    }
  }
}

export async function getZona(slug: string): Promise<Zona> {
  try {
    const { data, error } = await withTimeout(
      supabase.from('zonas_culturales').select('*').eq('slug', slug).single()
    )
    if (error) throw error
    return data as Zona
  } catch {
    return apiGet<Zona>(`/zonas/${encodeURIComponent(slug)}`)
  }
}

export async function enviarMensajeChat(mensaje: string, historial: ChatMessage[]): Promise<ChatResponse> {
  return apiPost<ChatResponse>('/chat/', {
    mensaje,
    historial
  })
}

// ---------- Registro por URL ----------

export interface RegistroURLResponse {
  id: number
  url: string
  tipo_url: string
  estado: string
  mensaje?: string | null
  created_at: string
}

export interface RegistroEstadoResponse extends RegistroURLResponse {
  datos_extraidos?: Record<string, unknown> | null
  espacio_id?: string | null
  updated_at: string
}

export interface RegistroManualRequest {
  nombre: string
  municipio?: string
  categoria_principal?: string
  tipo?: string
  barrio?: string
  descripcion_corta?: string
  instagram_handle?: string
  sitio_web?: string
  acepta_politica_datos: boolean
}

export interface RegistroManualResponse {
  ok: boolean
  lugar_id: string
  slug: string
  mensaje: string
}

export async function registrarPorURL(url: string, acepta_politica_datos: boolean): Promise<RegistroURLResponse> {
  return apiPost<RegistroURLResponse>('/registro/', { url, acepta_politica_datos })
}

export async function consultarEstadoRegistro(solicitudId: number): Promise<RegistroEstadoResponse> {
  return apiGet<RegistroEstadoResponse>(`/registro/${solicitudId}`)
}

export async function registrarPerfilManual(data: RegistroManualRequest): Promise<RegistroManualResponse> {
  return apiPost<RegistroManualResponse>('/registro/manual', data)
}

// ---------- Publicar evento (colectivos/público) ----------

export interface PublicarEventoData {
  titulo: string
  fecha_inicio: string // ISO
  fecha_fin?: string
  hora_inicio?: string
  hora_fin?: string
  descripcion?: string
  categoria_principal?: string
  municipio?: string
  barrio?: string
  nombre_lugar?: string
  espacio_id?: string
  precio?: string
  es_gratuito?: boolean
  aforo?: number
  sesion_numero?: number
  imagen_url?: string
  imagen_url_alternativa?: string
  contacto_instagram?: string
  contacto_email?: string
}

export async function publicarEvento(data: PublicarEventoData): Promise<{ ok: boolean; mensaje: string; evento?: Record<string, unknown> }> {
  return apiPost<{ ok: boolean; mensaje: string; evento?: Record<string, unknown> }>('/eventos/publicar', data)
}

// ---------- Perfil de usuario ----------

export interface PerfilUsuario {
  id: string
  user_id: string
  nombre: string
  apellido: string
  email: string
  telefono: string | null
  bio: string | null
  preferencias: string[]
  zona_id: number | null
  municipio: string
  ubicacion_barrio: string | null
  ubicacion_lat: number | null
  ubicacion_lng: number | null
  created_at: string
  updated_at: string
}

export async function crearPerfil(
  data: {
    nombre: string
    apellido: string
    email: string
    preferencias: string[]
    zona_id?: number
    municipio?: string
    telefono?: string
    bio?: string
    ubicacion_barrio?: string
    ubicacion_lat?: number
    ubicacion_lng?: number
  },
  userId: string
): Promise<PerfilUsuario> {
  const response = await fetch(`${API_BASE_URL}/perfil/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userId}`,
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    if (response.status === 409) {
      return obtenerPerfil(userId)
    }
    const text = await response.text()
    throw new Error(`Error API (${response.status}): ${text}`)
  }
  return response.json() as Promise<PerfilUsuario>
}

export async function obtenerPerfil(userId: string): Promise<PerfilUsuario> {
  const response = await fetch(`${API_BASE_URL}/perfil/me`, {
    headers: { 'Authorization': `Bearer ${userId}` },
  })
  if (!response.ok) throw new Error('Perfil no encontrado')
  return response.json() as Promise<PerfilUsuario>
}

export async function actualizarPerfil(
  data: Partial<{ nombre: string; apellido: string; preferencias: string[]; zona_id: number; municipio: string }>,
  userId: string
): Promise<PerfilUsuario> {
  const response = await fetch(`${API_BASE_URL}/perfil/me`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userId}`,
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Error al actualizar perfil')
  return response.json() as Promise<PerfilUsuario>
}

// ─── ML: Tracking de interacciones + Recomendaciones personalizadas ───────────

/**
 * Registra una interacción del usuario para entrenar el modelo de recomendación.
 * Llamar esto desde EventCard (view, click) y desde EventoPage (share).
 *
 * Los pesos implícitos en el backend:
 *   view_evento=3, click=4, share=6, asistir=8
 */
export async function trackInteraccion(
  tipo: 'view_evento' | 'click' | 'share' | 'asistir',
  eventoId: string,
  categoria: string,
  userId: string,
  metadata?: { barrio?: string; municipio?: string }
): Promise<void> {
  try {
    await fetch(`${API_BASE_URL}/perfil/interaccion`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userId}`,
      },
      body: JSON.stringify({ tipo, item_id: eventoId, categoria, metadata }),
    })
  } catch {
    // Fire-and-forget: nunca bloquear la UI por tracking fallido
  }
}

/**
 * Obtiene eventos recomendados para el usuario usando el scoring ML del backend:
 *   f_cat (decaimiento exponencial t½=14d) + f_geo (Haversine) +
 *   f_urgencia (e^(-días/3)) + f_popularidad (log1p clicks 24h) + f_calidad
 */
export async function getRecomendaciones(userId: string, limit = 12): Promise<Evento[]> {
  const response = await fetch(`${API_BASE_URL}/perfil/recomendaciones?limit=${limit}`, {
    headers: { 'Authorization': `Bearer ${userId}` },
  })
  if (!response.ok) return []
  const data = await response.json() as { recomendaciones?: Evento[] } | Evento[]
  if (Array.isArray(data)) return data
  return (data as { recomendaciones?: Evento[] }).recomendaciones ?? []
}

/**
 * Versión extendida de discoverEventosAI que incluye barrio para búsqueda
 * semántica hiper-local (ej: "aranjuez rock" busca colectivos en Aranjuez).
 */
export async function discoverEventosConBarrio(
  params: DiscoverEventosParams & { barrio?: string }
): Promise<DiscoverEventosResponse> {
  const search = new URLSearchParams()
  if (params.municipio) search.set('municipio', params.municipio)
  if (params.categoria) search.set('categoria', params.categoria)
  if (params.barrio) search.set('barrio', params.barrio)
  if (typeof params.es_gratuito === 'boolean') search.set('es_gratuito', String(params.es_gratuito))
  if (params.colectivo_slug) search.set('colectivo_slug', params.colectivo_slug)
  if (params.texto) search.set('texto', params.texto)
  if (params.max_queries) search.set('max_queries', String(params.max_queries))
  if (params.max_results_per_query) search.set('max_results_per_query', String(params.max_results_per_query))
  if (typeof params.days_from === 'number') search.set('days_from', String(params.days_from))
  if (typeof params.days_ahead === 'number') search.set('days_ahead', String(params.days_ahead))
  if (typeof params.strict_categoria === 'boolean') search.set('strict_categoria', String(params.strict_categoria))
  search.set('auto_insert', String(params.auto_insert ?? true))
  const path = '/scraper/discover-events/publico?' + search.toString()
  return apiPost<DiscoverEventosResponse>(path, {})
}

export async function registrarInteraccion(
  data: { tipo: string; item_id: string; categoria?: string },
  userId: string
): Promise<void> {
  await fetch(`${API_BASE_URL}/perfil/interaccion`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userId}`,
    },
    body: JSON.stringify(data),
  }).catch(() => {})
}

export async function registrarBusqueda(
  query: string,
  categorias: string[],
  userId: string
): Promise<void> {
  await fetch(`${API_BASE_URL}/perfil/busqueda`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userId}`,
    },
    body: JSON.stringify({ query, categorias }),
  }).catch(() => {})
}

export async function obtenerRecomendaciones(userId: string, limit = 10): Promise<Evento[]> {
  const response = await fetch(`${API_BASE_URL}/perfil/recomendaciones?limit=${limit}`, {
    headers: { 'Authorization': `Bearer ${userId}` },
  })
  if (!response.ok) return []
  return response.json() as Promise<Evento[]>
}

// ---------- Zonas con cultura ----------

export interface ZonaCulturaHoy {
  eventos: Evento[]
  espacios: Espacio[]
  zona: Zona
}

export async function getZonaCulturaHoy(slug: string): Promise<ZonaCulturaHoy> {
  try {
    const { data: zona, error: zonaErr } = await withTimeout(
      supabase.from('zonas_culturales').select('*').eq('slug', slug).single()
    )
    if (zonaErr || !zona) throw new Error('Zona no encontrada')

    const today = new Date().toISOString().slice(0, 10)
    const in14d = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
    const municipio = (zona.municipio ?? '').trim()

    let eventosQuery = supabase
      .from('eventos')
      .select('*')
      .gte('fecha_inicio', today)
      .lte('fecha_inicio', in14d)
      .neq('estado_moderacion', 'rechazado')
      .order('fecha_inicio')
      .limit(50)

    let espaciosQuery = supabase
      .from('lugares')
      .select('*')
      .neq('nivel_actividad', 'cerrado')
      .limit(100)

    if (municipio) {
      eventosQuery = eventosQuery.ilike('municipio', `%${municipio}%`)
      espaciosQuery = espaciosQuery.ilike('municipio', `%${municipio}%`)
    }

    const [eventosRes, espaciosRes] = await withTimeout(Promise.all([eventosQuery, espaciosQuery]))
    let eventos = (eventosRes.data ?? []) as Evento[]

    if (eventos.length === 0) {
      const fallback = await supabase
        .from('eventos')
        .select('*')
        .gte('fecha_inicio', today)
        .lte('fecha_inicio', in14d)
        .neq('estado_moderacion', 'rechazado')
        .order('fecha_inicio')
        .limit(20)
      eventos = (fallback.data ?? []) as Evento[]
    }

    return {
      zona: zona as Zona,
      eventos,
      espacios: (espaciosRes.data ?? []) as Espacio[],
    }
  } catch {
    return apiGet<ZonaCulturaHoy>(`/zonas/${encodeURIComponent(slug)}/cultura-hoy`)
  }
}

export const CATEGORIAS_CULTURALES = [
  { value: 'teatro', label: 'Teatro' },
  { value: 'musica_en_vivo', label: 'Música en Vivo' },
  { value: 'rock', label: 'Rock / Metal / Punk' },
  { value: 'hip_hop', label: 'Hip-Hop' },
  { value: 'jazz', label: 'Jazz' },
  { value: 'electronica', label: 'Electrónica' },
  { value: 'danza', label: 'Danza' },
  { value: 'galeria', label: 'Galerías' },
  { value: 'arte_contemporaneo', label: 'Arte Contemporáneo' },
  { value: 'libreria', label: 'Librerías' },
  { value: 'poesia', label: 'Poesía' },
  { value: 'cine', label: 'Cine' },
  { value: 'fotografia', label: 'Fotografía' },
  { value: 'festival', label: 'Festivales' },
  { value: 'taller', label: 'Talleres' },
  { value: 'conferencia', label: 'Conferencias' },
  { value: 'filosofia', label: 'Filosofía' },
  { value: 'muralismo', label: 'Muralismo' },
  { value: 'editorial', label: 'Editorial' },
  { value: 'circo', label: 'Circo' },
]

// ---------- Reseñas (Reviews) ----------

export interface Resena {
  id: string
  user_id: string
  user_nombre?: string | null
  tipo: string
  item_id: string
  puntuacion: number
  titulo?: string | null
  comentario: string
  created_at: string
}

export interface ResenaStats {
  promedio: number
  total: number
  distribucion: Record<string, number>
}

export async function getResenas(tipo: string, itemId: string, limit = 20, offset = 0): Promise<Resena[]> {
  const { data, error } = await supabase
    .from('resenas')
    .select('*')
    .eq('tipo', tipo)
    .eq('item_id', itemId)
    .order('created_at', { ascending: false })
    .range(offset, offset + limit - 1)
  if (error) return []
  return (data ?? []) as Resena[]
}

export async function getResenaStats(tipo: string, itemId: string): Promise<ResenaStats> {
  const { data, error } = await supabase
    .from('resenas')
    .select('puntuacion')
    .eq('tipo', tipo)
    .eq('item_id', itemId)
  if (error || !data) return { promedio: 0, total: 0, distribucion: {} }
  const total = data.length
  const promedio = total > 0 ? data.reduce((s, r) => s + r.puntuacion, 0) / total : 0
  const distribucion: Record<string, number> = {}
  data.forEach(r => { distribucion[String(r.puntuacion)] = (distribucion[String(r.puntuacion)] || 0) + 1 })
  return { promedio, total, distribucion }
}

export async function crearResena(
  data: { tipo: string; item_id: string; puntuacion: number; titulo?: string; comentario: string },
  userId: string,
  userNombre?: string
): Promise<Resena> {
  const response = await fetch(`${API_BASE_URL}/resenas/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userId}`,
      ...(userNombre ? { 'X-User-Nombre': userNombre } : {}),
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text)
  }
  return response.json() as Promise<Resena>
}

export async function actualizarResena(
  resenaId: string,
  data: { puntuacion?: number; titulo?: string; comentario?: string },
  userId: string
): Promise<Resena> {
  const response = await fetch(`${API_BASE_URL}/resenas/${resenaId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${userId}`,
    },
    body: JSON.stringify(data),
  })
  if (!response.ok) throw new Error('Error al actualizar reseña')
  return response.json() as Promise<Resena>
}

export async function eliminarResena(resenaId: string, userId: string): Promise<void> {
  await fetch(`${API_BASE_URL}/resenas/${resenaId}`, {
    method: 'DELETE',
    headers: { 'Authorization': `Bearer ${userId}` },
  })
}

// ─────────────────────────────────────────────────────────────
// ML client-side — scoring de urgencia para UI
// ─────────────────────────────────────────────────────────────

/**
 * Score de urgencia de un evento para mostrar badge en UI.
 * urgency = 4 * e^(-días/3)
 * Retorna: 'alta' | 'media' | 'baja' | null
 */
export function getUrgencyLabel(fechaInicio: string): 'alta' | 'media' | 'baja' | null {
  try {
    const now = new Date()
    const ev = new Date(fechaInicio)
    const daysUntil = (ev.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
    if (daysUntil < 0) return null
    const score = 4 * Math.exp(-daysUntil / 3)
    if (score >= 3.0) return 'alta'   // < 1 día
    if (score >= 1.5) return 'media'  // 1-3 días
    if (score >= 0.5) return 'baja'   // 3-7 días
    return null
  } catch {
    return null
  }
}

