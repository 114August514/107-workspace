import { PlusIcon, ThreeBarsIcon } from '@primer/octicons-react'
import { Button, Dialog, IconButton, PageLayout } from '@primer/react'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom'

import type { Home } from '../../api/types'
import type { AsyncState as AsyncResource } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { NotificationBell } from '../notification/NotificationBell'
import { CreateWorkspaceDialog } from '../workspace/CreateWorkspaceDialog'
import { appShellCopy } from './copy'
import { UserSwitcher } from './UserSwitcher'
import { WorkNavigation } from './WorkNavigation'
import styles from './AppShell.module.css'

interface Props {
  username: string
  onUsernameChange: (username: string) => void
  home: AsyncResource<Home>
  children: ReactNode
}

export function AppShell({ username, onUsernameChange, home, children }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const navigationId = useId()
  const navigationButtonRef = useRef<HTMLButtonElement>(null)
  const homeLinkRef = useRef<HTMLAnchorElement>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [navigationOpen, setNavigationOpen] = useState(false)

  useEffect(() => {
    setNavigationOpen(false)
  }, [location.pathname, username])

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
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
            <RouterLink to="/" className={styles.brand}>
              {appShellCopy.brand}
            </RouterLink>
          </div>
          <div className={styles.actions}>
            <Button
              className={styles.createButton}
              variant="default"
              leadingVisual={PlusIcon}
              aria-label={appShellCopy.createWorkspace}
              onClick={() => setCreateOpen(true)}
            >
              <span className={styles.createLabel}>{appShellCopy.createWorkspace}</span>
            </Button>
            {/* key=username：切换身份时整棵重挂载，丢弃在途的未读数请求，
                避免 A 身份迟到的响应盖掉 B 身份刚拉到的数字。 */}
            <NotificationBell key={username} username={username} />
            <UserSwitcher value={username} onChange={onUsernameChange} />
          </div>
        </div>
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

      <footer className={styles.footer}>
        <div className={styles.footerInner}>{appShellCopy.footer}</div>
      </footer>

      {navigationOpen ? (
        <Dialog
          title={appShellCopy.drawerTitle}
          position="left"
          width="medium"
          height="large"
          className={styles.navigationDrawer}
          initialFocusRef={homeLinkRef}
          returnFocusRef={navigationButtonRef}
          onClose={() => setNavigationOpen(false)}
        >
          <div id={navigationId}>
            <AsyncState
              loading={home.loading}
              loadingText={appShellCopy.navigationLoading}
              error={toNavigationError(home.error)}
              onRetry={home.reload}
            >
              {home.data ? (
                <WorkNavigation
                  home={home.data}
                  homeLinkRef={homeLinkRef}
                  onNavigate={() => setNavigationOpen(false)}
                />
              ) : null}
            </AsyncState>
          </div>
        </Dialog>
      ) : null}

      <CreateWorkspaceDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(workspace) => navigate(`/workspaces/${workspace.id}`)}
      />
    </div>
  )
}

function toNavigationError(error: Error | undefined) {
  if (!error) return undefined
  return {
    message: appShellCopy.navigationError,
    problems: [appShellCopy.navigationErrorNextStep],
  }
}
