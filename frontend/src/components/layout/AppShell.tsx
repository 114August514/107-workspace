import { PlusIcon, ThreeBarsIcon } from '@primer/octicons-react'
import { Button, defaultPaneWidth, IconButton, PageLayout } from '@primer/react'
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom'

import type { Home } from '../../api/types'
import type { AsyncState as AsyncResource } from '../../api/useAsync'
import { GlobalNavigationDrawer } from './GlobalNavigationDrawer'
import { NotificationBell } from '../notification/NotificationBell'
import { CreateUserGroupDialog } from '../workspace/CreateUserGroupDialog'
import { ContextGuide } from './ContextGuide'
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

type AppShellStyle = CSSProperties & { '--app-shell-sidebar-width': string }

const appShellStyle: AppShellStyle = {
  '--app-shell-sidebar-width': `${defaultPaneWidth.medium}px`,
}

export function AppShell({ username, onUsernameChange, home, children }: Props) {
  const navigate = useNavigate()
  const location = useLocation()
  const navigationId = useId()
  const navigationButtonRef = useRef<HTMLButtonElement>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [navigationOpen, setNavigationOpen] = useState(false)

  useEffect(() => {
    setNavigationOpen(false)
  }, [location.pathname, username])

  return (
    <div className={styles.shell} style={appShellStyle}>
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
              aria-label={appShellCopy.createUserGroup}
              onClick={() => setCreateOpen(true)}
            >
              <span className={styles.createLabel}>{appShellCopy.createUserGroup}</span>
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
