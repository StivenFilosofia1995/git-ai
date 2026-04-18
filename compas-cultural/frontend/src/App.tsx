import { Routes, Route, Outlet, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './lib/AuthContext'
import Header from './components/layout/Header'
import Footer from './components/layout/Footer'
import ChatWidget from './components/chat/ChatWidget'
import Home from './pages/Home'
import Explorar from './pages/Explorar'
import EspacioDetalle from './pages/EspacioDetalle'
import Agenda from './pages/Agenda'
import ZonaDetalle from './pages/ZonaDetalle'
import Chat from './pages/Chat'
import Registrar from './pages/Registrar'
import Login from './pages/Login'
import Colectivos from './pages/Colectivos'
import Mapa from './pages/Mapa'
import EventoDetalle from './pages/EventoDetalle'
import CompletarPerfil from './pages/CompletarPerfil'
import NotFound from './pages/NotFound'

/** Soft guard: logged-in users with incomplete profile get nudged to /completar-perfil */
function ProfileGuard({ children }: Readonly<{ children: React.ReactNode }>) {
  const { user, perfilCompleto, perfilLoading, loading } = useAuth()
  const location = useLocation()

  // Still loading — render nothing to avoid flash
  if (loading || perfilLoading) return <>{children}</>

  // Logged-in user without profile → redirect (except if already on the page)
  if (user && !perfilCompleto && location.pathname !== '/completar-perfil') {
    return <Navigate to="/completar-perfil" replace />
  }

  return <>{children}</>
}

function Layout() {
  return (
    <div className="min-h-screen bg-white">
      <Header />
      <main>
        <ProfileGuard>
          <Outlet />
        </ProfileGuard>
      </main>
      <Footer />
      <ChatWidget />
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="mapa" element={<Mapa />} />
          <Route path="explorar" element={<Explorar />} />
          <Route path="espacio/:slug" element={<EspacioDetalle />} />
          <Route path="evento/:slug" element={<EventoDetalle />} />
          <Route path="agenda" element={<Agenda />} />
          <Route path="registrar" element={<Registrar />} />
          <Route path="colectivos" element={<Colectivos />} />
          <Route path="zona/:slug" element={<ZonaDetalle />} />
          {/* Login deshabilitado en producción por seguridad */}
          {/* <Route path="login" element={<Login />} /> */}
          {/* <Route path="completar-perfil" element={<CompletarPerfil />} /> */}
        </Route>
        <Route path="/chat" element={<Chat />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AuthProvider>
  )
}

export default App