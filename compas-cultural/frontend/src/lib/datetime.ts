const CO_TZ = 'America/Bogota'

const HAS_TIMEZONE_RE = /(Z|[+-]\d{2}:\d{2})$/
const LOCAL_ISO_RE = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?)?$/

type DateFormatOptions = Intl.DateTimeFormatOptions

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

export function formatEventDate(value: string | null | undefined, options: DateFormatOptions, fallback = 'Por confirmar'): string {
  const parsed = parseEventDate(value)
  if (!parsed) return fallback

  return new Intl.DateTimeFormat('es-CO', {
    timeZone: CO_TZ,
    ...options,
  }).format(parsed)
}

export function getEventDateParts(value: string | null | undefined) {
  return {
    diaCorto: formatEventDate(value, { weekday: 'short', day: 'numeric', month: 'short' }),
    diaLargo: formatEventDate(value, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }),
    hora: formatEventDate(value, { hour: '2-digit', minute: '2-digit' }),
  }
}