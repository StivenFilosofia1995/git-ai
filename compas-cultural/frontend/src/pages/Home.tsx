import { useEffect, useState } from 'react'
import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'
import CulturalMap from '../components/map/CulturalMap'
import AgendaFeed from '../components/agenda/AgendaFeed'
import EventosHoySection from '../components/agenda/EventosHoySection'
import RecomendacionesSection from '../components/agenda/RecomendacionesSection'
import HomeChatSection from '../components/chat/HomeChatSection'
import AISearchBar from '../components/search/AISearchBar'
import ZonaCard from '../components/zones/ZonaCard'
import { getZonas, getEspacios, getEventos, type Zona } from '../lib/api'

export default function Home() {
  const [zonas, setZonas] = useState<Zona[]>([])
  const [totalEspacios, setTotalEspacios] = useState(0)
  const [totalEventos, setTotalEventos] = useState(0)

  useEffect(() => {
    getZonas().then(setZonas).catch(() => {})
    getEspacios({ limit: 200 }).then(e => setTotalEspacios(e.length)).catch(() => {})
    getEventos({ limit: 200 }).then(e => setTotalEventos(e.length)).catch(() => {})
  }, [])

  return (
    <>
      <Helmet>
        <title>Cultura ET&Eacute;REA &mdash; Valle de Aburr&aacute;</title>
        <meta name="description" content="Mapa vivo del ecosistema cultural del Valle de Aburr&aacute;" />
      </Helmet>

      {/* HERO */}
      <section className="relative bg-white border-b-2 border-black overflow-hidden">
        {/* Bauhaus geometric accents — contained to right edge */}
        <div className="absolute top-12 right-8 w-24 h-24 border-2 border-black rounded-full hidden lg:block" />
        <div className="absolute bottom-20 right-16 w-12 h-12 bg-black hidden lg:block" style={{ clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)' }} />
        <div className="absolute top-1/2 right-6 w-6 h-6 bg-black hidden lg:block" />

        <div className="relative max-w-7xl mx-auto px-6 pt-24 pb-16 lg:pt-32 lg:pb-24">
          <div className="max-w-2xl">
            {/* Top label */}
            <div className="flex items-center gap-3 mb-10">
              <span className="block w-3 h-3 bg-black animate-pulse" />
              <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">
                Medell&iacute;n &middot; Valle de Aburr&aacute; &middot; Live
              </span>
            </div>

            {/* Title */}
            <h1 className="font-heading font-black tracking-tighter leading-[0.9] mb-8">
              <span className="block text-[3.5rem] md:text-[5rem] lg:text-[6.5rem] text-black">Cultura</span>
              <span className="block text-[4rem] md:text-[6rem] lg:text-[8rem] text-black" style={{
                WebkitTextStroke: '2px black',
                WebkitTextFillColor: 'transparent',
              }}>ET&Eacute;REA</span>
            </h1>

            <p className="text-black max-w-md text-base leading-relaxed mb-10 font-mono">
              Teatro &middot; Jazz &middot; Hip-hop &middot; Galer&iacute;as &middot;
              Spoken Word &middot; Arte Underground
              &mdash; actualizado en tiempo real.
            </p>

            <AISearchBar />

            {/* Data counters */}
            <div className="flex gap-8 mt-10">
              {[
                { n: totalEspacios || 110, label: 'ESPACIOS' },
                { n: totalEventos || 90, label: 'EVENTOS' },
                { n: zonas.length || 15, label: 'ZONAS' },
              ].map(d => (
                <div key={d.label}>
                  <div className="text-3xl font-heading font-black">{d.n}</div>
                  <div className="text-[9px] font-mono font-bold tracking-[0.2em] mt-1">{d.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* MARQUEE */}
      <div className="bg-black text-white py-2.5 overflow-hidden border-b-2 border-black">
        <div className="animate-marquee whitespace-nowrap flex gap-8">
          {Array.from({ length: 2 }, (_, j) => (
            <span key={j} className="flex gap-8">
              {['TEATRO', 'JAZZ', 'HIP-HOP', 'GALER&Iacute;AS', 'DANZA', 'ELECTR&Oacute;NICA', 'POES&Iacute;A', 'CINE', 'MURALISMO', 'FREESTYLE', 'EDITORIAL', 'CIRCO'].map(cat => (
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
                <CulturalMap />
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
          <div className="bg-black text-white p-12 md:p-20 border-2 border-black relative overflow-hidden">
            {/* Bauhaus decorative geometry */}
            <div className="absolute top-0 right-0 w-40 h-40 border-2 border-white/20 rounded-full -translate-y-1/2 translate-x-1/2" />
            <div className="absolute bottom-0 left-12 w-20 h-20 border-2 border-white/10" />

            <div className="relative z-10 max-w-lg">
              <h2 className="text-3xl md:text-5xl font-heading font-black uppercase tracking-tighter mb-4 leading-[0.95]">
                &iquest;Ten&eacute;s un espacio cultural?
              </h2>
              <p className="text-white text-sm mb-10 font-mono leading-relaxed">
                Registr&aacute; tu centro cultural, colectivo o proyecto con solo pegar tu link de Instagram o web.
              </p>
              <Link
                to="/registrar"
                className="inline-flex items-center gap-3 bg-white text-black px-8 py-4 font-heading text-sm font-black uppercase tracking-wider hover:bg-black hover:text-white hover:outline hover:outline-2 hover:outline-white transition-all duration-300"
              >
                Registrar mi espacio
                <span className="text-lg">&rarr;</span>
              </Link>
            </div>
          </div>
        </section>
      </div>
    </>
  )
}
