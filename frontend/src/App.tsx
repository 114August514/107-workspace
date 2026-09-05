import { App as AntdApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { lazy, Suspense } from 'react'
import { matchPath, Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { api } from './api/client'
import { toAsyncError } from './api/errors'
import type { Home, Project } from './api/types'
import { useAsync, type AsyncState as AsyncResource } from './api/useAsync'
import { AuthProvider, useAuth } from './auth/AuthProvider'
import { authCopy } from './auth/authCopy'
import { EnvironmentsSection } from './components/usergroup/EnvironmentsSection'
import { MembersSection } from './components/usergroup/MembersSection'
import { OverviewSection } from './components/usergroup/OverviewSection'
import { ProjectsSection } from './components/usergroup/ProjectsSection'
import { SettingsSection } from './components/usergroup/SettingsSection'
import { SharedResourcesSection } from './components/usergroup/SharedResourcesSection'
import { AsyncState } from './components/common/AsyncState'
import { AppShell } from './components/layout/AppShell'
import { ArtifactFilePreviewPage } from './pages/ArtifactFilePreviewPage'
import { HomePage } from './pages/HomePage'
import { PersonalExecutionContextPage } from './pages/PersonalExecutionContextPage'
import { ProfilePage } from './pages/ProfilePage'
import { EnvironmentListPage } from './pages/EnvironmentListPage'
import { EnvironmentPage } from './pages/EnvironmentPage'
import { EnvironmentVersionPage } from './pages/EnvironmentVersionPage'
import { ProjectPage } from './pages/ProjectPage'
import { PublicHomePage } from './pages/PublicHomePage'
import { RunPage } from './pages/RunPage'
import { RunLocatorPage } from './pages/RunLocatorPage'
import { SharedResourcePage } from './pages/SharedResourcePage'
import { SharedResourceVersionPage } from './pages/SharedResourceVersionPage'
import { VersionDetailPage } from './pages/VersionDetailPage'
import { UserGroupPage } from './pages/UserGroupPage'
import { PrimerRoot } from './primer/setup'
import { theme } from './theme'

const DesignSystemPage = lazy(() =>
  import('./pages/design-system/DesignSystemPage').then((module) => ({
    default: module.DesignSystemPage,
  })),
)

const emptyProject: AsyncResource<Project | undefined> = {
  data: undefined,
  loading: false,
  error: undefined,
  reload: async () => {},
}

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
  return (
    <ConfigProvider locale={zhCN} theme={theme}>
      <AntdApp>
        <AuthProvider>
          <AuthGate />
        </AuthProvider>
      </AntdApp>
    </ConfigProvider>
  )
}

function AuthGate() {
  const location = useLocation()
  const auth = useAuth()

  if (auth.status === 'loading') {
    return (
      <AppShell home={auth.home} project={emptyProject}>
        <AsyncState loading loadingText={authCopy.confirming} onRetry={auth.retry}>
          {null}
        </AsyncState>
      </AppShell>
    )
  }

  if (auth.status === 'error') {
    return (
      <AppShell home={auth.home} project={emptyProject}>
        <AsyncState
          loading={false}
          loadingText={authCopy.confirming}
          error={
            toAsyncError(auth.error) ?? {
              message: authCopy.confirmFailed,
              problems: [authCopy.confirmFailedNext],
            }
          }
          onRetry={auth.retry}
        >
          {null}
        </AsyncState>
      </AppShell>
    )
  }

  if (auth.status === 'unauthenticated') {
    if (location.pathname !== '/') {
      return <Navigate to="/" replace />
    }
    return <PublicHomePage />
  }

  if (!auth.user) {
    return <PublicHomePage />
  }

  return <ProductSession />
}

function ProductSession() {
  const { user, home } = useAuth()
  const location = useLocation()
  const username = user?.username ?? ''
  const projectId = matchPath('/projects/:projectId/*', location.pathname)?.params.projectId
  const project = useAsync<Project | undefined>(
    () => (projectId ? api.getProject(projectId) : Promise.resolve(undefined)),
    [username, projectId],
  )
  const routedProject: AsyncResource<Project | undefined> = {
    ...project,
    data: project.data?.id === projectId ? project.data : undefined,
  }

  return (
    <AppShell user={user} home={home} project={routedProject}>
      <ProductRoutes username={username} home={home} project={routedProject} />
    </AppShell>
  )
}

export function ProductRoutes({
  username,
  home,
  project,
}: {
  username: string
  home: AsyncResource<Home>
  project: AsyncResource<Project | undefined>
}) {
  return (
    <Routes>
      <Route path="/" element={<HomePage username={username} home={home} />} />
      <Route path="/profile" element={<ProfilePage home={home} />} />
      <Route
        path="/execution-context"
        element={<PersonalExecutionContextPage username={username} home={home} />}
      />
      <Route
        path="/user-groups/:userGroupId"
        element={<UserGroupPage key={username} onMembershipChanged={home.reload} />}
      >
        <Route index element={<OverviewSection />} />
        <Route path="members" element={<MembersSection />} />
        <Route path="projects" element={<ProjectsSection />} />
        <Route path="shared-resources" element={<SharedResourcesSection />} />
        <Route path="environments" element={<EnvironmentsSection />} />
        <Route path="settings" element={<SettingsSection />} />
        <Route path="*" element={<Navigate to=".." replace />} />
      </Route>
      <Route path="/environments" element={<EnvironmentListPage key={username} />} />
      <Route path="/environments/:environmentId" element={<EnvironmentPage key={username} />} />
      <Route
        path="/environment-versions/:versionId"
        element={<EnvironmentVersionPage key={username} />}
      />
      <Route
        path="/projects/:projectId"
        element={<ProjectPage key={username} project={project} />}
      />
      <Route path="/projects/:projectId/runs/:runId" element={<RunPage key={username} />} />
      <Route
        path="/projects/:projectId/runs/:runId/artifacts/:artifactId/file"
        element={<ArtifactFilePreviewPage key={username} />}
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
