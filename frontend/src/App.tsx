import { App as AntdApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { lazy, Suspense, useCallback, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { getCurrentUser, setCurrentUser } from './api/client'
import { AppShell } from './components/layout/AppShell'
import { HomePage } from './pages/HomePage'
import { ProjectPage } from './pages/ProjectPage'
import { RunPage } from './pages/RunPage'
import { VersionDetailPage } from './pages/VersionDetailPage'
import { WorkspacePage } from './pages/WorkspacePage'
import { theme } from './theme'

const USER_KEY = 'workspace107.devUser'
const DesignSystemPage = lazy(() =>
  import('./pages/design-system/DesignSystemPage').then((module) => ({
    default: module.DesignSystemPage,
  })),
)

export function App() {
  return (
    <Routes>
      <Route
        path="/design-system"
        element={
          <Suspense fallback={<div role="status">正在加载交互参考台…</div>}>
            <DesignSystemPage />
          </Suspense>
        }
      />
      <Route path="*" element={<ProductApp />} />
    </Routes>
  )
}

function ProductApp() {
  const [username, setUsername] = useState(() => {
    const saved = window.localStorage.getItem(USER_KEY) ?? getCurrentUser()
    setCurrentUser(saved)
    return saved
  })

  const changeUser = useCallback((next: string) => {
    setCurrentUser(next)
    window.localStorage.setItem(USER_KEY, next)
    setUsername(next)
  }, [])

  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <AntdApp>
        <AppShell username={username} onUsernameChange={changeUser}>
          <Routes>
            {/* key=username：切换身份后重新挂载，避免看到上一个人的数据 */}
            <Route path="/" element={<HomePage key={username} username={username} />} />
            <Route path="/user-groups/:userGroupId" element={<WorkspacePage key={username} />} />
            <Route path="/projects/:projectId" element={<ProjectPage key={username} />} />
            <Route path="/runs/:runId" element={<RunPage key={username} />} />
            <Route path="/versions/:versionId" element={<VersionDetailPage key={username} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell>
      </AntdApp>
    </ConfigProvider>
  )
}
