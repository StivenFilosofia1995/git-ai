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
      '/api': { target: 'http://localhost:8002', changeOrigin: true },
    },
  },
  build: {
    assetsDir: 'assets',
  },
})