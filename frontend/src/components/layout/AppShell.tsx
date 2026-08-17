import { PlusIcon, ThreeBarsIcon } from '@primer/octicons-react'
import { Button, Dialog, IconButton } from '@primer/react'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom'

import type { Home } from '../../api/types'
import type { AsyncState as AsyncResource } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { NotificationBell } from '../notification/NotificationBell'
import { CreateWorkspaceDialog } from '../workspace/CreateWorkspaceDialog'
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
              aria-label="打开导航"
              aria-expanded={navigationOpen}
              aria-controls={navigationId}
              onClick={() => setNavigationOpen(true)}
            />
            <RouterLink to="/" className={styles.brand}>
              107 Workspace
            </RouterLink>
          </div>
          <div className={styles.actions}>
            <Button
              className={styles.createButton}
              variant="default"
              leadingVisual={PlusIcon}
              aria-label="创建协作空间"
              onClick={() => setCreateOpen(true)}
            >
              <span className={styles.createLabel}>创建协作空间</span>
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
          <aside className={styles.persistentSidebar} aria-label="首页工作入口">
            {home.data ? <WorkNavigation home={home.data} /> : null}
          </aside>
        ) : null}
        <main className={styles.content}>
          <div className={styles.centeredContent}>{children}</div>
        </main>
      </div>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>GPU 型号、分区、QoS 和配额等信息以平台页面为准。</div>
      </footer>

      {navigationOpen ? (
        <Dialog
          title="107 Workspace"
          position="left"
          width="var(--workspace-drawer-width)"
          height="large"
          className={styles.navigationDrawer}
          initialFocusRef={homeLinkRef}
          returnFocusRef={navigationButtonRef}
          onClose={() => setNavigationOpen(false)}
        >
          <div id={navigationId}>
            <AsyncState
              loading={home.loading}
              loadingText="正在加载工作入口…"
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
    message: '工作入口加载失败。',
    problems: ['请检查网络连接后重试。'],
  }
}
