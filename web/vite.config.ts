import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// 04 Q6 已定：开发期用 Vite 代理，后端不开 CORS。
// 后端地址可用环境变量 VITE_API_TARGET 覆盖（多实例并行联调时用），默认仍是 8000。
// 用 loadEnv 而不是 process.env：项目没装 @types/node，直接读 process 过不了 tsc。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'VITE_')
  const apiTarget = env.VITE_API_TARGET || 'http://127.0.0.1:8000'

  return {
    plugins: [react()],
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: false },
      },
    },
  }
})
