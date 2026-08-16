import { PlusIcon } from '@primer/octicons-react'
import { Button } from '@primer/react'
import { useState, type ReactNode } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'

import { NotificationBell } from '../notification/NotificationBell'
import { CreateWorkspaceDialog } from '../workspace/CreateWorkspaceDialog'
import { UserSwitcher } from './UserSwitcher'
import styles from './AppShell.module.css'

interface Props {
  username: string
  onUsernameChange: (username: string) => void
  children: ReactNode
}

export function AppShell({ username, onUsernameChange, children }: Props) {
  const navigate = useNavigate()
  const [createOpen, setCreateOpen] = useState(false)

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.headerInner}>
          <RouterLink to="/" className={styles.brand}>
            107 Workspace
          </RouterLink>
          <div className={styles.actions}>
            <Button
              variant="primary"
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

      <main className={styles.content}>{children}</main>

      <footer className={styles.footer}>
        <div className={styles.footerInner}>GPU 型号、分区、QoS 和配额等信息以平台页面为准。</div>
      </footer>

      <CreateWorkspaceDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(workspace) => navigate(`/workspaces/${workspace.id}`)}
      />
    </div>
  )
}
