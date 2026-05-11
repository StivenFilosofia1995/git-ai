import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'

const BRAVE_CREATOR = 'stiven975'
const BRAVE_CREATORS_URL = 'https://creators.brave.com/'
const BRAVE_DOWNLOAD_URL = 'https://brave.com/download/'

const razones = [
  {
    emoji: '🗺️',
    titulo: 'El mapa cultural más completo de Medellín',
    texto:
      'Más de 600 espacios y 400 colectivos culturales mapeados a mano — teatros, galerías, colectivos de hip-hop, jazz, filosofía, danza, circo y mucho más. Sin plata corporativa, sin algoritmos.',
  },
  {
    emoji: '🤖',
    titulo: 'ETÉREA: tu guía cultural con IA',
    texto:
      'Nuestra IA conoce cada zona de Medellín y puede recomendarte espacios, contarte la historia de un barrio o ayudarte a encontrar eventos. Completamente gratuita para la comunidad.',
  },
  {
    emoji: '🏘️',
    titulo: 'Hecho desde y para las comunas',
    texto:
      'No somos una startup con inversión externa. Somos una iniciativa local que cree que la cultura popular del Valle de Aburrá merece ser visible, documentada y celebrada.',
  },
  {
    emoji: '📅',
    titulo: 'Agenda cultural independiente',
    texto:
      'Más de 500 eventos cargados sin cobrar un peso a los organizadores. Queremos que los eventos culturales pequeños tengan la misma visibilidad que los grandes festivales.',
  },
  {
    emoji: '🔓',
    titulo: 'Siempre libre, siempre abierto',
    texto:
      'La plataforma es gratuita, no tiene publicidad y no vende datos. Para mantenerlo así necesitamos el apoyo de personas que crean en la cultura libre.',
  },
  {
    emoji: '💡',
    titulo: 'Sustentabilidad real',
    texto:
      'Los servidores, el dominio, las herramientas de IA y el tiempo de desarrollo tienen costo. Tu aporte, por pequeño que sea, nos ayuda a seguir online y mejorar cada semana.',
  },
]

function BraveLogo({ className = '' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 256 301"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M233.773 80.763l-5.41-14.513-12.32 4.72c-1.027.394-1.928.665-2.748.665-.974 0-1.802-.383-2.558-1.237l-9.22-10.148c-1.3-1.43-2.766-2.156-4.317-2.156-1.234 0-2.517.425-3.816 1.264L128 96.41 62.616 59.358c-1.299-.839-2.582-1.264-3.816-1.264-1.55 0-3.017.726-4.317 2.156l-9.22 10.148c-.756.854-1.584 1.237-2.558 1.237-.82 0-1.72-.271-2.748-.665L27.637 66.25l-5.41 14.513L0 80.773v14.97c0 40.826 14.08 78.477 39.66 106.091l60.3 65.36c7.41 8.032 17.85 12.638 28.04 12.638s20.63-4.606 28.04-12.638l60.3-65.36C242.92 174.22 257 136.569 257 95.742v-14.97l-23.227.001z"
        fill="#FF6000"
      />
      <path
        d="M183.938 141.17l-12.74-48.37c-.755-2.87-3.336-4.865-6.303-4.865h-74.79c-2.967 0-5.548 1.994-6.303 4.865l-12.74 48.37c-.586 2.226.032 4.597 1.626 6.242l53.88 56.03c1.217 1.266 2.879 1.98 4.615 1.98 1.737 0 3.399-.714 4.615-1.98l53.88-56.03c1.594-1.645 2.212-4.016 1.626-6.242l-.366-.001z"
        fill="#fff"
        opacity=".9"
      />
    </svg>
  )
}

