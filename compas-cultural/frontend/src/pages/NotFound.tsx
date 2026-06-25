import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'

export default function NotFound() {
  return (
    <>
      <Helmet>
        <title>Página no encontrada — Cultura ETÉREA</title>
      </Helmet>

      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-6xl font-mono font-bold mb-4">404</h1>
          <p className="text-xl font-mono mb-8 uppercase tracking-wider">Página no encontrada</p>
          <Link to="/" className="inline-block border-2 border-black px-8 py-3 font-mono font-bold uppercase tracking-wider hover:bg-black hover:text-white transition-all duration-300">
            VOLVER AL INICIO
          </Link>
        </div>
      </div>
    </>
  )
}