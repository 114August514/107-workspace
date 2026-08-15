import { PencilIcon, PlusIcon } from '@primer/octicons-react'
import { Breadcrumbs, Button, Label, PageHeader, Text } from '@primer/react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { can } from '../api/types'
import type { SharedResourceDetail, SharedResourceVersion, Workspace } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { normalizeError } from '../components/common/asyncStateError'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import { PrimerMono, PrimerRelativeTime } from '../components/primer/PrimerMono'
import { PrimerStack } from '../components/primer/PrimerStack'
import { EditSharedResourceModal } from '../components/sharedresource/EditSharedResourceModal'
import { PublishVersionModal } from '../components/sharedresource/PublishVersionModal'
import styles from '../components/sharedresource/sharedResource.module.css'
import { PrimerRoot } from '../primer/setup'
import { formatBytes } from '../utils/format'

export function SharedResourcePage() {
  const { resourceId = '' } = useParams()
  const [token, setToken] = useState(0)
  const bump = () => setToken((value) => value + 1)

  const resource = useAsync<SharedResourceDetail>(
    () => api.getSharedResource(resourceId),
    [resourceId, token],
  )
  const workspace = useAsync<Workspace | undefined>(
    async () =>
      resource.data?.owner_workspace_id
        ? api.getWorkspace(resource.data.owner_workspace_id)
        : undefined,
    [resource.data?.owner_workspace_id],
  )
  const [editing, setEditing] = useState(false)
  const [publishing, setPublishing] = useState(false)

  const isPlatform = resource.data?.is_platform_owned ?? false
  const canManage = !isPlatform && can(workspace.data, 'shared_resource.manage')
  const canPublish = !isPlatform && can(workspace.data, 'shared_resource.version.create')
  const versions = resource.data?.versions ?? []

  return (
    <PrimerRoot>
      <PrimerStack gap="large">
        <AsyncState loading={resource.loading} error={normalizeError(resource.error)}>
          {resource.data && (
            <PageHeader>
              <PageHeader.Breadcrumbs>
                <Breadcrumbs>
                  <Breadcrumbs.Item as={Link} to="/">
                    首页
                  </Breadcrumbs.Item>
                  {workspace.data ? (
                    <Breadcrumbs.Item as={Link} to={`/workspaces/${workspace.data.id}`}>
                      {workspace.data.name}
                    </Breadcrumbs.Item>
                  ) : (
                    <Breadcrumbs.Item>平台</Breadcrumbs.Item>
                  )}
                  <Breadcrumbs.Item
                    as={Link}
                    to={`/workspaces/${workspace.data?.id ?? ''}/shared-resources`}
                  >
                    共享资源
                  </Breadcrumbs.Item>
                </Breadcrumbs>
              </PageHeader.Breadcrumbs>
              <PageHeader.TitleArea>
                <PageHeader.Title as="h1">{resource.data.name}</PageHeader.Title>
              </PageHeader.TitleArea>
              <PageHeader.TrailingVisual>
                {isPlatform ? (
                  <Label variant="attention">平台资源</Label>
                ) : (
                  <Label variant="done">空间资源</Label>
                )}
              </PageHeader.TrailingVisual>
              {resource.data.description ? (
                <PageHeader.Description>{resource.data.description}</PageHeader.Description>
              ) : (
                <PageHeader.Description>这个共享资源还没有填写说明。</PageHeader.Description>
              )}
              <PageHeader.Actions>
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
              </PageHeader.Actions>
            </PageHeader>
          )}
        </AsyncState>

        <PrimerListCard title="版本">
          <AsyncState
            loading={resource.loading}
            error={normalizeError(resource.error)}
            empty={resource.data !== undefined && versions.length === 0}
            emptyText="这个共享资源还没有已发布版本。"
            emptyDescription={
              canPublish ? '发布首个版本后，Project 才能引用这个共享资源。' : undefined
            }
            emptyAction={canPublish ? '发布版本' : null}
            onEmptyAction={canPublish ? () => setPublishing(true) : undefined}
          >
            <table className={styles.table}>
              <thead>
                <tr>
                  {(['版本', '说明', '文件数', '总大小', '发布时间'] as const).map((h) => (
                    <th key={h} className={styles.th}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {versions.map((version: SharedResourceVersion) => (
                  <tr key={version.id} className={styles.row}>
                    <td className={styles.td}>
                      <Link
                        to={`/shared-resource-versions/${version.id}`}
                        style={{ fontWeight: 500 }}
                      >
                        {version.label}
                      </Link>
                    </td>
                    <td className={styles.td}>
                      <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
                        {version.description || '—'}
                      </Text>
                    </td>
                    <td className={styles.td}>
                      <PrimerMono>{String(version.file_count)}</PrimerMono>
                    </td>
                    <td className={styles.td}>{formatBytes(version.total_size)}</td>
                    <td className={styles.td}>
                      <PrimerRelativeTime value={version.created_at} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </AsyncState>
        </PrimerListCard>

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
