import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'

const IG_STIVEN = 'https://www.instagram.com/stivenetereo/'
const LIBRO_EXLIBRIS = 'https://www.exlibris.com.co/maquinas-organicas-y-humanos-con-engranajes'
const LIBRO_EDITORIAL = 'https://aunhumanos.com'

export default function Nosotros() {
  return (
    <>
      <Helmet>
        <title>Nosotros — Cultura ETÉREA</title>
        <meta
          name="description"
          content="Stiven Arteaga — filósofo, constructor técnico de IA y creador de Cultura ETÉREA. Conoce el proyecto y el libro 'Máquinas orgánicas y humanos con engranajes'."
        />
      </Helmet>

      {/* HERO */}
      <section className="border-b-2 border-black bg-white">
        <div className="max-w-4xl mx-auto px-6 py-16 lg:py-24">
          <div className="flex items-center gap-3 mb-8">
            <span className="w-3 h-3 bg-black" />
            <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">
              Cultura ETÉREA · Quiénes somos
            </span>
          </div>
          <h1 className="text-4xl md:text-6xl font-heading font-black tracking-tighter uppercase leading-[0.9] mb-6">
            Hola,<br />
            <span style={{ WebkitTextStroke: '2px black', WebkitTextFillColor: 'transparent' }}>
              soy Stiven.
            </span>
          </h1>
          <p className="text-sm font-mono leading-relaxed max-w-xl text-black/70 mb-8">
            Filósofo · Constructor técnico de IA · Creador de Cultura ETÉREA
          </p>
          <div className="flex flex-wrap gap-4">
            <a
              href={IG_STIVEN}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-black text-white px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider hover:bg-white hover:text-black border-2 border-black transition-all duration-300"
            >
              {"◆ @stivenetereo en IG"}
            </a>
            <a
              href={LIBRO_EXLIBRIS}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-white text-black px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider border-2 border-black hover:bg-black hover:text-white transition-all duration-300"
            >
              Comprar el libro →
            </a>
          </div>
        </div>
      </section>

      {/* BIO */}
      <section className="border-b-2 border-black">
        <div className="max-w-4xl mx-auto px-6 py-14 grid md:grid-cols-2 gap-12 items-start">
          {/* Foto / bloque visual */}
          <div className="border-2 border-black p-8 bg-black text-white flex flex-col justify-between min-h-[320px]">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-[0.3em] mb-6 opacity-60">
                Stiven Arteaga
              </p>
              <p className="font-heading font-black text-2xl uppercase leading-tight mb-4">
                Filósofo<br />
                &amp; Constructor<br />
                Técnico de AI
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-[10px] font-mono tracking-widest opacity-60">Nodo EAFIT · Medellín</span>
              <span className="text-[10px] font-mono tracking-widest opacity-60">@stivenetereo</span>
            </div>
          </div>

          {/* Texto bio */}
          <div className="flex flex-col gap-5">
            <p className="font-mono text-sm leading-relaxed text-black/80">
              Desde hace años, mi obsesión ha sido entender el punto exacto donde dejamos de ser simples
              usuarios de la tecnología para convertirnos en parte de ella. No soy solo un filósofo que
              observa desde la barrera; mi trabajo diario en{' '}
              <strong className="font-bold">Nodo EAFIT</strong>, construyendo soluciones de Inteligencia
              Artificial, me permite ver las entrañas de los algoritmos que hoy nos definen.
            </p>
            <p className="font-mono text-sm leading-relaxed text-black/80">
              Cultura ETÉREA nació de esa misma lógica: usar la técnica como{' '}
              <strong className="font-bold">órgano extenso</strong> para hacer visible el ecosistema
              cultural del Valle de Aburrá. No como observador externo, sino como constructor dentro
              del ensamblaje.
            </p>
            <p className="font-mono text-sm leading-relaxed text-black/80">
              Creo que la IA y la cultura no son opuestos. Son el mismo impulso humano de dar sentido,
              de conectar, de resistir el olvido.
            </p>
            <a
              href={IG_STIVEN}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-[11px] font-mono font-bold uppercase tracking-wider underline underline-offset-4 hover:no-underline transition-all"
            >
              Ver perfil → @stivenetereo
            </a>
          </div>
        </div>
      </section>

      {/* LIBRO */}
      <section className="border-b-2 border-black bg-black text-white">
        <div className="max-w-4xl mx-auto px-6 py-14 grid md:grid-cols-2 gap-12 items-center">
          <div>
            <p className="text-[10px] font-mono uppercase tracking-[0.3em] mb-4 text-white/50">
              Libro · Editorial Aún Humanos
            </p>
            <h2 className="text-3xl md:text-4xl font-heading font-black uppercase leading-tight mb-6">
              Máquinas<br />orgánicas<br />
              <span style={{ WebkitTextStroke: '1px white', WebkitTextFillColor: 'transparent' }}>
                y humanos con<br />engranajes
              </span>
            </h2>
            <p className="font-mono text-sm leading-relaxed text-white/80 mb-8">
              No te hablo de ciencia ficción, sino de nuestra realidad inmediata. Sostengo que ya somos
              el <strong className="text-white">"Tercer Ente"</strong>: una fusión donde nuestros deseos,
              memorias y decisiones están mediados por engranajes digitales. Esta obra es un acto de
              resistencia — una invitación a que detengas un momento la inercia de la pantalla y te
              preguntes qué queda de ti cuando el algoritmo se apaga.
            </p>
            <div className="flex flex-wrap gap-4">
              <a
                href={LIBRO_EXLIBRIS}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 bg-white text-black px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider hover:bg-yellow-300 border-2 border-white transition-all duration-300"
              >
                Comprar en Exlibris →
              </a>
              <a
                href={LIBRO_EDITORIAL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 bg-transparent text-white px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider border-2 border-white hover:bg-white hover:text-black transition-all duration-300"
              >
                Editorial Aún Humanos
              </a>
            </div>
          </div>
          {/* Visual del libro */}
          <div className="border-2 border-white/30 p-8 flex flex-col items-center justify-center min-h-[280px] text-center">
            <div className="w-24 h-32 border-2 border-white/50 flex items-center justify-center mb-6">
              <span className="text-white/30 font-mono text-[9px] uppercase tracking-widest rotate-90 whitespace-nowrap">
                Stiven Arteaga
              </span>
            </div>
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-white/50">
              "La técnica como órgano extenso"
            </p>
          </div>
        </div>
      </section>

      {/* CONTACTO */}
      <section className="border-b-2 border-black bg-white">
        <div className="max-w-4xl mx-auto px-6 py-14 text-center">
          <div className="flex items-center gap-3 justify-center mb-6">
            <span className="w-3 h-3 bg-black" />
            <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">Proyectos · Colaboraciones</span>
            <span className="w-3 h-3 bg-black" />
          </div>
          <h2 className="text-3xl md:text-4xl font-heading font-black uppercase leading-tight mb-6">
            ¿Quieres<br />trabajar conmigo?
          </h2>
          <p className="font-mono text-sm leading-relaxed max-w-lg mx-auto text-black/70 mb-10">
            Si tienes un proyecto donde la filosofía, la IA y la cultura se cruzan — o simplemente
            quieres explorar esta <strong className="text-black font-bold">ontología de la instantaneidad</strong> —
            escríbeme. La conversación más humana sigue siendo directa y personal.
          </p>
          <a
            href={IG_STIVEN}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-3 bg-black text-white px-10 py-4 font-mono text-xs font-bold uppercase tracking-widest hover:bg-white hover:text-black border-2 border-black transition-all duration-300"
          >
            {"◆ Escribirme a Instagram · @stivenetereo"}
          </a>
          <p className="text-[10px] font-mono text-black/40 uppercase tracking-wider mt-4">
            Para proyectos culturales · IA · filosofía · colaboraciones
          </p>
        </div>
      </section>

      {/* MANIFIESTO breve */}
      <section className="bg-white">
        <div className="max-w-4xl mx-auto px-6 py-12 grid md:grid-cols-3 gap-0 border-2 border-black">
          {[
            {
              icon: '◈',
              titulo: 'Tecnología como filosofía',
              texto: 'La IA no es solo una herramienta. Es el espejo más nítido de lo que creemos, valoramos y olvidamos como especie.',
            },
            {
              icon: '■',
              titulo: 'Cultura como resistencia',
              texto: 'Mapear colectivos y espacios culturales es un acto político. Hacerlos visibles es negarle al olvido su trabajo silencioso.',
            },
            {
              icon: '●',
              titulo: 'Lo humano como pregunta',
              texto: 'En la fusión con los engranajes digitales, la pregunta que no debemos dejar de hacernos es: ¿qué queda de nosotros?',
            },
          ].map((item, i) => (
            <div
              key={item.titulo}
              className={`p-8 ${i < 2 ? 'border-b-2 md:border-b-0 md:border-r-2 border-black' : ''}`}
            >
              <span className="text-2xl block mb-4">{item.icon}</span>
              <h3 className="font-heading font-black text-sm uppercase tracking-tight mb-3">
                {item.titulo}
              </h3>
              <p className="font-mono text-xs leading-relaxed text-black/70">
                {item.texto}
              </p>
            </div>
          ))}
        </div>

        {/* CTA final */}
        <div className="max-w-4xl mx-auto px-6 pb-16 pt-10 text-center">
          <div className="flex flex-wrap gap-4 justify-center">
            <Link
              to="/explorar"
              className="inline-flex items-center gap-2 bg-black text-white px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider hover:bg-white hover:text-black border-2 border-black transition-all duration-300"
            >
              Explorar la plataforma →
            </Link>
            <Link
              to="/aportes"
              className="inline-flex items-center gap-2 bg-yellow-300 text-black px-6 py-3 font-mono text-xs font-bold uppercase tracking-wider border-2 border-black hover:bg-yellow-400 transition-all duration-300"
            >
              ♥ Apoyar el proyecto
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}
