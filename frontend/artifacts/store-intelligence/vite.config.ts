import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const rawPort = process.env.PORT ?? '5173'
const port = Number(rawPort)
if (Number.isNaN(port) || port <= 0) throw new Error(`Invalid PORT: "${rawPort}"`)

const basePath = process.env.BASE_PATH ?? '/'

export default defineConfig({
  base: basePath,
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, 'src') },
    dedupe: ['react', 'react-dom'],
  },
  root: path.resolve(import.meta.dirname),
  build: {
    outDir: path.resolve(import.meta.dirname, 'dist/public'),
    emptyOutDir: true,
  },
  server: {
    port,
    strictPort: true,
    host: '0.0.0.0',
    allowedHosts: true,
    proxy: {
      '/api':         { target: 'http://127.0.0.1:8000', changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') },
      '/streams':     { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/live':        { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/stores':      { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/shelf-zones': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health':      { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws':          { target: 'ws://127.0.0.1:8000',   ws: true },
    },
  },
  preview: {
    port,
    host: '0.0.0.0',
    allowedHosts: true,
  },
})
