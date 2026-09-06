import {
  EnvironmentProvider,
  EnvironmentHeaderContext,
  EnvironmentHeaderNav,
} from '../environment/EnvironmentHeader'
import {
  FileDirectoryIcon,
  GearIcon,
  PlayIcon,
  PlusIcon,
  PulseIcon,
  ThreeBarsIcon,
} from '@primer/octicons-react'
import {
  ActionList,
  ActionMenu,
  Button,
  ButtonGroup,
  defaultPaneWidth,
  IconButton,
  PageLayout,
  UnderlineNav,
} from '@primer/react'
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { Link as RouterLink, matchPath, useLocation } from 'react-router-dom'

import type { Home, Project, User } from '../../api/types'
import type { AsyncState as AsyncResource } from '../../api/useAsync'
import { startLogin } from '../../auth/AuthProvider'
import { authCopy } from '../../auth/authCopy'
import { BrandMark } from '../../brand/BrandMark'
import { GlobalNavigationDrawer } from './GlobalNavigationDrawer'
import { NotificationBell } from '../notification/NotificationBell'
import { ContextGuide } from './ContextGuide'
import {
  UserGroupHeaderContext,
  UserGroupHeaderNav,
  UserGroupProvider,
} from '../usergroup/UserGroupHeaderNav'
import { appShellCopy } from './copy'
import { ProjectSwitcher } from './ProjectSwitcher'
import { UserMenu } from './UserMenu'
import { WorkNavigation } from './WorkNavigation'
import styles from './AppShell.module.css'

interface Props {
  user?: User
  home: AsyncResource<Home>
  project: AsyncResource<Project | undefined>
  children: ReactNode
}

type AppShellStyle = CSSProperties & { '--app-shell-sidebar-width': string }

const appShellStyle: AppShellStyle = {
  '--app-shell-sidebar-width': `${defaultPaneWidth.medium}px`,
}

