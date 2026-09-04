import {
  FileDirectoryIcon,
  GearIcon,
  PlayIcon,
  PlusIcon,
  PulseIcon,
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

import type { Home, Project } from '../../api/types'
import type { AsyncState as AsyncResource } from '../../api/useAsync'
import { GlobalNavigationDrawer } from './GlobalNavigationDrawer'
import { NotificationBell } from '../notification/NotificationBell'
import { CreateUserGroupDialog } from '../workspace/CreateUserGroupDialog'
import { ContextGuide } from './ContextGuide'
import { appShellCopy } from './copy'
import { ProjectSwitcher } from './ProjectSwitcher'
import { UserSwitcher } from './UserSwitcher'
import { WorkNavigation } from './WorkNavigation'
import styles from './AppShell.module.css'

interface Props {
  username: string
  onUsernameChange: (username: string) => void
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

export function AppShell({ username, onUsernameChange, home, project, children }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const navigationId = useId()
  const navigationButtonRef = useRef<HTMLButtonElement>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [navigationOpen, setNavigationOpen] = useState(false)
  const projectId = matchPath('/projects/:projectId/*', location.pathname)?.params.projectId
  const currentProject = project.data?.id === projectId ? project.data : undefined
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
    <div className={styles.shell} style={appShellStyle}>
      <header className={`${styles.header} ${projectId ? styles.projectHeader : ''}`}>
        <div className={styles.headerInner}>
          <div className={styles.headerStart}>
            <IconButton
              ref={navigationButtonRef}
              icon={ThreeBarsIcon}
              variant="default"
              aria-label={appShellCopy.openNavigation}
              aria-expanded={navigationOpen}
              aria-controls={navigationId}
              onClick={() => setNavigationOpen(true)}
            />
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
            ) : location.pathname === '/' ? (
              <span className={styles.homeContext}>{appShellCopy.homeContext}</span>
            ) : null}
          </div>
          <div className={styles.actions}>
            <IconButton
              icon={PlusIcon}
              variant="default"
              aria-label={appShellCopy.createUserGroup}
              onClick={() => setCreateOpen(true)}
            />
            {/* key=username：切换身份时整棵重挂载，丢弃在途的未读数请求，
                避免 A 身份迟到的响应盖掉 B 身份刚拉到的数字。 */}
            <NotificationBell key={username} username={username} />
            <UserSwitcher value={username} onChange={onUsernameChange} />
          </div>
        </div>
        {projectId ? (
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
        {location.pathname === '/' ? (
          <aside className={styles.persistentSidebar} aria-label={appShellCopy.sidebarLabel}>
            {home.data ? <WorkNavigation home={home.data} /> : null}
          </aside>
        ) : null}
        <main className={styles.main}>
          <PageLayout containerWidth="full" padding="none" rowGap="none" columnGap="none">
            <PageLayout.Content as="div" width="xlarge" padding="normal">
              {children}
            </PageLayout.Content>
          </PageLayout>
        </main>
      </div>

      <ContextGuide pathname={location.pathname} />

      {navigationOpen ? (
        <GlobalNavigationDrawer
          id={navigationId}
          home={home}
          returnFocusRef={navigationButtonRef}
          onClose={() => setNavigationOpen(false)}
        />
      ) : null}

      <CreateUserGroupDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(userGroup) => {
          home.reload()
          navigate(`/user-groups/${userGroup.id}`)
        }}
      />
    </div>
  )
}
