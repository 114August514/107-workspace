import { App as AntdApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { lazy, Suspense, useCallback, useRef, useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { api, getCurrentUser, setCurrentUser } from './api/client'
import type { Home } from './api/types'
import { useAsync, type AsyncState as AsyncResource } from './api/useAsync'
import { AppShell } from './components/layout/AppShell'
import { HomePage } from './pages/HomePage'
import { ProjectPage } from './pages/ProjectPage'
import { RunPage } from './pages/RunPage'
import { RunLocatorPage } from './pages/RunLocatorPage'
import { SharedResourcePage } from './pages/SharedResourcePage'
import { SharedResourceVersionPage } from './pages/SharedResourceVersionPage'
import { VersionDetailPage } from './pages/VersionDetailPage'
import { UserGroupPage } from './pages/UserGroupPage'
import { PrimerRoot } from './primer/setup'
import { theme } from './theme'

const USER_KEY = 'workspace107.devUser'
const DesignSystemPage = lazy(() =>
  import('./pages/design-system/DesignSystemPage').then((module) => ({
    default: module.DesignSystemPage,
  })),
)

export function App() {
  return (
    <PrimerRoot>
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
    </PrimerRoot>
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
        <ProductSession key={username} username={username} onUsernameChange={changeUser} />
      </AntdApp>
    </ConfigProvider>
  )
}

function ProductSession({
  username,
  onUsernameChange,
}: {
  username: string
  onUsernameChange: (username: string) => void
}) {
  const homeRequest = useRef<Promise<Home> | null>(null)
  const loadHome = () => {
    if (homeRequest.current) return homeRequest.current
    const request = api.home()
    homeRequest.current = request
    const clear = () => {
      if (homeRequest.current === request) homeRequest.current = null
    }
    void request.then(clear, clear)
    return request
  }
  const home = useAsync<Home>(loadHome, [username])

  return (
    <AppShell username={username} onUsernameChange={onUsernameChange} home={home}>
      <ProductRoutes username={username} home={home} />
    </AppShell>
  )
}

export function ProductRoutes({ username, home }: { username: string; home: AsyncResource<Home> }) {
  return (
    <Routes>
      <Route path="/" element={<HomePage username={username} home={home} />} />
      <Route path="/user-groups/:userGroupId" element={<UserGroupPage key={username} />} />
      <Route path="/projects/:projectId" element={<ProjectPage key={username} />} />
      <Route
        path="/projects/:projectId/runs/:runId"
        element={<RunPage key={username} currentUser={home.data?.user} />}
      />
      <Route path="/runs/:runId" element={<RunLocatorPage key={username} />} />
      <Route path="/versions/:versionId" element={<VersionDetailPage key={username} />} />
      <Route path="/shared-resources/:resourceId" element={<SharedResourcePage key={username} />} />
      <Route
        path="/shared-resource-versions/:versionId"
        element={<SharedResourceVersionPage key={username} />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
