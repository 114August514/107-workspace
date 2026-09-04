import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// jsdom + Primer/Ant Design 模块很吃内存，worker 不宜无上限；CI（GitHub 4 vCPU runner）
// 上 4 个 jsdom worker 与主线程互相抢占，会放大单个用例的渲染与查询耗时，是 issue #101
// 三组用例超出 5s 预算的直接诱因。CI 上降到 2 个 worker；本地多大核工作站保持 4 个。
// 前端工程没有 @types/node，这里用 globalThis 探测 CI 环境变量。
const isCI = Boolean(
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.CI,
)

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
    maxWorkers: isCI ? 2 : 4,
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}'],
    deps: {
      optimizer: {
        web: {
          // issue #101：隔离模式下每个 jsdom 测试文件都要重新求值 antd 等重依赖的
          // 数千个 ESM 模块，全量 collect 约 84s，是运行成本大头，也让 worker 长时间
          // 占满 CPU 加剧并发抢占。用 esbuild 预打包成少量 chunk 后 collect 降到约 30s；
          // 文件间模块隔离保持不变。
          // 注意 @ant-design/icons 与 @primer/react 不进 bundle：前者打包后出现组件
          // undefined（Element type is invalid），后者含 Node 无法直接加载的 CSS import，
          // 两者保持按文件求值。
          enabled: true,
          include: [
            'react',
            'react-dom',
            'react-dom/client',
            'react/jsx-runtime',
            'react/jsx-dev-runtime',
            'antd',
            'react-router-dom',
            'dayjs',
            'xlsx',
            'prism-react-renderer',
          ],
        },
      },
    },
  },
})
