const CO_TZ = 'America/Bogota'

const HAS_TIMEZONE_RE = /(Z|[+-]\d{2}:\d{2})$/
const LOCAL_ISO_RE = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?)?$/

type DateFormatOptions = Intl.DateTimeFormatOptions
type EventDateInput = string | null | undefined | { fecha_inicio?: string | null; fuente?: string | null }

function getInputContext(value: EventDateInput) {
  if (typeof value === 'string' || value == null) {
    return { fecha_inicio: value ?? null, fuente: null }
  }

  return {
    fecha_inicio: value.fecha_inicio ?? null,
    fuente: value.fuente ?? null,
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
  return {
    hour: Number(lookup.hour ?? '0'),
    minute: Number(lookup.minute ?? '0'),
    second: Number(lookup.second ?? '0'),
  }
}

function isAutomatedSource(source?: string | null): boolean {
  const normalized = (source ?? '').toLowerCase()
  return normalized.startsWith('auto_scraper_') || normalized.startsWith('smart_listener_') || normalized === 'sitio_web' || normalized === 'rss'
}

export function hasReliableEventTime(value: EventDateInput): boolean {
  const context = getInputContext(value)
  const parsed = parseEventDate(context.fecha_inicio)
  if (!parsed) return false

  const { hour, minute, second } = getBogotaClockParts(parsed)
  if (hour === 0 && minute === 0 && second === 0) {
    return false
  }

  if (isAutomatedSource(context.fuente) && minute === 0 && second === 0 && hour > 0 && hour < 7) {
    return false
  }

  return true
}

export function formatEventDate(value: string | null | undefined, options: DateFormatOptions, fallback = 'Por confirmar'): string {
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
  return formatEventDate(context.fecha_inicio, { hour: '2-digit', minute: '2-digit' }, fallback)
}

export function getEventDateParts(value: EventDateInput) {
  const context = getInputContext(value)
  const horaConfiable = hasReliableEventTime(value)

  return {
    diaCorto: formatEventDate(context.fecha_inicio, { weekday: 'short', day: 'numeric', month: 'short' }),
    diaLargo: formatEventDate(context.fecha_inicio, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }),
    hora: horaConfiable ? formatEventDate(context.fecha_inicio, { hour: '2-digit', minute: '2-digit' }) : null,
    horaConfiable,
  }
}