export function AppShell({ user, home, project, children }: Props) {
  const signedIn = user !== undefined
  const username = user?.username ?? ''
  const location = useLocation()
  const navigationId = useId()
  const navigationButtonRef = useRef<HTMLButtonElement>(null)
  const [navigationOpen, setNavigationOpen] = useState(false)
  const projectId =
    location.pathname === '/projects/new'
      ? undefined
      : matchPath('/projects/:projectId/*', location.pathname)?.params.projectId
  const currentProject = project.data?.id === projectId ? project.data : undefined
  const isEnvironment =
    location.pathname !== '/environments/new' &&
    /^\/(environments|environment-versions)\/[^/]+$/.test(location.pathname)
  const isUserGroupAssetList =
    matchPath('/user-groups/:userGroupId/projects', location.pathname) !== null ||
    matchPath('/user-groups/:userGroupId/shared-resources', location.pathname) !== null ||
    matchPath('/user-groups/:userGroupId/environments', location.pathname) !== null
  const groupId = matchPath('/user-groups/:userGroupId/*', location.pathname)?.params.userGroupId
  const creationOwner =
    groupId && groupId !== 'new' ? { kind: 'user_group', id: groupId } : currentProject?.owner
  const ownerQuery = creationOwner
    ? `?owner=${encodeURIComponent(`${creationOwner.kind}:${creationOwner.id}`)}`
    : ''

  const projectPath = projectId ? `/projects/${projectId}` : ''
  const projectSubpath = projectPath ? location.pathname.slice(projectPath.length) : ''
  const projectArea = projectSubpath.startsWith('/runs')
    ? 'runs'
    : projectSubpath.startsWith('/activity')
      ? 'activity'
      : projectSubpath.startsWith('/settings')
        ? 'settings'
        : 'files'

  useEffect(() => {
    setNavigationOpen(false)
  }, [location.pathname, username])

  return (
    <UserGroupProvider>
      <EnvironmentProvider>
        <div className={styles.shell} style={appShellStyle}>
          <header
            className={`${styles.header} ${projectId || isEnvironment || location.pathname.startsWith('/user-groups/') ? styles.projectHeader : ''}`}
          >
            <div className={styles.headerInner}>
              <div className={styles.headerStart}>
                {signedIn ? (
                  <IconButton
                    ref={navigationButtonRef}
                    icon={ThreeBarsIcon}
                    variant="default"
                    aria-label={appShellCopy.openNavigation}
                    aria-expanded={navigationOpen}
                    aria-controls={navigationId}
                    onClick={() => setNavigationOpen(true)}
                  />
                ) : null}
                <RouterLink to="/" className={styles.brand} aria-label={appShellCopy.homeMarkLabel}>
                  <BrandMark size={32} decorative />
                </RouterLink>
                {!projectId && !isEnvironment && !location.pathname.startsWith('/user-groups/') ? (
                  <Button
                    as={RouterLink}
                    to="/"
                    variant="invisible"
                    className={`${styles.projectContextItem} ${styles.projectOwner}`}
                  >
                    <span className={styles.projectContextLabel}>{appShellCopy.brand}</span>
                  </Button>
                ) : null}
                {projectId ? (
                  <div
                    className={styles.projectContext}
                    role="group"
                    aria-label={appShellCopy.projectContextLabel}
                  >
                    {currentProject ? (
                      <>
                        <Button
                          as={RouterLink}
                          to={
                            currentProject.owner.kind === 'user_group'
                              ? `/user-groups/${currentProject.owner.id}`
                              : '/'
                          }
                          variant="invisible"
                          className={`${styles.projectContextItem} ${styles.projectOwner}`}
                        >
                          <span className={styles.projectContextLabel}>
                            {currentProject.owner.display_name}
                          </span>
                        </Button>
                        <span className={styles.projectSeparator} aria-hidden>
                          /
                        </span>
                        <ButtonGroup className={styles.projectSelector}>
                          <Button
                            as={RouterLink}
                            to={`/projects/${projectId}`}
                            variant="invisible"
                            className={`${styles.projectContextItem} ${styles.projectName}`}
                          >
                            <span className={styles.projectContextLabel}>
                              {currentProject.name}
                            </span>
                          </Button>
                          <ProjectSwitcher project={currentProject} />
                        </ButtonGroup>
                      </>
                    ) : project.error ? (
                      <Button
                        variant="invisible"
                        className={styles.projectRetry}
                        onClick={() => void project.reload()}
                      >
                        {appShellCopy.projectError}
                      </Button>
                    ) : (
                      <span className={styles.projectLoading} role="status">
                        {appShellCopy.projectLoading}
                      </span>
                    )}
                  </div>
                ) : location.pathname === '/' ? null : (
                  <>
                    <UserGroupHeaderContext />
                    <EnvironmentHeaderContext />
                  </>
                )}
              </div>
              <div className={styles.actions}>
                {signedIn ? (
                  <>
                    <ActionMenu>
                      <ActionMenu.Anchor>
                        <IconButton
                          icon={PlusIcon}
                          variant="default"
                          aria-label="创建"
                          aria-haspopup="menu"
                        />
                      </ActionMenu.Anchor>
                      <ActionMenu.Overlay align="end" width="auto">
                        <ActionList>
                          <ActionList.LinkItem href="/projects/new">
                            创建 Project
                          </ActionList.LinkItem>
                          <ActionList.LinkItem href={`/shared-resources/new${ownerQuery}`}>
                            创建共享资源
                          </ActionList.LinkItem>
                          <ActionList.LinkItem href={`/environments/new${ownerQuery}`}>
                            创建运行环境
                          </ActionList.LinkItem>
                          <ActionList.Divider />
                          <ActionList.LinkItem href="/user-groups/new">
                            创建 User Group
                          </ActionList.LinkItem>
                        </ActionList>
                      </ActionMenu.Overlay>
                    </ActionMenu>

                    {/* key=user.id：身份变化时整棵重挂载，丢弃在途的未读数请求。 */}
                    <NotificationBell key={user.id} username={username} />
                    <UserMenu user={user} />
                  </>
                ) : (
                  <Button variant="primary" onClick={() => startLogin()}>
                    {authCopy.login}
                  </Button>
                )}
              </div>
            </div>
            {signedIn ? (
              <>
                <UserGroupHeaderNav />
                <EnvironmentHeaderNav />
              </>
            ) : null}
            {signedIn && projectId ? (
              <div className={styles.projectNavigationSurface}>
                <UnderlineNav
                  aria-label={appShellCopy.projectNavigationLabel}
                  className={styles.projectNavigation}
                  hideIconsBreakpoint={null}
                >
                  <UnderlineNav.Item
                    as={RouterLink}
                    to={`/projects/${projectId}/files`}
                    leadingVisual={<FileDirectoryIcon />}
                    aria-current={projectArea === 'files' ? 'page' : undefined}
                  >
                    {appShellCopy.files}
                  </UnderlineNav.Item>
                  <UnderlineNav.Item
                    as={RouterLink}
                    to={`/projects/${projectId}/runs`}
                    leadingVisual={<PlayIcon />}
                    aria-current={projectArea === 'runs' ? 'page' : undefined}
                  >
                    {appShellCopy.runs}
                  </UnderlineNav.Item>
                  <UnderlineNav.Item
                    as={RouterLink}
                    to={`/projects/${projectId}/activity`}
                    leadingVisual={<PulseIcon />}
                    aria-current={projectArea === 'activity' ? 'page' : undefined}
                  >
                    {appShellCopy.activity}
                  </UnderlineNav.Item>
                  <UnderlineNav.Item
                    as={RouterLink}
                    to={`/projects/${projectId}/settings`}
                    leadingVisual={<GearIcon />}
                    aria-current={projectArea === 'settings' ? 'page' : undefined}
                  >
                    {appShellCopy.settings}
                  </UnderlineNav.Item>
                </UnderlineNav>
              </div>
            ) : null}
          </header>

          <div className={styles.body}>
            {signedIn && location.pathname === '/' ? (
              <aside className={styles.persistentSidebar} aria-label={appShellCopy.sidebarLabel}>
                {home.data ? <WorkNavigation home={home.data} /> : null}
              </aside>
            ) : null}
            <main className={styles.main}>
              <PageLayout containerWidth="full" padding="none" rowGap="none" columnGap="none">
                <PageLayout.Content
                  as="div"
                  width={isUserGroupAssetList ? 'full' : 'xlarge'}
                  padding={isUserGroupAssetList ? 'none' : 'normal'}
                >
                  {children}
                </PageLayout.Content>
              </PageLayout>
            </main>
          </div>

          <ContextGuide pathname={location.pathname} />

          {signedIn && navigationOpen ? (
            <GlobalNavigationDrawer
              id={navigationId}
              home={home}
              returnFocusRef={navigationButtonRef}
              onClose={() => setNavigationOpen(false)}
            />
          ) : null}
        </div>
      </EnvironmentProvider>
    </UserGroupProvider>
  )
}
