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
  let query = supabase
    .from('lugares')
    .select('*')
    .neq('nivel_actividad', 'cerrado')
    .order('nombre')
    .range(params?.offset ?? 0, (params?.offset ?? 0) + (params?.limit ?? 500) - 1)

  if (params?.municipio) query = query.ilike('municipio', `%${params.municipio}%`)
  if (params?.categoria) query = query.eq('categoria_principal', params.categoria)
  if (params?.tipo) query = query.eq('tipo', params.tipo)

  const { data, error } = await query
  if (error) throw new Error(error.message)
  return (data ?? []) as Espacio[]
}

export async function getEspacio(slug: string): Promise<Espacio> {
  const { data, error } = await supabase
    .from('lugares')
    .select('*')
    .eq('slug', slug)
    .single()
  if (error) throw new Error(error.message)
  return data as Espacio
}

type EventosTemporalFilters = {
  municipio?: string
  categoria?: string
  es_gratuito?: boolean
}

function buildTemporalFiltersQS(filters?: EventosTemporalFilters): string {
  const search = new URLSearchParams()
  if (filters?.municipio) search.set('municipio', filters.municipio)
  if (filters?.categoria) search.set('categoria', filters.categoria)
  if (typeof filters?.es_gratuito === 'boolean') search.set('es_gratuito', String(filters.es_gratuito))
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export async function getEventosHoy(filters?: EventosTemporalFilters): Promise<Evento[]> {
  const qs = buildTemporalFiltersQS(filters)
  return apiGet<Evento[]>(`/eventos/hoy${qs}`)
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

export async function getEventosProximasSemanas(dias = 21, filters?: EventosTemporalFilters): Promise<Evento[]> {
  const search = new URLSearchParams()
  search.set('dias', String(dias))
  if (filters?.municipio) search.set('municipio', filters.municipio)
  if (filters?.categoria) search.set('categoria', filters.categoria)
  if (typeof filters?.es_gratuito === 'boolean') search.set('es_gratuito', String(filters.es_gratuito))
  return apiGet<Evento[]>(`/eventos/proximas-semanas?${search.toString()}`)
}

export async function getEvento(slug: string): Promise<Evento> {
  const { data, error } = await supabase
    .from('eventos')
    .select('*')
    .eq('slug', slug)
    .single()
  if (error) throw new Error(error.message)
  return data as Evento
}

export async function getEventosByEspacio(espacioId: string): Promise<Evento[]> {
  const { data, error } = await supabase
    .from('eventos')
    .select('*')
    .eq('espacio_id', espacioId)
    .order('fecha_inicio', { ascending: false })
  if (error) throw new Error(error.message)
  return (data ?? []) as Evento[]
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
  es_gratuito?: boolean
}): Promise<Evento[]> {
  const limit = params?.limit ?? 500
  const offset = params?.offset ?? 0
  const search = new URLSearchParams()
  search.set('limit', String(limit))
  search.set('offset', String(offset))
  if (params?.categoria) search.set('categoria', params.categoria)
  if (params?.municipio) search.set('municipio', params.municipio)
  if (typeof params?.es_gratuito === 'boolean') search.set('es_gratuito', String(params.es_gratuito))
  return apiGet<Evento[]>(`/eventos/?${search.toString()}`)
}

export async function buscar(q: string): Promise<BusquedaResponse> {
  const term = `%${q}%`
  const [espaciosRes, eventosRes] = await Promise.all([
    supabase.from('lugares').select('*').or(`nombre.ilike.${term},descripcion_corta.ilike.${term},barrio.ilike.${term},municipio.ilike.${term}`).limit(50),
    supabase.from('eventos').select('*').or(`titulo.ilike.${term},descripcion.ilike.${term},nombre_lugar.ilike.${term},municipio.ilike.${term}`).limit(50),
  ])
  const resultados: ResultadoBusqueda[] = [
    ...((espaciosRes.data ?? []) as Espacio[]).map(item => ({ tipo: 'espacio' as const, item })),
    ...((eventosRes.data ?? []) as Evento[]).map(item => ({ tipo: 'evento' as const, item })),
  ]
  return { resultados, total: resultados.length, query: q }
}

export async function getZonas(): Promise<Zona[]> {
  const { data, error } = await supabase
    .from('zonas_culturales')
    .select('*')
    .order('nombre')
  if (error) throw new Error(error.message)
  return (data ?? []) as Zona[]
}

export interface StatsResponse {
  espacios: number
  eventos: number
  zonas: number
  colectivos: number
}

export async function getStats(): Promise<StatsResponse> {
  const [esp, ev, z, col] = await Promise.all([
    supabase.from('lugares').select('id', { count: 'exact', head: true }),
    supabase.from('eventos').select('id', { count: 'exact', head: true }),
    supabase.from('zonas_culturales').select('id', { count: 'exact', head: true }),
    supabase.from('lugares').select('id', { count: 'exact', head: true }).eq('tipo', 'colectivo'),
  ])
  return {
    espacios: esp.count ?? 0,
    eventos: ev.count ?? 0,
    zonas: z.count ?? 0,
    colectivos: col.count ?? 0,
  }
}

export async function getZona(slug: string): Promise<Zona> {
  const { data, error } = await supabase
    .from('zonas_culturales')
    .select('*')
    .eq('slug', slug)
    .single()
  if (error) throw new Error(error.message)
  return data as Zona
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

export async function registrarPorURL(url: string): Promise<RegistroURLResponse> {
  return apiPost<RegistroURLResponse>('/registro/', { url })
}

export async function consultarEstadoRegistro(solicitudId: number): Promise<RegistroEstadoResponse> {
  return apiGet<RegistroEstadoResponse>(`/registro/${solicitudId}`)
}

// ---------- Publicar evento (colectivos/público) ----------

export interface PublicarEventoData {
  titulo: string
  fecha_inicio: string // ISO
  fecha_fin?: string
  descripcion?: string
  categoria_principal?: string
  municipio?: string
  barrio?: string
  nombre_lugar?: string
  espacio_id?: string
  precio?: string
  es_gratuito?: boolean
  imagen_url?: string
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
  const { data: zona, error: zonaErr } = await supabase
    .from('zonas_culturales')
    .select('*')
    .eq('slug', slug)
    .single()
  if (zonaErr || !zona) throw new Error('Zona no encontrada')

  const today = new Date().toISOString().slice(0, 10)
  const [eventosRes, espaciosRes] = await Promise.all([
    supabase.from('eventos').select('*').eq('municipio', zona.municipio).gte('fecha_inicio', today).order('fecha_inicio').limit(50),
    supabase.from('lugares').select('*').eq('municipio', zona.municipio).neq('nivel_actividad', 'cerrado').limit(100),
  ])
  return {
    zona: zona as Zona,
    eventos: (eventosRes.data ?? []) as Evento[],
    espacios: (espaciosRes.data ?? []) as Espacio[],
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
