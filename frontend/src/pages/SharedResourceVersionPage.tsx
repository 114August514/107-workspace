import { TagIcon } from '@primer/octicons-react'
import { Breadcrumbs, Text } from '@primer/react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { SharedResourceDetail, SharedResourceVersionDetail, Workspace } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { normalizeError } from '../components/common/asyncStateError'
import { SharedResourceVersionBody } from '../components/sharedresource/SharedResourceVersionBody'
import styles from '../components/sharedresource/sharedResource.module.css'
import { PrimerStack } from '../components/primer/PrimerStack'
import { PrimerRoot } from '../primer/setup'

/**
 * 版本详情独立页：活动记录与通知里的深链路入口。
 * 页头（面包屑 + 标题 + 说明）由本页持有，详情主体与资源详情页
 * 右侧分栏共用 SharedResourceVersionBody。
 */
export function SharedResourceVersionPage() {
  const { versionId = '' } = useParams()
  const version = useAsync<SharedResourceVersionDetail>(
    () => api.getSharedResourceVersion(versionId),
    [versionId],
  )
  const resource = useAsync<SharedResourceDetail | undefined>(
    async () => (version.data ? api.getSharedResource(version.data.shared_resource_id) : undefined),
    [version.data?.shared_resource_id],
  )
  // 面包屑要回到所属工作区的「共享资源」深链路，所以也得加载工作区。
  const workspace = useAsync<Workspace | undefined>(
    async () =>
      resource.data?.owner_workspace_id
        ? api.getWorkspace(resource.data.owner_workspace_id)
        : undefined,
    [resource.data?.owner_workspace_id],
  )

  const isPlatform = resource.data?.is_platform_owned ?? false

  return (
    <PrimerRoot>
      <PrimerStack gap="large">
        <AsyncState loading={version.loading} error={normalizeError(version.error)}>
          {version.data && (
            <header className={styles.header}>
              {/* 与资源详情页同一页头式样：面包屑一行，标题（图标 + h1）换行。 */}
              <Breadcrumbs>
                <Breadcrumbs.Item as={Link} to="/">
                  首页
                </Breadcrumbs.Item>
                {isPlatform ? (
                  // 平台资源没有所属工作区，面包屑这一段就只显示「平台」。
                  <Breadcrumbs.Item>平台</Breadcrumbs.Item>
                ) : workspace.data ? (
                  <Breadcrumbs.Item as={Link} to={`/workspaces/${workspace.data.id}`}>
                    {workspace.data.name}
                  </Breadcrumbs.Item>
                ) : null}
                <Breadcrumbs.Item
                  as={Link}
                  to={`/workspaces/${workspace.data?.id ?? ''}/shared-resources`}
                >
                  共享资源
                </Breadcrumbs.Item>
                {resource.data && (
                  <Breadcrumbs.Item as={Link} to={`/shared-resources/${resource.data.id}`}>
                    {resource.data.name}
                  </Breadcrumbs.Item>
                )}
              </Breadcrumbs>
              <div className={styles.titleRow}>
                <TagIcon className={styles.titleIcon} size={24} />
                <h1 className={styles.title}>{version.data.label}</h1>
              </div>
              <Text as="p" className={styles.headerDescription}>
                {version.data.description || '这个版本没有填写说明。'}
              </Text>
            </header>
          )}
        </AsyncState>

        <SharedResourceVersionBody versionId={versionId} />
      </PrimerStack>
    </PrimerRoot>
  )
}
