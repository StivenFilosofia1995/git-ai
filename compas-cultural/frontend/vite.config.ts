import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
const isCapacitor = process.env.BUILD_TARGET === 'capacitor'

export default defineConfig({
  plugins: [react()],
  base: isCapacitor ? './' : '/',
  server: {
    port: 5173,
    host: true,
    proxy: {
      // VITE_PROXY_TARGET=https://www.culturaetereamed.com para probar contra producción
      '/api': { target: process.env.VITE_PROXY_TARGET ?? 'http://localhost:8002', changeOrigin: true, secure: true },
    },
  },
  build: {
    assetsDir: 'assets',
  },
})