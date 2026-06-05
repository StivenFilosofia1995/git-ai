const CACHE = 'eterea-v1'
const OFFLINE_URL = '/'

// Install: cache shell
self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll([OFFLINE_URL])).then(() => self.skipWaiting())
  )
})

// Activate: clean old caches
self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  )
})

// Fetch: network first, fallback cache
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return
  if (e.request.url.includes('/api/')) return // Never cache API
  e.respondWith(
    fetch(e.request)
      .then(res => {
        const clone = res.clone()
        caches.open(CACHE).then(c => c.put(e.request, clone))
        return res
      })
      .catch(() => caches.match(e.request).then(r => r || caches.match(OFFLINE_URL)))
  )
})

// Push notifications
self.addEventListener('push', e => {
  const data = e.data?.json() || {}
  const title = data.title || 'Cultura ETÉREA'
  const body = data.body || 'Hay eventos culturales nuevos en Medellín'
  const icon = '/icons/icon-192.png'
  const badge = '/icons/icon-192.png'
  const url = data.url || '/'

  e.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon,
      badge,
      vibrate: [200, 100, 200],
      data: { url },
      actions: [
        { action: 'ver', title: 'Ver eventos' },
        { action: 'cerrar', title: 'Cerrar' },
      ]
    })
  )
})

// Notification click
self.addEventListener('notificationclick', e => {
  e.notification.close()
  if (e.action === 'cerrar') return
  const url = e.notification.data?.url || '/'
  e.waitUntil(
    clients.matchAll({ type: 'window' }).then(cs => {
      const c = cs.find(c => c.url === url)
      if (c) return c.focus()
      return clients.openWindow(url)
    })
  )
})
