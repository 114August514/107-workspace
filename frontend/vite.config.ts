import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  ssr: {
    noExternal: ['@primer/react'],
  },
  server: {
    port: 5174,
    // 开发时把 /api 转发到后端，避免前端代码里出现硬编码地址。
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'node',
    // jsdom plus isolated Primer/Ant Design modules is memory-heavy on many-core workstations.
    maxWorkers: 4,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
  },
})
