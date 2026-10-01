import { Link, useLocation } from 'react-router-dom'

// 5 ítems, ≥48px de alto: lo que el usuario usa a diario. El resto vive en "Más".
const LINKS = [
  { to: '/', label: 'Hoy', icon: '●', match: (p: string) => p === '/' || p.startsWith('/agenda') },
  { to: '/mapa', label: 'Mapa', icon: '◎', match: (p: string) => p.startsWith('/mapa') },
  { to: '/cerca-de-ti', label: 'Cerca', icon: '📍', match: (p: string) => p.startsWith('/cerca-de-ti') },
  { to: '/guardados', label: 'Guardados', icon: '♡', match: (p: string) => p.startsWith('/guardados') },
  { to: '/nosotros', label: 'Más', icon: '☰', match: (p: string) => ['/nosotros', '/colectivos', '/web-search', '/aportes', '/descargar', '/publicar'].some(r => p.startsWith(r)) },
]

export default function MobileNav() {
  const { pathname } = useLocation()

  return (
    <nav
      aria-label="Navegación principal"
      className="md:hidden fixed bottom-0 inset-x-0 bg-white border-t-2 border-black pb-[env(safe-area-inset-bottom)] z-50"
    >
      <div className="grid grid-cols-5">
        {LINKS.map(({ to, label, icon, match }) => {
          const active = match(pathname)
          return (
            <Link
              key={to}
              to={to}
              aria-current={active ? 'page' : undefined}
              className={`min-h-[52px] flex flex-col items-center justify-center gap-0.5 text-[11px] font-bold transition-colors ${active ? 'text-white bg-black' : 'text-black'}`}
            >
              <span className="text-base leading-none" aria-hidden="true">{icon}</span>
              {label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
