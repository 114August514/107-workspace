import { PencilIcon, PlusIcon } from '@primer/octicons-react'
import { Button, Label, Text } from '@primer/react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { can } from '../api/types'
import type { SharedResourceDetail, SharedResourceVersion, Workspace } from '../api/types'
import { useAsync } from '../api/useAsync'
import { PrimerAsyncSection } from '../components/primer/PrimerAsyncSection'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import { PrimerMono, PrimerRelativeTime } from '../components/primer/PrimerMono'
import { PrimerPageHeader } from '../components/primer/PrimerPageHeader'
import { PrimerStack } from '../components/primer/PrimerStack'
import { EditSharedResourceModal } from '../components/sharedresource/EditSharedResourceModal'
import { PublishVersionModal } from '../components/sharedresource/PublishVersionModal'
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

  return (
    <PrimerStack gap="large">
      <PrimerAsyncSection loading={resource.loading} error={resource.error}>
        {resource.data && (
          <PrimerPageHeader
            breadcrumb={[
              { title: <Link to="/">首页</Link> },
              workspace.data
                ? {
                    title: (
                      <Link to={`/workspaces/${workspace.data.id}`}>{workspace.data.name}</Link>
                    ),
                  }
                : { title: '平台' },
              { title: resource.data.name },
            ]}
            title={resource.data.name}
            tags={
              isPlatform ? (
                <Label variant="attention">平台资源</Label>
              ) : (
                <Label variant="done">空间资源</Label>
              )
            }
            description={resource.data.description || '这个 Shared Resource 还没有填写说明'}
            actions={
              <>
                {canManage && (
                  <Button leadingVisual={PencilIcon} onClick={() => setEditing(true)}>
                    修改
                  </Button>
                )}
                {canPublish && (
                  <Button
                    variant="primary"
                    leadingVisual={PlusIcon}
                    onClick={() => setPublishing(true)}
                  >
                    发布新版本
                  </Button>
                )}
              </>
            }
          />
        )}
      </PrimerAsyncSection>

      <PrimerListCard title="版本">
        <PrimerAsyncSection
          loading={resource.loading}
          error={resource.error}
          empty={(resource.data?.versions ?? []).length === 0}
          emptyText="还没有发布过版本。点击右上角「发布新版本」上传文件。"
        >
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {(['版本', '说明', '文件数', '总大小', '发布时间'] as const).map((h) => (
                  <th
                    key={h}
                    style={{
                      textAlign: 'left',
                      padding: '8px 16px',
                      fontSize: 14,
                      fontWeight: 600,
                      color: 'var(--fgColor-muted)',
                      borderBottom: '1px solid var(--borderColor-default)',
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(resource.data?.versions ?? []).map((version: SharedResourceVersion) => (
                <tr
                  key={version.id}
                  style={{ borderBottom: '1px solid var(--borderColor-default)' }}
                >
                  <td style={{ padding: '8px 16px' }}>
                    <Link
                      to={`/shared-resource-versions/${version.id}`}
                      style={{ fontWeight: 500 }}
                    >
                      {version.label}
                    </Link>
                  </td>
                  <td style={{ padding: '8px 16px' }}>
                    <Text size="small">{version.description}</Text>
                  </td>
                  <td style={{ padding: '8px 16px' }}>
                    <PrimerMono>{String(version.file_count)}</PrimerMono>
                  </td>
                  <td style={{ padding: '8px 16px' }}>
                    <Text size="small">{formatBytes(version.total_size)}</Text>
                  </td>
                  <td style={{ padding: '8px 16px' }}>
                    <PrimerRelativeTime value={version.created_at} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </PrimerAsyncSection>
      </PrimerListCard>

      {resource.data?.versions.length === 0 && !isPlatform && (
        <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
          资源创建后内容为空，需发布首个版本才能在 Run 中引用。
        </Text>
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
  )
}
