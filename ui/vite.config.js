import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// En desarrollo, /api se redirige a la API de FastAPI (uvicorn en el puerto 8000).
// En producción (Docker), FastAPI sirve el build de dist/ y /api desde el mismo origen.
const apiTarget = process.env.AGENTCS_API_URL ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: { '/api': { target: apiTarget, changeOrigin: true } },
  },
});
