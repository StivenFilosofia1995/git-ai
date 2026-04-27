import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

type SmartImageKind = 'thumb' | 'card' | 'detail'

interface SmartEventImageProps {
  alt: string
  primaryUrl?: string | null
  sourceUrl?: string | null
  kind?: SmartImageKind
  className?: string
  loading?: 'lazy' | 'eager'
  fallbackClassName?: string
  fallback?: ReactNode
}

function normalizeUrl(url: string): string {
  const trimmed = url.trim()
  if (!trimmed) return ''
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  return `https://${trimmed}`
}

function buildProxyUrl(primaryUrl?: string | null, sourceUrl?: string | null, kind: SmartImageKind = 'card'): string | null {
  const base = `${API_BASE_URL}/media/event-image`
  const params = new URLSearchParams()

  const normalizedPrimary = primaryUrl ? normalizeUrl(primaryUrl) : ''
  const normalizedSource = sourceUrl ? normalizeUrl(sourceUrl) : ''

  if (normalizedPrimary) params.set('src', normalizedPrimary)
  if (normalizedSource) params.set('source_url', normalizedSource)
  params.set('kind', kind)

  const query = params.toString()
  return query ? `${base}?${query}` : null
}

function buildScreenshotUrl(sourceUrl?: string | null): string | null {
  if (!sourceUrl) return null
  const normalized = normalizeUrl(sourceUrl)
  if (!normalized) return null
  return `https://image.thum.io/get/width/1200/noanimate/${normalized}`
}

export default function SmartEventImage({
  alt,
  primaryUrl,
  sourceUrl,
  kind = 'card',
  className = '',
  loading = 'lazy',
  fallbackClassName = '',
  fallback,
}: Readonly<SmartEventImageProps>) {
  const candidates = useMemo(() => {
    const proxyUrl = buildProxyUrl(primaryUrl, sourceUrl, kind)
    const normalizedPrimary = primaryUrl ? normalizeUrl(primaryUrl) : ''
    const screenshot = buildScreenshotUrl(sourceUrl)

    return [proxyUrl, normalizedPrimary, screenshot].filter((value): value is string => Boolean(value))
  }, [primaryUrl, sourceUrl, kind])

  const [index, setIndex] = useState(0)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setIndex(0)
    setFailed(false)
  }, [candidates])

  const currentSrc = candidates[index]
  const hasImage = Boolean(currentSrc)

  if (!hasImage || failed) {
    if (fallback) return <>{fallback}</>
    return <div className={fallbackClassName} aria-hidden="true" />
  }

  return (
    <img
      src={currentSrc}
      alt={alt}
      className={className}
      loading={loading}
      decoding="async"
      onError={() => {
        if (index < candidates.length - 1) {
          setIndex(index + 1)
          return
        }
        setFailed(true)
      }}
    />
  )
}
