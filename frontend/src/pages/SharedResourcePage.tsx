import { PackageIcon, PencilIcon, PlusIcon } from '@primer/octicons-react'
import { Breadcrumbs, Button, Label, Text } from '@primer/react'
import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import { can } from '../api/types'
import type { LegacyWorkspaceContext, SharedResourceDetail } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { normalizeError } from '../components/common/asyncStateError'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import { PrimerRelativeTime } from '../components/primer/PrimerMono'
import { PrimerStack } from '../components/primer/PrimerStack'
import { EditSharedResourceModal } from '../components/sharedresource/EditSharedResourceModal'
import { PublishVersionModal } from '../components/sharedresource/PublishVersionModal'
import { loadSharedResourceOwnerContext } from '../components/sharedresource/ownerContext'
import { SharedResourceVersionBody } from '../components/sharedresource/SharedResourceVersionBody'
import styles from '../components/sharedresource/sharedResource.module.css'
import { PrimerRoot } from '../primer/setup'

export function SharedResourcePage() {
  const { resourceId = '' } = useParams()
  const [token, setToken] = useState(0)
  const bump = () => setToken((value) => value + 1)

  const resource = useAsync<SharedResourceDetail>(
    () => api.getSharedResource(resourceId),
    [resourceId, token],
  )
  const workspace = useAsync<LegacyWorkspaceContext | undefined>(
    async () => (resource.data ? loadSharedResourceOwnerContext(resource.data) : undefined),
    [resource.data?.owner.kind, resource.data?.owner.id],
  )
  const [editing, setEditing] = useState(false)
  const [publishing, setPublishing] = useState(false)

  const canManage = can(workspace.data, 'shared_resource.manage')
  const canPublish = can(workspace.data, 'shared_resource.version.create')
  // 版本列表按 sequence 倒序，首个即最新。
  const versions = resource.data?.versions ?? []
  const latestVersionId = versions[0]?.id

  // 选中版本同步到 ?version=：刷新不丢，也允许直接分享某个版本的链接。
  // URL 里的 id 不在当前版本列表里（失效或乱填）时落回最新版本。
  const [searchParams, setSearchParams] = useSearchParams()
  const versionFromUrl = searchParams.get('version')
  const selectedVersionId = versions.some((v) => v.id === versionFromUrl)
    ? versionFromUrl
    : versions[0]?.id

  return (
    <PrimerRoot>
      <PrimerStack gap="large">
        <AsyncState loading={resource.loading} error={normalizeError(resource.error)}>
          {resource.data && (
            <header className={styles.header}>
              {/* GitHub 仓库头式样：面包屑独占一行，标题（图标 + h1 + 归属标签）
                  换到第二行，操作按钮放在标题行右侧。 */}
              <Breadcrumbs>
                <Breadcrumbs.Item as={Link} to="/">
                  首页
                </Breadcrumbs.Item>
                {workspace.data ? (
                  <Breadcrumbs.Item as={Link} to={`/workspaces/${workspace.data.id}`}>
                    {resource.data.owner.display_name}
                  </Breadcrumbs.Item>
                ) : (
                  <Breadcrumbs.Item>{resource.data.owner.display_name}</Breadcrumbs.Item>
                )}
                {workspace.data ? (
                  <Breadcrumbs.Item
                    as={Link}
                    to={`/workspaces/${workspace.data.id}/shared-resources`}
                  >
                    共享资源
                  </Breadcrumbs.Item>
                ) : (
                  <Breadcrumbs.Item>共享资源</Breadcrumbs.Item>
                )}
              </Breadcrumbs>
              <div className={styles.titleRow}>
                <PackageIcon className={styles.titleIcon} size={24} />
                <h1 className={styles.title}>{resource.data.name}</h1>
                <Label>归属：{resource.data.owner.display_name}</Label>
                <div className={styles.actions}>
                  {canManage && (
                    <Button leadingVisual={PencilIcon} onClick={() => setEditing(true)}>
                      修改共享资源
                    </Button>
                  )}
                  {canPublish && (
                    <Button
                      variant="primary"
                      leadingVisual={PlusIcon}
                      onClick={() => setPublishing(true)}
                    >
                      发布版本
                    </Button>
                  )}
                </div>
              </div>
              <Text as="p" className={styles.headerDescription}>
                {resource.data.description || '这个共享资源还没有填写说明。'}
              </Text>
            </header>
          )}
        </AsyncState>

        {versions.length === 0 ? (
          <PrimerListCard title="版本">
            <AsyncState
              loading={resource.loading}
              error={normalizeError(resource.error)}
              empty={resource.data !== undefined}
              emptyText="这个共享资源还没有已发布版本。"
              emptyDescription={
                canPublish ? '发布首个版本后，Project 才能引用这个共享资源。' : undefined
              }
              emptyAction={canPublish ? '发布版本' : null}
              onEmptyAction={canPublish ? () => setPublishing(true) : undefined}
            >
              {null}
            </AsyncState>
          </PrimerListCard>
        ) : (
          <div className={styles.splitLayout}>
            {/* GitHub Releases 式样：左侧版本列表，右侧选中版本详情。 */}
            <nav className={styles.versionNav} aria-label="版本列表">
              {versions.map((version) => {
                const selected = version.id === selectedVersionId
                return (
                  <button
                    key={version.id}
                    type="button"
                    aria-current={selected ? 'true' : undefined}
                    className={
                      selected
                        ? `${styles.versionItem} ${styles.versionItemSelected}`
                        : styles.versionItem
                    }
                    onClick={() => setSearchParams({ version: version.id }, { replace: true })}
                  >
                    <span className={styles.versionItemLabel}>
                      {version.label}
                      {version.id === latestVersionId && <Label>最新</Label>}
                    </span>
                    <Text size="small" className={styles.desc}>
                      <PrimerRelativeTime value={version.created_at} />
                    </Text>
                  </button>
                )
              })}
            </nav>
            {selectedVersionId && <SharedResourceVersionBody versionId={selectedVersionId} />}
          </div>
        )}

        <EditSharedResourceModal
          open={editing}
          resource={resource.data}
          onClose={() => setEditing(false)}
          onUpdated={bump}
        />

        <PublishVersionModal
          open={publishing}
          resourceId={resourceId}
          onClose={() => setPublishing(false)}
          onPublished={() => bump()}
        />
      </PrimerStack>
    </PrimerRoot>
  )
}
