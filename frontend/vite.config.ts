import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import { authRequestProxy } from './vite.auth-proxy'

const authMode = process.env.WORKSPACE107_AUTH_MODE ?? 'dev'
const loginStack = authMode === 'ustc'
const backendOrigin = process.env.WORKSPACE107_BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'
const frontendPort = Number(
  process.env.WORKSPACE107_DEV_FRONTEND_PORT ??
    new URL(process.env.WORKSPACE107_PUBLIC_ORIGIN ?? 'http://127.0.0.1:5174').port,
)

export default defineConfig({
  plugins: [react(), loginStack ? authRequestProxy() : null],
  ssr: {
    noExternal: ['@primer/react'],
  },
  server: {
    port: frontendPort || 5174,
    strictPort: true,
    // AUTH_MODE=dev: 直接把 /api 转到后端。ustc 由 vite.auth-proxy 做 auth_request。
    proxy: loginStack
      ? undefined
      : {
          '/api': {
            target: backendOrigin,
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
