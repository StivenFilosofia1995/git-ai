import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'

const BREB_KEY = '@stiven975'

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

const PASOS_BREB = [
  {
    banco: 'Bancolombia App',
    icono: '🏦',
    pasos: ['Abrí la app de Bancolombia', 'Transferir → Transferencia Bre-B', `Escribí la llave: ${BREB_KEY}`, 'Ingresá el monto y confirmá'],
  },
  {
    banco: 'Nequi',
    icono: '💜',
    pasos: ['Abrí Nequi', 'Transferir → Bre-B', `Llave: ${BREB_KEY}`, 'Confirmá el envío'],
  },
  {
    banco: 'Otros bancos',
    icono: '🏧',
    pasos: ['PSE, Davivienda, BBVA, Itaú...', 'Buscar "Transferencia Bre-B" o "Pago a llave"', `Llave destino: ${BREB_KEY}`, 'Cualquier monto suma'],
  },
]

export default function Aportes() {
  return (
    <>
      <Helmet>
        <title>Apoyá Cultura ETÉREA — Bre-B Bancolombia</title>
        <meta
          name="description"
          content="Cultura ETÉREA es la plataforma cultural gratuita del Valle de Aburrá. Apoyanos con Bre-B desde cualquier banco colombiano usando la llave @stiven975."
        />
      </Helmet>

      {/* HERO */}
      <section className="relative border-b-2 border-black bg-yellow-300 overflow-hidden">
        <img
          src="/medellin-ilustracion.png"
          alt=""
          aria-hidden="true"
          className="absolute inset-0 w-[200%] sm:w-full h-full object-contain sm:object-cover object-center pointer-events-none select-none opacity-[0.25] mix-blend-multiply sm:opacity-30 left-1/2 -translate-x-1/2"
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'linear-gradient(to right, rgba(253,224,71,0.97) 38%, rgba(253,224,71,0.74) 58%, rgba(253,224,71,0.2) 80%)' }}
          aria-hidden="true"
        />
        <div className="relative z-10 max-w-4xl mx-auto px-6 py-16 text-center">
          <p className="relative text-[11px] font-mono font-bold uppercase tracking-[0.3em] mb-4">
            Cultura ETÉREA · Aportes
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
              href="#como-aportar"
              className="inline-flex items-center justify-center gap-2 px-8 py-4 bg-black text-yellow-300 font-mono font-bold text-sm uppercase tracking-widest hover:bg-white hover:text-black border-2 border-black transition-all duration-200"
            >
              ♥ Ver cómo aportar
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

      {/* BRE-B PANEL */}
      <section id="como-aportar" className="border-b-2 border-black bg-[#003087]">
        <div className="max-w-4xl mx-auto px-6 py-12">
          <div className="flex flex-col md:flex-row items-start gap-8">
            <div className="shrink-0 text-center md:text-left">
              <div className="inline-flex items-center justify-center w-20 h-20 bg-white rounded-none mb-3">
                <span className="text-4xl font-heading font-black text-[#003087]">B·B</span>
              </div>
              <p className="text-white/70 font-mono text-[10px] uppercase tracking-[0.2em] block">Bre-B · Bancolombia</p>
            </div>
            <div className="text-white flex-1">
              <h2 className="text-2xl md:text-3xl font-heading font-black uppercase tracking-tight mb-3">
                Consignanos desde cualquier banco
              </h2>
              <p className="font-mono text-sm leading-relaxed text-white/90 mb-5">
                Bre-B es la red de pagos interoperables de Bancolombia. Podés enviarnos plata
                desde <strong>cualquier banco</strong> de Colombia — Nequi, Davivienda, BBVA, Itaú, Banco de Bogotá...
                sin importar dónde tengás tu cuenta. Rápido, seguro, sin comisiones raras.
              </p>
              {/* Key display */}
              <div className="bg-white text-[#003087] inline-flex items-center gap-3 px-5 py-3 border-2 border-white mb-2">
                <span className="text-[11px] font-mono font-bold uppercase tracking-[0.15em] opacity-60">Llave Bre-B</span>
                <span className="text-xl font-heading font-black">{BREB_KEY}</span>
              </div>
              <p className="text-[10px] font-mono text-white/60 mt-2">
                Red Bre-B · Bancolombia · Colombia
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* PASOS POR BANCO */}
      <section className="border-b-2 border-black bg-white">
        <div className="max-w-4xl mx-auto px-6 py-12">
          <h2 className="text-xl font-heading font-black uppercase tracking-tight mb-8 text-center">
            ¿Cómo consignar según tu banco?
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {PASOS_BREB.map(({ banco, icono, pasos }) => (
              <div key={banco} className="border-2 border-black p-6">
                <div className="text-3xl mb-2">{icono}</div>
                <h3 className="font-heading font-black text-sm uppercase tracking-tight mb-3 text-[#003087]">
                  {banco}
                </h3>
                <ol className="space-y-1.5">
                  {pasos.map((p, i) => (
                    <li key={i} className="flex gap-2 font-mono text-xs leading-relaxed">
                      <span className="shrink-0 font-black text-[#003087]">{i + 1}.</span>
                      <span className={p.startsWith('@') || p.includes(BREB_KEY) ? 'font-black text-[#003087]' : ''}>{p}</span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
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

      {/* CTA FINAL */}
      <section className="max-w-4xl mx-auto px-6 py-16">
        <div className="text-center border-2 border-black p-10 bg-yellow-300">
          <p className="text-[11px] font-mono font-bold uppercase tracking-[0.3em] mb-3">
            Todo aporte importa
          </p>
          <h3 className="text-2xl md:text-3xl font-heading font-black uppercase tracking-tight mb-4">
            Ayudanos a sostener<br />la cultura libre
          </h3>
          <p className="font-mono text-sm max-w-md mx-auto mb-6 leading-relaxed">
            Con tu apoyo seguimos mapeando, documentando y conectando la escena cultural
            del Valle de Aburrá. Gracias por creer en esto.
          </p>
          <div className="inline-flex items-center gap-4 bg-[#003087] text-white px-8 py-4 border-2 border-[#003087]">
            <span className="text-[10px] font-mono uppercase tracking-[0.15em] opacity-70">Llave Bre-B</span>
            <span className="text-2xl font-heading font-black">{BREB_KEY}</span>
          </div>
          <p className="text-[10px] font-mono mt-3 opacity-60">
            Bancolombia · Nequi · Davivienda · BBVA · todos los bancos
          </p>
        </div>
      </section>
    </>
  )
}
