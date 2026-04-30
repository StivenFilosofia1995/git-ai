import { useEffect, useState, lazy, Suspense, Component, type ReactNode } from 'react'
import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'
import AgendaFeed from '../components/agenda/AgendaFeed'
import EventosHoySection from '../components/agenda/EventosHoySection'
import RecomendacionesSection from '../components/agenda/RecomendacionesSection'
import HomeChatSection from '../components/chat/HomeChatSection'
import AISearchBar from '../components/search/AISearchBar'
import ColtejerWireframe from '../components/illustrations/ColtejerWireframe'
import ZonaCard from '../components/zones/ZonaCard'
import { getZonas, getStats, getEventos, type Zona } from '../lib/api'

const CulturalMap = lazy(() => import('../components/map/CulturalMap'))

class MapErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  state = { hasError: false }
  static getDerivedStateFromError() { return { hasError: true } }
  render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-[600px] border-2 border-black bg-gray-50 flex items-center justify-center">
          <div className="text-center px-8">
            <div className="text-4xl mb-4">🗺️</div>
            <p className="font-mono text-sm text-gray-600">No se pudo cargar el mapa</p>
            <p className="font-mono text-xs text-gray-400 mt-2">Explorá los espacios desde la sección Explorar</p>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default function Home() {
  const [zonas, setZonas] = useState<Zona[]>([])
  const [stats, setStats] = useState({ espacios: 0, eventos: 0, zonas: 0 })
  const [eventosCount, setEventosCount] = useState(0)

  useEffect(() => {
    getZonas().then(setZonas).catch(() => {})
    // Load stats and fallback eventos count in parallel
    Promise.allSettled([
      getStats().then(setStats),
      getEventos({ limit: 1 }).then(() => {
        // If getEventos works, get a real count via stats fallback
      }),
    ])
    // Also try a direct eventos count for the fallback display
    getEventos({ limit: 500 }).then(evs => setEventosCount(evs.length)).catch(() => {})
  }, [])

  return (
    <>
      <Helmet>
        <title>Cultura ET&Eacute;REA &mdash; Valle de Aburr&aacute;</title>
        <meta name="description" content="Mapa vivo del ecosistema cultural del Valle de Aburr&aacute;" />
      </Helmet>

      {/* HERO */}
      <section className="relative bg-white border-b-2 border-black overflow-hidden">
        {/* Background illustration */}
        <img
          src="/medellin-ilustracion.png"
          alt=""
          aria-hidden="true"
          className="absolute right-0 top-0 h-full w-auto max-w-[55%] object-contain object-right pointer-events-none select-none opacity-[0.18] mix-blend-multiply"
          style={{ imageRendering: 'auto' }}
        />
        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-16 lg:pt-32 lg:pb-24">
          <div className="flex items-start justify-between gap-12">
            <div className="max-w-2xl">
              <div className="flex items-center gap-3 mb-10">
                <span className="block w-3 h-3 bg-black animate-pulse" />
                <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">
                  Medellín · Valle de Aburrá · Live
                </span>
              </div>

              <h1 className="font-heading font-black tracking-tighter leading-[0.9] mb-8">
                <span className="block text-[3.5rem] md:text-[5rem] lg:text-[6.5rem] text-black">Cultura</span>
                <span className="block text-[4rem] md:text-[6rem] lg:text-[8rem] text-black" style={{
                  WebkitTextStroke: '2px black',
                  WebkitTextFillColor: 'transparent',
                }}>ETÉREA</span>
              </h1>

              <p className="text-black max-w-md text-base leading-relaxed mb-10 font-mono">
                Teatro · Jazz · Hip-hop · Galerías ·
                Spoken Word · Arte Underground
                — actualizado en tiempo real.
              </p>

              <AISearchBar />

              <div className="mt-4 flex flex-wrap gap-3">
                <Link
                  to="/cerca-de-ti"
                  className="px-4 py-2 text-[10px] font-mono font-bold uppercase tracking-wider border-2 border-black bg-black text-white hover:bg-neutral-800 transition-all"
                >
                  📍 Cerca de ti
                </Link>
              </div>

              {/* Real-time data counters */}
              <div className="flex gap-8 mt-10">
                {[
                  { n: stats.espacios || zonas.length || 0, label: 'ESPACIOS' },
                  { n: stats.eventos || eventosCount || 0, label: 'EVENTOS' },
                  { n: stats.zonas || zonas.length || 0, label: 'ZONAS' },
                ].map(d => {
                  const displayNum = typeof d.n === 'number' ? d.n.toLocaleString('es-CO') : d.n
                  return (
                    <div key={d.label}>
                      <div className="text-3xl font-heading font-black">{displayNum}</div>
                      <div className="text-[9px] font-mono font-bold tracking-[0.2em] mt-1">{d.label}</div>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Coltejer wireframe — hidden on small screens */}
            <div className="hidden lg:block flex-shrink-0 -mr-8 mt-8">
              <ColtejerWireframe />
            </div>
          </div>
        </div>
      </section>

      {/* MARQUEE */}
      <div className="bg-black text-white py-2.5 overflow-hidden border-b-2 border-black">
        <div className="animate-marquee whitespace-nowrap flex gap-8">
          {Array.from({ length: 2 }, (_, j) => (
            <span key={j} className="flex gap-8">
              {['TEATRO', 'ROCK', 'METAL', 'JAZZ', 'HIP-HOP', 'GALERÍAS', 'DANZA', 'ELECTRÓNICA', 'POESÍA', 'CINE', 'MURALISMO', 'FREESTYLE', 'EDITORIAL', 'CIRCO', 'FOTOGRAFÍA', 'PUNK'].map(cat => (
                <span key={`${j}-${cat}`} className="text-[11px] font-mono font-bold tracking-[0.3em] uppercase flex items-center gap-3">
                  <span className="w-1.5 h-1.5 bg-white" />
                  {cat}
                </span>
              ))}
            </span>
          ))}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6">

        {/* EVENTOS HOY */}
        <EventosHoySection />

        {/* CHAT INLINE — preguntale a ETÉREA desde el home */}
        <HomeChatSection />

        {/* MAPA + AGENDA */}
        <section className="py-20 border-t-2 border-black">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
            <div className="lg:col-span-2">
              <div className="flex items-center gap-3 mb-6">
                <span className="w-4 h-4 bg-black" />
                <h2 className="text-xl font-heading font-black uppercase tracking-wider">Mapa Cultural</h2>
              </div>
              <div className="border-2 border-black overflow-hidden">
                <MapErrorBoundary>
                  <Suspense fallback={
                    <div className="w-full h-[600px] bg-gray-50 flex items-center justify-center">
                      <p className="font-mono text-sm text-gray-400 animate-pulse">Cargando mapa…</p>
                    </div>
                  }>
                    <CulturalMap />
                  </Suspense>
                </MapErrorBoundary>
              </div>
            </div>

            <div>
              <div className="flex items-center gap-3 mb-6">
                <span className="w-4 h-4 bg-black" style={{ clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)' }} />
                <h2 className="text-xl font-heading font-black uppercase tracking-wider">Pr&oacute;ximos</h2>
              </div>
              <AgendaFeed />
              <Link
                to="/agenda"
                className="btn-outline w-full text-center block mt-6 text-xs"
              >
                Ver toda la agenda
              </Link>
            </div>
          </div>
        </section>

        {/* RECOMENDACIONES PERSONALIZADAS */}
        <RecomendacionesSection />

        {/* ZONAS CULTURALES */}
        <section className="py-20 border-t-2 border-black">
          <div className="flex items-end justify-between mb-12">
            <div>
              <h2 className="text-4xl md:text-5xl font-heading font-black uppercase tracking-tighter">Zonas</h2>
              <p className="text-sm font-mono font-bold mt-2 uppercase tracking-wider">Ecosistemas creativos del valle · Cultura en vivo</p>
            </div>
            <span className="text-xs font-mono font-bold uppercase tracking-wider">{zonas.length} zonas</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-0 border-2 border-black stagger">
            {zonas.map((zona, i) => (
              <ZonaCard key={zona.id} zona={zona} index={i} />
            ))}
          </div>
        </section>

        {/* CTA REGISTRO */}
        <section className="py-20 mb-8 border-t-2 border-black">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-0 border-2 border-black">
            {/* Espacio */}
            <div className="bg-black text-white p-10 md:p-14 relative overflow-hidden border-b-2 lg:border-b-0 lg:border-r-2 border-black">
              <div className="absolute top-0 right-0 w-32 h-32 border-2 border-white/10 rounded-full -translate-y-1/2 translate-x-1/2" />
              <div className="relative z-10">
                <h2 className="text-2xl md:text-4xl font-heading font-black uppercase tracking-tighter mb-3 leading-[0.95]">
                  ¿Tenés un espacio cultural?
                </h2>
                <p className="text-white text-sm mb-8 font-mono leading-relaxed opacity-80">
                  Registrá tu centro cultural, galería, teatro o librería pegando tu link de Instagram o web.
                </p>
                <Link
                  to="/registrar"
                  className="inline-flex items-center gap-3 bg-white text-black px-6 py-3 font-heading text-sm font-black uppercase tracking-wider hover:bg-black hover:text-white hover:outline hover:outline-2 hover:outline-white transition-all duration-300"
                >
                  Registrar espacio →
                </Link>
              </div>
            </div>

            {/* Colectivo */}
            <div className="bg-white text-black p-10 md:p-14 relative overflow-hidden">
              <div className="absolute bottom-0 left-0 w-24 h-24 border-2 border-black/10" />
              <div className="relative z-10">
                <h2 className="text-2xl md:text-4xl font-heading font-black uppercase tracking-tighter mb-3 leading-[0.95]">
                  ¿Tenés un colectivo?
                </h2>
                <p className="text-black text-sm mb-8 font-mono leading-relaxed opacity-60">
                  Colectivos de hip-hop, teatro, danza, poesía, filosofía... Registrá tu proyecto y quedá conectado al scraping activo.
                </p>
                <Link
                  to="/registrar"
                  className="inline-flex items-center gap-3 bg-black text-white px-6 py-3 font-heading text-sm font-black uppercase tracking-wider hover:bg-white hover:text-black border-2 border-black transition-all duration-300"
                >
                  Registrar colectivo →
                </Link>
              </div>
            </div>
          </div>
        </section>
      </div>
    </>
  )
}
