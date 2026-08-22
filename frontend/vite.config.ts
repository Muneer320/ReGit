import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // REST + WebSocket -> FastAPI backend (single uvicorn worker, per adr-07)
      '/api': {
        target: 'http://localhost:8377',
        changeOrigin: true,
        ws: true, // WS /api/collaborate/:artifact_id upgrades
      },
      '/ws': {
        target: 'ws://localhost:8377',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})
