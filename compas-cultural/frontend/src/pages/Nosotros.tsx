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
          content="Cultura ETÉREA: mapa vivo del ecosistema cultural del Valle de Aburrá. Construida por Stiven Arteaga — filósofo de la IA y autor de 'Máquinas orgánicas y humanos con engranajes'."
        />
      </Helmet>

      {/* HERO */}
      <section className="relative border-b-2 border-black bg-white overflow-hidden">
        <img
          src="/medellin-ilustracion.png"
          alt=""
          aria-hidden="true"
          className="absolute right-0 bottom-0 h-full w-auto max-w-[85%] sm:max-w-[55%] object-contain object-right-bottom pointer-events-none select-none"
          style={{ opacity: 0.22 }}
        />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'linear-gradient(to right, rgba(255,255,255,0.97) 38%, rgba(255,255,255,0.66) 58%, rgba(255,255,255,0.05) 78%)' }}
          aria-hidden="true"
        />
        <div className="relative z-10 max-w-4xl mx-auto px-6 py-16 lg:py-24">
          <div className="relative flex items-center gap-3 mb-8">
            <span className="w-3 h-3 bg-black" />
            <span className="text-[11px] tracking-[0.3em] uppercase font-mono font-bold">
              Cultura ETÉREA · Manifiesto
            </span>
          </div>
          <h1 className="text-4xl md:text-6xl font-heading font-black tracking-tighter uppercase leading-[0.9] mb-6">
            La cultura<br />
            <span style={{ WebkitTextStroke: '2px black', WebkitTextFillColor: 'transparent' }}>
              no desaparece.<br />La invisibilizan.
            </span>
          </h1>
          <p className="text-sm font-mono leading-relaxed max-w-xl text-black/70 mb-4">
            Cultura ETÉREA es la respuesta tecnológica a esa invisibilidad. Un sistema de escucha
            permanente que mapea el ecosistema cultural del Valle de Aburrá — no desde las instituciones,
            sino desde los colectivos, los espacios independientes, las calles.
          </p>
          <p className="text-sm font-mono leading-relaxed max-w-xl text-black/70 mb-8">
            Construida con inteligencia artificial, scrapers autónomos y código que no duerme.
            Sin publicidad. Sin intermediarios. Sin olvido.
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
              El libro →
            </a>
          </div>
        </div>
      </section>

      {/* BIO */}
      <section className="border-b-2 border-black">
        <div className="max-w-4xl mx-auto px-6 py-14 grid md:grid-cols-2 gap-12 items-start">
          {/* Bloque visual */}
          <div className="border-2 border-black p-8 bg-black text-white flex flex-col justify-between min-h-[320px]">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-[0.3em] mb-6 opacity-60">
                Stiven Arteaga · Creador
              </p>
              <p className="font-heading font-black text-2xl uppercase leading-tight mb-4">
                Filósofo<br />
                de la IA<br />
                <span style={{ WebkitTextStroke: '1px white', WebkitTextFillColor: 'transparent' }}>
                  &amp; Constructor<br />de sistemas
                </span>
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-[10px] font-mono tracking-widest opacity-60">Nodo EAFIT · Medellín</span>
              <span className="text-[10px] font-mono tracking-widest opacity-60">@stivenetereo</span>
            </div>
          </div>

          {/* Texto bio — foco en la app, el libro y la filosofía */}
          <div className="flex flex-col gap-5">
            <p className="font-mono text-sm leading-relaxed text-black/80">
              Cultura ETÉREA no nació en una incubadora ni con inversión semilla.
              Nació de una pregunta filosófica: <strong className="text-black font-bold">
              ¿puede la inteligencia artificial devolverle visibilidad a lo que el mercado decide ignorar?</strong>
            </p>
            <p className="font-mono text-sm leading-relaxed text-black/80">
              Stiven Arteaga — filósofo y constructor técnico de IA en{' '}
              <strong className="font-bold">Nodo EAFIT</strong> — lleva años trabajando
              en el cruce exacto donde los algoritmos dejan de ser neutros y se convierten en
              decisiones políticas. Esta plataforma es su respuesta práctica: código que mapea,
              escucha y preserva el tejido cultural del Valle de Aburrá.
            </p>
            <p className="font-mono text-sm leading-relaxed text-black/80">
              La IA de ETÉREA no reemplaza al gestor cultural ni al artista. Los{' '}
              <strong className="font-bold">amplifica</strong>. Usa scrapers autónomos,
              extracción de datos de Instagram y procesamiento de lenguaje natural para que
              ningún evento quede sin anunciarse, ningún colectivo sin aparecer.
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
            <p className="font-mono text-sm leading-relaxed text-white/80 mb-4">
              Este no es un libro de ciencia ficción. Es filosofía de lo inmediato. Sostiene que ya somos
              el{' '}<strong className="text-white">"Tercer Ente"</strong>: ni máquinas puras ni humanos
              sin extensiones. Somos la fusión — nuestros deseos, memorias y decisiones mediados
              por engranajes digitales que ya no podemos apagar.
            </p>
            <p className="font-mono text-sm leading-relaxed text-white/80 mb-4">
              La pregunta central del libro es la misma que mueve a Cultura ETÉREA:{' '}
              <strong className="text-white">¿qué queda de lo humano cuando el algoritmo
              decide qué existe y qué se olvida?</strong> La respuesta no es apagar la pantalla.
              Es entender la técnica como órgano extenso — apropiarse de ella antes de que
              ella se apropie de nosotros.
            </p>
            <p className="font-mono text-sm leading-relaxed text-white/80 mb-8">
              Cultura ETÉREA es, en cierto modo, la versión ejecutable de ese argumento filosófico:
              código que se niega a dejar que los algoritmos de las redes sociales sean los únicos
              árbitros de qué cultura existe.
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
              titulo: 'IA como pregunta filosófica',
              texto: 'Antes de construir con inteligencia artificial, hay que preguntarse a qué intereses sirve. Cada algoritmo es una decisión ética disfrazada de proceso técnico.',
            },
            {
              icon: '■',
              titulo: 'Cultura como acto político',
              texto: 'Mapear 500 colectivos independientes es negarle al olvido institucional su trabajo silencioso. La visibilidad no es un lujo — es supervivencia cultural.',
            },
            {
              icon: '●',
              titulo: 'El Tercer Ente ya existe',
              texto: 'No somos usuarios de la tecnología. Somos el ensamblaje. La pregunta no es si la IA cambiará lo humano — ya lo hizo. La pregunta es quién controla ese cambio.',
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