export default function Aportes() {
  return (
    <>
      <Helmet>
        <title>Apoyá Cultura ETÉREA — Brave Rewards</title>
        <meta
          name="description"
          content="Cultura ETÉREA es la plataforma cultural gratuita del Valle de Aburrá. Apoyanos con BAT a través de Brave Rewards y ayudanos a seguir mapeando la cultura de Medellín."
        />
      </Helmet>

      {/* HERO */}
      <section className="relative border-b-2 border-black bg-yellow-300 overflow-hidden">
        <img src="/medellin-ilustracion.png" alt="" aria-hidden="true" className="absolute inset-0 w-[200%] sm:w-full h-full object-contain sm:object-cover object-center pointer-events-none select-none opacity-[0.25] mix-blend-multiply sm:opacity-30 left-1/2 -translate-x-1/2" />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'linear-gradient(to right, rgba(253,224,71,0.97) 38%, rgba(253,224,71,0.74) 58%, rgba(253,224,71,0.2) 80%)' }}
          aria-hidden="true"
        />
        <div className="relative z-10 max-w-4xl mx-auto px-6 py-16 text-center">
          <p className="relative text-[11px] font-mono font-bold uppercase tracking-[0.3em] mb-4">
            Cultura ETÉREA · Brave Rewards
          </p>
          <h1 className="text-4xl md:text-6xl font-heading font-black uppercase tracking-tight leading-none mb-6">
            ¿Por qué<br />apoyarnos?
          </h1>
          <p className="text-base font-mono max-w-xl mx-auto leading-relaxed mb-10">
            Somos una plataforma cultural independiente del Valle de Aburrá.
            Sin publicidad, sin dueños corporativos, sin lucro.
            Solo cultura.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href={BRAVE_DOWNLOAD_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-black text-yellow-300 font-mono font-bold text-sm uppercase tracking-widest hover:bg-white hover:text-black border-2 border-black transition-all duration-200"
            >
              <BraveLogo className="w-5 h-5" />
              Descargar Brave y apoyar
            </a>
            <Link
              to="/"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-white text-black font-mono font-bold text-sm uppercase tracking-widest border-2 border-black hover:bg-black hover:text-white transition-all duration-200"
            >
              Explorar la plataforma
            </Link>
          </div>
        </div>
      </section>

      {/* BRAVE REWARDS PANEL */}
      <section className="border-b-2 border-black bg-[#FF6000]">
        <div className="max-w-4xl mx-auto px-6 py-12">
          <div className="flex flex-col md:flex-row items-center gap-8">
            <div className="shrink-0 flex flex-col items-center gap-3">
              <BraveLogo className="w-20 h-20" />
              <p className="text-white font-mono font-black text-[11px] uppercase tracking-[0.2em]">
                Brave Rewards
              </p>
            </div>
            <div className="text-white">
              <h2 className="text-2xl md:text-3xl font-heading font-black uppercase tracking-tight mb-3">
                Apoyanos con BAT — sin bancos, sin comisiones
              </h2>
              <p className="font-mono text-sm leading-relaxed text-white/90 mb-4">
                Brave Rewards es el sistema de propinas digitales del navegador Brave.
                Si ya usás Brave y tenés BAT acumulado por ver anuncios, podés mandarnos una propina directamente
                — anónima, instantánea, sin intermediarios.
              </p>
              <div className="flex flex-wrap gap-3">
                <div className="bg-black/30 px-4 py-2 font-mono text-sm font-bold">
                  Creador: <span className="text-yellow-300">@{BRAVE_CREATOR}</span>
                </div>
                <a
                  href={BRAVE_CREATORS_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="bg-white text-[#FF6000] px-4 py-2 font-mono text-sm font-bold uppercase tracking-widest hover:bg-yellow-300 transition-colors"
                >
                  Ver en Brave Creators →
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* RAZONES */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <h2 className="text-xl font-heading font-black uppercase tracking-tight mb-10 text-center">
          Lo que tu aporte sostiene
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {razones.map((r) => (
            <div
              key={r.titulo}
              className="border-2 border-black p-6 hover:bg-yellow-50 transition-colors duration-150"
            >
              <div className="text-3xl mb-3">{r.emoji}</div>
              <h3 className="font-heading font-black text-base uppercase tracking-tight mb-2">
                {r.titulo}
              </h3>
              <p className="font-mono text-sm leading-relaxed text-black/80">
                {r.texto}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* STATS */}
      <section className="border-t-2 border-b-2 border-black bg-black text-white py-12">
        <div className="max-w-4xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            {[
              { n: '600+', label: 'Espacios mapeados' },
              { n: '400+', label: 'Colectivos registrados' },
              { n: '500+', label: 'Eventos en agenda' },
              { n: '60+', label: 'Zonas y barrios' },
            ].map(({ n, label }) => (
              <div key={label}>
                <p className="text-3xl font-heading font-black text-yellow-300 leading-none">{n}</p>
                <p className="text-[10px] font-mono uppercase tracking-widest mt-1 text-white/70">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <h2 className="text-xl font-heading font-black uppercase tracking-tight mb-8 text-center">
          ¿Cómo funciona Brave Rewards?
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          {[
            {
              paso: '01',
              texto: 'Descargá el navegador Brave (gratuito, basado en Chromium). Activá Brave Rewards en la configuración.',
            },
            {
              paso: '02',
              texto: 'Brave te da BAT (Basic Attention Token) por ver anuncios opcionales. Es plata tuya para repartir.',
            },
            {
              paso: '03',
              texto: `Visitá nuestro sitio con Brave y hacé clic en el ícono BAT — o buscá al creador @${BRAVE_CREATOR} en Brave Creators.`,
            },
          ].map(({ paso, texto }) => (
            <div key={paso} className="border-2 border-black p-6">
              <p className="text-4xl font-heading font-black text-[#FF6000] leading-none mb-3">{paso}</p>
              <p className="font-mono text-sm leading-relaxed">{texto}</p>
            </div>
          ))}
        </div>

        {/* CTA final */}
        <div className="text-center border-2 border-black p-10 bg-yellow-300">
          <p className="text-[11px] font-mono font-bold uppercase tracking-[0.3em] mb-3">
            Todo aporte importa
          </p>
          <h3 className="text-2xl md:text-3xl font-heading font-black uppercase tracking-tight mb-4">
            Ayudanos a sostener<br />la cultura libre
          </h3>
          <p className="font-mono text-sm max-w-md mx-auto mb-8 leading-relaxed">
            Con tu apoyo seguimos mapeando, documentando y conectando la escena cultural
            del Valle de Aburrá. Gracias por creer en esto.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <a
              href={BRAVE_DOWNLOAD_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-8 py-4 bg-black text-yellow-300 font-mono font-bold text-sm uppercase tracking-widest hover:bg-white hover:text-black border-2 border-black transition-all duration-200"
            >
              <BraveLogo className="w-5 h-5" />
              Descargar Brave
            </a>
            <a
              href={BRAVE_CREATORS_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-8 py-4 bg-[#FF6000] text-white font-mono font-bold text-sm uppercase tracking-widest hover:bg-black hover:text-white border-2 border-[#FF6000] hover:border-black transition-all duration-200"
            >
              Ver creador @{BRAVE_CREATOR}
            </a>
          </div>
        </div>
      </section>
    </>
  )
}
