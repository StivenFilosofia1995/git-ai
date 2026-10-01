import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
import App from './App.tsx'
import { initGA } from './lib/analytics'
import './index.css'

initGA()

// Register Service Worker for PWA (offline + push notifications)
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) { return { error } }
  render() {
    if (this.state.error) {
      // Nunca mostrar el stack al usuario: solo en consola para depurar.
      console.error(this.state.error)
      return <div style={{ padding: 32, fontFamily: 'system-ui, sans-serif', maxWidth: 480, margin: '10vh auto', textAlign: 'center' }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, marginBottom: 8 }}>Algo se rompió</h1>
        <p style={{ marginBottom: 20, opacity: 0.7 }}>Recarga la página para seguir viendo la agenda.</p>
        <button
          onClick={() => window.location.reload()}
          style={{ padding: '12px 20px', background: '#000', color: '#fff', border: '2px solid #000', fontWeight: 700, cursor: 'pointer' }}
        >
          Recargar
        </button>
      </div>
    }
    return this.props.children
  }
}

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('No se encontró el elemento root para montar la aplicación')
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <ErrorBoundary>
      <HelmetProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </HelmetProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)