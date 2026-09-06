import { ContainerIcon, PeopleIcon, VersionsIcon } from '@primer/octicons-react'
import { Button } from '@primer/react'
import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import type { Environment, EnvironmentPublicationAttempt } from '../../api/types'
import groupStyles from '../../pages/UserGroupPage.module.css'
import styles from '../../pages/Environment.module.css'
import overview from '../usergroup/overview.module.css'
import { PublishEnvironmentDialog } from './PublishEnvironmentDialog'

export function EnvironmentLayout({
  environment,
  children,
  initial,
  onCloseRetry,
}: {
  environment: Environment
  children: ReactNode
  initial?: EnvironmentPublicationAttempt
  onCloseRetry?: () => void
}) {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const canPublish = environment.capabilities?.includes('environment.version.create')
  const close = () => {
    setOpen(false)
    onCloseRetry?.()
  }
  return (
    <div className={groupStyles.overviewInner}>
      <header className={groupStyles.header}>
        <div className={groupStyles.avatar}>
          <ContainerIcon size={28} />
        </div>
        <div className={groupStyles.identity}>
          <h1 className={groupStyles.title}>{environment.name}</h1>
          <span className={styles.itemMeta}>运行环境</span>
        </div>
        {canPublish && (
          <Button variant="primary" className={styles.publishButton} onClick={() => setOpen(true)}>
            发布版本
          </Button>
        )}
      </header>
      <div className={overview.layout}>
        <div className={overview.section}>{children}</div>
        <aside className={overview.about}>
          <h2 className={overview.aboutTitle}>About</h2>
          <p className={overview.aboutDescription}>
            {environment.description || '这个运行环境还没有填写说明。'}
          </p>
          <p className={overview.aboutMeta}>
            <PeopleIcon />
            <Link
              to={
                environment.owner.kind === 'user_group'
                  ? `/user-groups/${environment.owner.id}`
                  : '/'
              }
            >
              {environment.owner.display_name}
            </Link>
          </p>
          <p className={overview.aboutMeta}>
            <VersionsIcon />
            {environment.versions.length} 个已发布版本
          </p>
          <div className={styles.aboutSection}>
            <h2 className={overview.aboutTitle}>如何使用</h2>
            <p className={overview.aboutDescription}>
              在项目的运行配置中选择此环境的确定版本。已发布内容保持不变；更新环境时请使用新版本。
            </p>
          </div>
        </aside>
      </div>
      {canPublish && (open || initial) && (
        <PublishEnvironmentDialog
          environmentId={environment.id}
          initial={initial}
          onClose={close}
          onCreated={() => {
            close()
            navigate(`/environments/${environment.id}?tab=history`, {
              state: { publication: Date.now() },
            })
          }}
        />
      )}
    </div>
  )
}
