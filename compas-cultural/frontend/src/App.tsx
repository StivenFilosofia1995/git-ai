import { Routes, Route, Outlet } from 'react-router-dom'
import { AuthProvider } from './lib/AuthContext'
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
import NotFound from './pages/NotFound'

function Layout() {
  return (
    <div className="min-h-screen bg-white">
      <Header />
      <main>
        <Outlet />
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
          <Route path="login" element={<Login />} />
        </Route>
        <Route path="/chat" element={<Chat />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AuthProvider>
  )
}

export default App