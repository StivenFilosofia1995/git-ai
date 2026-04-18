const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

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
  const query = new URLSearchParams()
  if (params?.limit !== undefined) query.set('limit', String(params.limit))
  if (params?.offset !== undefined) query.set('offset', String(params.offset))
  if (params?.municipio) query.set('municipio', params.municipio)
  if (params?.categoria) query.set('categoria', params.categoria)
  if (params?.tipo) query.set('tipo', params.tipo)

  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiGet<Espacio[]>(`/espacios/${suffix}`)
}

export async function getEspacio(slug: string): Promise<Espacio> {
  return apiGet<Espacio>(`/espacios/${encodeURIComponent(slug)}`)
}

export async function getEventosHoy(): Promise<Evento[]> {
  return apiGet<Evento[]>('/eventos/hoy')
}

export async function getEventosFeed(limit = 20): Promise<Evento[]> {
  return apiGet<Evento[]>(`/eventos/feed?limit=${limit}`)
}

export async function getEventosSemana(): Promise<Evento[]> {
  return apiGet<Evento[]>('/eventos/semana')
}

export async function getEvento(slug: string): Promise<Evento> {
  return apiGet<Evento>(`/eventos/${encodeURIComponent(slug)}`)
}

export async function getEventosByEspacio(espacioId: string): Promise<Evento[]> {
  return apiGet<Evento[]>(`/eventos/espacio/${espacioId}`)
}

export async function scrapeLugar(lugarId: string): Promise<{ status: string; message: string }> {
  return apiPost<{ status: string; message: string }>(`/scraper/lugar/${lugarId}/publico`, {})
}

export async function scrapeZona(municipio: string, limit = 10): Promise<{ status: string; message: string; result: Record<string, unknown> }> {
  return apiPost<{ status: string; message: string; result: Record<string, unknown> }>(`/scraper/zona/${encodeURIComponent(municipio)}/publico?limit=${limit}`, {})
}

export async function getEventos(params?: {
  limit?: number
  offset?: number
  categoria?: string
}): Promise<Evento[]> {
  const query = new URLSearchParams()
  if (params?.limit !== undefined) query.set('limit', String(params.limit))
  if (params?.offset !== undefined) query.set('offset', String(params.offset))
  if (params?.categoria) query.set('categoria', params.categoria)

  const suffix = query.toString() ? `?${query.toString()}` : ''
  return apiGet<Evento[]>(`/eventos/${suffix}`)
}

export async function buscar(q: string): Promise<BusquedaResponse> {
  const query = new URLSearchParams({ q })
  return apiGet<BusquedaResponse>(`/busqueda/?${query.toString()}`)
}

export async function getZonas(): Promise<Zona[]> {
  return apiGet<Zona[]>('/zonas/')
}

export interface StatsResponse {
  espacios: number
  eventos: number
  zonas: number
}

export async function getStats(): Promise<StatsResponse> {
  return apiGet<StatsResponse>('/health/stats')
}

export async function getZona(slug: string): Promise<Zona> {
  return apiGet<Zona>(`/zonas/${encodeURIComponent(slug)}`)
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
  return apiGet<ZonaCulturaHoy>(`/zonas/${encodeURIComponent(slug)}/cultura-hoy`)
}

export const CATEGORIAS_CULTURALES = [
  { value: 'teatro', label: 'Teatro' },
  { value: 'danza', label: 'Danza' },
  { value: 'musica', label: 'Música' },
  { value: 'artes_visuales', label: 'Artes Visuales' },
  { value: 'literatura', label: 'Literatura' },
  { value: 'cine', label: 'Cine' },
  { value: 'hip_hop', label: 'Hip-Hop' },
  { value: 'jazz', label: 'Jazz' },
  { value: 'electronica', label: 'Electrónica' },
  { value: 'poesia', label: 'Poesía' },
  { value: 'fotografia', label: 'Fotografía' },
  { value: 'muralismo', label: 'Muralismo' },
  { value: 'circo', label: 'Circo' },
  { value: 'gastronomia_cultural', label: 'Gastronomía Cultural' },
  { value: 'editorial', label: 'Editorial' },
  { value: 'freestyle', label: 'Freestyle' },
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
  return apiGet<Resena[]>(`/resenas/${tipo}/${itemId}?limit=${limit}&offset=${offset}`)
}

export async function getResenaStats(tipo: string, itemId: string): Promise<ResenaStats> {
  return apiGet<ResenaStats>(`/resenas/${tipo}/${itemId}/stats`)
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
