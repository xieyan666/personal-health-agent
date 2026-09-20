import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// host: true -> listen on 0.0.0.0 so colleagues on the same LAN can open
// http://<本机局域网IP>:5341/ via the /api proxy below.
export default defineConfig({
  plugins: [react()],
  build: { target: 'es2020' },
  server: {
    host: true,
    port: 5341,
    strictPort: true,
    proxy: {
      '/api': {
        // Keep browser requests same-origin; Vite proxies them to the API on 8002.
        target: 'http://127.0.0.1:8002',
        changeOrigin: true,
      },
    },
  },
})
