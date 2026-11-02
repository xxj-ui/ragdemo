import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 04 Q6 已定：开发期用 Vite 代理，后端不开 CORS
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    },
  },
})
