const GA_ID = import.meta.env.VITE_GA_ID as string | undefined

declare global {
  interface Window {
    dataLayer: unknown[]
    gtag: (...args: unknown[]) => void
  }
}

export function initGA() {
  if (!GA_ID || typeof window === 'undefined') return

  const script = document.createElement('script')
  script.async = true
  script.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`
  document.head.appendChild(script)

  window.dataLayer = window.dataLayer || []
  window.gtag = function gtag() {
    // eslint-disable-next-line prefer-rest-params
    window.dataLayer.push(arguments)
  }
  window.gtag('js', new Date())
  // send_page_view: false — lo enviamos manualmente en cada cambio de ruta
  window.gtag('config', GA_ID, { send_page_view: false })
}

export function trackPageView(path: string, title?: string) {
  if (!GA_ID || typeof window === 'undefined' || !window.gtag) return
  window.gtag('config', GA_ID, { page_path: path, page_title: title })
}

export function trackEvent(name: string, params?: Record<string, unknown>) {
  if (!GA_ID || typeof window === 'undefined' || !window.gtag) return
  window.gtag('event', name, params ?? {})
}
