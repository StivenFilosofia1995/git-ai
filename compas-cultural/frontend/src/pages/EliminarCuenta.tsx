import { useState } from 'react'
import { Helmet } from 'react-helmet-async'
import { Link } from 'react-router-dom'
import { supabase } from '../lib/supabase'

export default function EliminarCuenta() {
  const [email, setEmail] = useState('')
  const [motivo, setMotivo] = useState('')
  const [enviado, setEnviado] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      await supabase.from('solicitudes_eliminacion').insert({
        email: email.toLowerCase().trim(),
        motivo: motivo || null,
      })
      setEnviado(true)
    } catch {
      setError('Hubo un error. Escríbenos directamente a autonomycsia@gmail.com')
    } finally { setLoading(false) }
  }

  return (
    <>
      <Helmet>
        <title>Eliminar cuenta — Cultura ETÉREA</title>
      </Helmet>
      <div className="max-w-xl mx-auto px-4 py-12">
        <Link to="/" className="font-mono text-xs uppercase tracking-wider hover:underline mb-8 inline-block">← Volver</Link>

        <h1 className="text-2xl font-mono font-black uppercase mb-2">Eliminar cuenta</h1>
        <p className="font-mono text-sm text-neutral-600 mb-8">
          Puedes solicitar la eliminación de tu cuenta y todos los datos asociados.
          Procesamos la solicitud en un plazo máximo de <strong>30 días hábiles</strong>.
        </p>

        {enviado ? (
          <div className="border-2 border-black p-6">
            <p className="font-mono font-bold text-sm mb-2">✓ Solicitud recibida</p>
            <p className="font-mono text-xs text-neutral-600">
              Hemos recibido tu solicitud para eliminar la cuenta asociada a <strong>{email}</strong>.
              Recibirás confirmación por correo electrónico cuando el proceso esté completo.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5 border-2 border-black p-6">
            <div>
              <label className="font-mono text-xs font-bold uppercase tracking-wider block mb-1">
                Correo electrónico de tu cuenta *
              </label>
              <input
                type="email" required value={email} onChange={e => setEmail(e.target.value)}
                placeholder="tu@email.com"
                className="w-full border-2 border-black px-3 py-2 font-mono text-sm outline-none focus:border-yellow-400"
              />
            </div>
            <div>
              <label className="font-mono text-xs font-bold uppercase tracking-wider block mb-1">
                Motivo (opcional)
              </label>
              <textarea
                value={motivo} onChange={e => setMotivo(e.target.value)} rows={3}
                placeholder="¿Por qué deseas eliminar tu cuenta?"
                className="w-full border-2 border-black px-3 py-2 font-mono text-sm outline-none focus:border-yellow-400 resize-none"
              />
            </div>

            <div className="bg-neutral-50 border border-black/20 p-4 font-mono text-xs text-neutral-600">
              <p className="font-bold mb-2">¿Qué datos se eliminan?</p>
              <ul className="space-y-1 list-disc list-inside">
                <li>Tu perfil y preferencias culturales</li>
                <li>Tu historial de eventos guardados</li>
                <li>Tu dirección de correo electrónico</li>
                <li>Todos los datos de actividad en la plataforma</li>
              </ul>
            </div>

            {error && <p className="font-mono text-xs text-red-600">{error}</p>}

            <button type="submit" disabled={loading || !email}
              className="w-full py-3 bg-black text-white font-mono font-bold uppercase tracking-widest text-sm hover:bg-red-700 transition-colors disabled:opacity-50">
              {loading ? 'Enviando...' : 'Solicitar eliminación de cuenta'}
            </button>
          </form>
        )}

        <p className="font-mono text-xs text-neutral-400 mt-6">
          También puedes escribirnos directamente a{' '}
          <a href="mailto:autonomycsia@gmail.com" className="underline">autonomycsia@gmail.com</a>
        </p>
      </div>
    </>
  )
}
