/**
 * datetime.ts
 * Fixes 2026-04:
 * - Respeta el campo backend `hora_confirmada` (nuevo).
 * - Trata 19:00:00 exacto con fuente auto_scraper/agenda como legacy no confiable
 *   (durante período transicional, hasta que todos los eventos sean re-scrapeados).
 * - Cuando hora no es confiable, formatEventTime devuelve "Hora por confirmar".
 */
const CO_TZ = 'America/Bogota'

const HAS_TIMEZONE_RE = /(Z|[+-]\d{2}:\d{2})$/
const LOCAL_ISO_RE = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?)?$/

type DateFormatOptions = Intl.DateTimeFormatOptions
type EventDateInput =
  | string
  | null
  | undefined
  | {
      fecha_inicio?: string | null
      fuente?: string | null
      hora_confirmada?: boolean | null
    }

function getInputContext(value: EventDateInput) {
  if (typeof value === 'string' || value == null) {
    return { fecha_inicio: value ?? null, fuente: null, hora_confirmada: null }
  }

  return {
    fecha_inicio: value.fecha_inicio ?? null,
    fuente: value.fuente ?? null,
    hora_confirmada: value.hora_confirmada ?? null,
  }
}

function isValidDate(value: Date): boolean {
  return !Number.isNaN(value.getTime())
}

function parseLocalBogotaIso(value: string): Date | null {
  const match = value.match(LOCAL_ISO_RE)
  if (!match) return null

  const [
    ,
    year,
    month,
    day,
    hour = '00',
    minute = '00',
    second = '00',
    millisecond = '0',
  ] = match

  const utcMillis = Date.UTC(
    Number(year),
    Number(month) - 1,
    Number(day),
    Number(hour) + 5,
    Number(minute),
    Number(second),
    Number(millisecond.padEnd(3, '0')),
  )

  return new Date(utcMillis)
}

export function parseEventDate(value?: string | null): Date | null {
  if (!value) return null

  const trimmed = value.trim()
  if (!trimmed) return null

  if (HAS_TIMEZONE_RE.test(trimmed)) {
    const parsed = new Date(trimmed)
    return isValidDate(parsed) ? parsed : null
  }

  const bogotaLocal = parseLocalBogotaIso(trimmed)
  if (bogotaLocal) return bogotaLocal

  const fallback = new Date(trimmed)
  return isValidDate(fallback) ? fallback : null
}

function getBogotaClockParts(value: Date) {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: CO_TZ,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(value)

  const lookup = Object.fromEntries(parts.map(part => [part.type, part.value]))
  const rawHour = Number(lookup.hour ?? '0')
  const normalizedHour = Number.isFinite(rawHour) ? rawHour % 24 : 0
  return {
    hour: normalizedHour,
    minute: Number(lookup.minute ?? '0'),
    second: Number(lookup.second ?? '0'),
  }
}

function isMidnightMarker(value: string | null | undefined): boolean {
  const parsed = parseEventDate(value)
  if (!parsed) return false
  const { hour, minute, second } = getBogotaClockParts(parsed)
  return hour === 0 && minute === 0 && second === 0
}

/**
 * Una hora es "confiable" (mostrable) SI Y SOLO SI:
 * 1. El backend marca explícitamente hora_confirmada=true, o
 * 2. El backend NO provee el campo (legacy) Y la hora no es 00:00:00 NI
 *    es un default sospechoso (19:00:00 con fuente de scraper).
 */
export function hasReliableEventTime(value: EventDateInput): boolean {
  const context = getInputContext(value)
  const parsed = parseEventDate(context.fecha_inicio)

  if (!parsed) return false

  const { hour, minute, second } = getBogotaClockParts(parsed)

  const isScraperSource = Boolean(
    context.fuente && /google_discovery|auto_scraper|agenda|scraping|generic|parser/i.test(context.fuente),
  )

  // 1. Si el backend marca explícitamente, respetamos (nuevo flujo).
  if (context.hora_confirmada === true) {
    // Defensa extra: algunos navegadores pueden formatear medianoche como 24:00
    // y terminar mostrando 12:00 a. m. para eventos sin hora real.
    if (isMidnightMarker(context.fecha_inicio)) return false

    // Defensa adicional para horas extrañas de madrugada en fuentes de scraping.
    // Evita mostrar 01:00-05:59 cuando suelen ser artefactos de parsing/zona horaria.
    if (isScraperSource && hour >= 1 && hour <= 5) return false

    return true
  }
  if (context.hora_confirmada === false) return false

  // 2. Fallback legacy: analizar por heurística (compatibilidad con datos viejos).
  // 2a. 00:00:00 = "sin hora extraída" (marcador universal).
  if (hour === 0 && minute === 0 && second === 0) {
    return false
  }

  // 2b. 19:00:00 exacto con fuente de scraper = legacy default inventado.
  // Transicional: hasta que el nuevo scraper re-procese todo, ocultamos estas horas.
  if (
    hour === 19 &&
    minute === 0 &&
    second === 0 &&
    isScraperSource
  ) {
    return false
  }

  // 2c. También ocultamos madrugadas sospechosas en fuentes de scraping.
  if (isScraperSource && hour >= 1 && hour <= 5) {
    return false
  }

  return true
}

export function formatEventDate(
  value: string | null | undefined,
  options: DateFormatOptions,
  fallback = 'Por confirmar',
): string {
  const parsed = parseEventDate(value)
  if (!parsed) return fallback

  return new Intl.DateTimeFormat('es-CO', {
    timeZone: CO_TZ,
    ...options,
  }).format(parsed)
}

export function formatEventTime(value: EventDateInput, fallback = 'Hora por confirmar'): string {
  const context = getInputContext(value)
  if (!hasReliableEventTime(value)) return fallback
  return formatEventDate(
    context.fecha_inicio,
    { hour: '2-digit', minute: '2-digit' },
    fallback,
  )
}

export function getEventDateParts(value: EventDateInput) {
  const context = getInputContext(value)
  const horaConfiable = hasReliableEventTime(value)

  return {
    diaCorto: formatEventDate(context.fecha_inicio, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
    }),
    diaLargo: formatEventDate(context.fecha_inicio, {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }),
    hora: horaConfiable
      ? formatEventDate(context.fecha_inicio, { hour: '2-digit', minute: '2-digit' })
      : null,
    horaConfiable,
  }
}
