import { Helmet } from 'react-helmet-async'

export default function ProteccionDatos() {
  return (
    <>
      <Helmet>
        <title>Ley de Protección de Datos - Cultura ETÉREA</title>
      </Helmet>

      <div className="max-w-3xl mx-auto px-4 py-12">
        <h1 className="text-3xl sm:text-4xl font-mono font-bold mb-4 uppercase">
          Ley de Protección de Datos
        </h1>
        <p className="font-mono text-sm mb-8">
          Cultura ETÉREA trata datos personales con fines culturales y comunitarios.
          Esta política resume cómo usamos la información y qué no hacemos.
        </p>

        <div className="space-y-6">
          <section className="border-2 border-black p-5">
            <h2 className="font-mono font-bold uppercase text-sm mb-2">Finalidad del sistema</h2>
            <p className="font-mono text-sm">
              Esta plataforma existe para apoyar la circulación de la agenda cultural del Valle de Aburrá.
              El uso de datos se limita a descubrir, organizar y mostrar eventos y espacios culturales.
            </p>
          </section>

          <section className="border-2 border-black p-5">
            <h2 className="font-mono font-bold uppercase text-sm mb-2">No scrapeamos cuentas personales</h2>
            <p className="font-mono text-sm">
              El sistema está orientado a espacios, colectivos y cuentas públicas de carácter cultural.
              No se deben registrar perfiles personales sin vocación pública cultural.
            </p>
          </section>

          <section className="border-2 border-black p-5">
            <h2 className="font-mono font-bold uppercase text-sm mb-2">Datos que tratamos</h2>
            <p className="font-mono text-sm">
              Podemos tratar nombre de espacio/colectivo, enlaces públicos, información de eventos,
              imágenes de difusión cultural y datos de contacto compartidos públicamente para gestión cultural.
            </p>
          </section>

          <section className="border-2 border-black p-5">
            <h2 className="font-mono font-bold uppercase text-sm mb-2">Uso de Meta API</h2>
            <p className="font-mono text-sm">
              Cuando está disponible, priorizamos el token oficial de Meta Graph API para perfiles públicos
              culturales, reduciendo dependencia de scraping web no oficial.
            </p>
          </section>

          <section className="border-2 border-black p-5">
            <h2 className="font-mono font-bold uppercase text-sm mb-2">Consentimiento</h2>
            <p className="font-mono text-sm">
              Al crear cuenta o registrar una URL, el usuario declara que acepta esta política,
              que tiene legitimidad para enviar la información y que su finalidad es cultural.
            </p>
          </section>

          <section className="border-2 border-black p-5">
            <h2 className="font-mono font-bold uppercase text-sm mb-2">Corrección o retiro</h2>
            <p className="font-mono text-sm">
              Si eres titular de datos o representante de un espacio y deseas corrección, actualización
              o retiro de información, puedes solicitarlo por los canales oficiales del proyecto.
            </p>
          </section>

          <section className="border-2 border-black p-5">
            <h2 className="font-mono font-bold uppercase text-sm mb-2">Borrado automático</h2>
            <p className="font-mono text-sm">
              Ejecutamos limpieza automática por retención: solicitudes de registro, logs de scraping y textos OCR
              se eliminan o anonimizan de forma periódica para minimizar persistencia de datos.
            </p>
          </section>

          <section className="border-2 border-black p-5 bg-black text-white">
            <h2 className="font-mono font-bold uppercase text-sm mb-2">Marco de referencia</h2>
            <p className="font-mono text-sm opacity-90">
              Esta política se alinea con principios de protección de datos personales aplicables en Colombia,
              incluyendo autorización, finalidad, necesidad y circulación restringida.
            </p>
          </section>
        </div>
      </div>
    </>
  )
}
