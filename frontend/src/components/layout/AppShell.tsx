import {
  FileDirectoryIcon,
  GearIcon,
  PlayIcon,
  PlusIcon,
  ThreeBarsIcon,
} from '@primer/octicons-react'
import {
  Button,
  ButtonGroup,
  defaultPaneWidth,
  IconButton,
  PageLayout,
  UnderlineNav,
} from '@primer/react'
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { Link as RouterLink, matchPath, useLocation, useNavigate } from 'react-router-dom'

import type { Home, Project, User } from '../../api/types'
import type { AsyncState as AsyncResource } from '../../api/useAsync'
import { startLogin } from '../../auth/AuthProvider'
import { authCopy } from '../../auth/authCopy'
import { GlobalNavigationDrawer } from './GlobalNavigationDrawer'
import { NotificationBell } from '../notification/NotificationBell'
import { CreateUserGroupDialog } from '../workspace/CreateUserGroupDialog'
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

function HomeMarkVisual() {
  return (
    <span className={styles.homeMarkVisual} aria-hidden>
      {appShellCopy.homeMark}
    </span>
  )
}

type AppShellStyle = CSSProperties & { '--app-shell-sidebar-width': string }

const appShellStyle: AppShellStyle = {
  '--app-shell-sidebar-width': `${defaultPaneWidth.medium}px`,
}

export function AppShell({ user, home, project, children }: Props) {
  const signedIn = user !== undefined
  const username = user?.username ?? ''
  const navigate = useNavigate()
  const location = useLocation()
  const navigationId = useId()
  const navigationButtonRef = useRef<HTMLButtonElement>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [navigationOpen, setNavigationOpen] = useState(false)
  const projectId = matchPath('/projects/:projectId/*', location.pathname)?.params.projectId
  const currentProject = project.data?.id === projectId ? project.data : undefined
  const requestedTab = new URLSearchParams(location.search).get('tab')
  const isUserGroupAssetList =
    matchPath('/user-groups/:userGroupId/projects', location.pathname) !== null ||
    matchPath('/user-groups/:userGroupId/shared-resources', location.pathname) !== null ||
    matchPath('/user-groups/:userGroupId/environments', location.pathname) !== null
  const projectArea = location.pathname.includes('/runs/')
    ? 'runs'
    : requestedTab === 'runs' || requestedTab === 'configurations'
      ? 'runs'
      : requestedTab === 'activities'
        ? 'settings'
        : 'files'

  useEffect(() => {
    setNavigationOpen(false)
  }, [location.pathname, username])

  return (
    <UserGroupProvider>
      <div className={styles.shell} style={appShellStyle}>
        <header
          className={`${styles.header} ${projectId || location.pathname.startsWith('/user-groups/') ? styles.projectHeader : ''}`}
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
              <IconButton
                as={RouterLink}
                to="/"
                icon={HomeMarkVisual}
                variant="default"
                aria-label={appShellCopy.homeMarkLabel}
              />
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
                          <span className={styles.projectContextLabel}>{currentProject.name}</span>
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
              ) : location.pathname === '/' || !signedIn ? (
                <span className={styles.homeContext}>{appShellCopy.homeContext}</span>
              ) : (
                <UserGroupHeaderContext />
              )}
            </div>
            <div className={styles.actions}>
              {signedIn ? (
                <>
                  <IconButton
                    icon={PlusIcon}
                    variant="default"
                    aria-label={appShellCopy.createUserGroup}
                    onClick={() => setCreateOpen(true)}
                  />
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
          {signedIn ? <UserGroupHeaderNav /> : null}
          {signedIn && projectId ? (
            <div className={styles.projectNavigationSurface}>
              <UnderlineNav
                aria-label={appShellCopy.projectNavigationLabel}
                className={styles.projectNavigation}
                hideIconsBreakpoint={null}
              >
                <UnderlineNav.Item
                  as={RouterLink}
                  to={`/projects/${projectId}?tab=files`}
                  leadingVisual={<FileDirectoryIcon />}
                  aria-current={projectArea === 'files' ? 'page' : undefined}
                >
                  {appShellCopy.files}
                </UnderlineNav.Item>
                <UnderlineNav.Item
                  as={RouterLink}
                  to={`/projects/${projectId}?tab=runs`}
                  leadingVisual={<PlayIcon />}
                  aria-current={projectArea === 'runs' ? 'page' : undefined}
                >
                  {appShellCopy.runs}
                </UnderlineNav.Item>
                <UnderlineNav.Item
                  as={RouterLink}
                  to={`/projects/${projectId}?tab=activities`}
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

        {signedIn ? (
          <CreateUserGroupDialog
            open={createOpen}
            onClose={() => setCreateOpen(false)}
            onCreated={(userGroup) => {
              home.reload()
              navigate(`/user-groups/${userGroup.id}`)
            }}
          />
        ) : null}
      </div>
    </UserGroupProvider>
  )
}
