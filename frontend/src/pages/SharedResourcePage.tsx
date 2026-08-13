import { EditOutlined, PlusOutlined } from '@ant-design/icons'
import { Button, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { can } from '../api/types'
import type { SharedResourceDetail, SharedResourceVersion, Workspace } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncSection } from '../components/common/AsyncSection'
import { Mono, RelativeTime } from '../components/common/Mono'
import { ListCard } from '../components/layout/ListCard'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { EditSharedResourceModal } from '../components/sharedresource/EditSharedResourceModal'
import { PublishVersionModal } from '../components/sharedresource/PublishVersionModal'
import { field } from '../utils/field'
import { formatBytes } from '../utils/format'

const versionColumns: ColumnsType<SharedResourceVersion> = [
  {
    title: '版本',
    dataIndex: field<SharedResourceVersion>('label'),
    width: 100,
    render: (label: string, version) => (
      <Link to={`/shared-resource-versions/${version.id}`} style={{ fontWeight: 500 }}>
        {label}
      </Link>
    ),
  },
  { title: '说明', dataIndex: field<SharedResourceVersion>('description'), ellipsis: true },
  {
    title: '文件数',
    dataIndex: field<SharedResourceVersion>('file_count'),
    width: 90,
    render: (count: number) => <Mono>{String(count)}</Mono>,
  },
  {
    title: '总大小',
    dataIndex: field<SharedResourceVersion>('total_size'),
    width: 110,
    render: formatBytes,
  },
  {
    title: '发布时间',
    dataIndex: field<SharedResourceVersion>('created_at'),
    width: 130,
    render: (value: string) => <RelativeTime value={value} />,
  },
]

export function SharedResourcePage() {
  const { resourceId = '' } = useParams()
  const [token, setToken] = useState(0)
  const bump = () => setToken((value) => value + 1)

  const resource = useAsync<SharedResourceDetail>(
    () => api.getSharedResource(resourceId),
    [resourceId, token],
  )
  // 平台资源没有 owner_workspace_id，按只读处理；空间资源需要 owner 的能力清单
  // 来决定显不显示编辑/发布入口。真正的授权仍由后端逐请求校验。
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
    <Stack gap="large">
      <AsyncSection loading={resource.loading} error={resource.error}>
        {resource.data && (
          <PageHeader
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
            tags={isPlatform ? <Tag color="purple">平台资源</Tag> : <Tag>空间资源</Tag>}
            description={resource.data.description || '这个 Shared Resource 还没有填写说明'}
            actions={
              <>
                {canManage && (
                  <Button icon={<EditOutlined />} onClick={() => setEditing(true)}>
                    修改
                  </Button>
                )}
                {canPublish && (
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => setPublishing(true)}
                  >
                    发布新版本
                  </Button>
                )}
              </>
            }
          />
        )}
      </AsyncSection>

      <ListCard title="版本">
        <AsyncSection
          loading={resource.loading}
          error={resource.error}
          empty={(resource.data?.versions ?? []).length === 0}
          emptyText="还没有发布过版本。点击右上角「发布新版本」上传文件。"
        >
          <Table
            rowKey="id"
            size="small"
            dataSource={resource.data?.versions ?? []}
            columns={versionColumns}
            pagination={false}
          />
        </AsyncSection>
      </ListCard>

      {resource.data?.versions.length === 0 && !isPlatform && (
        <Typography.Text type="secondary">
          资源创建后内容为空，需发布首个版本才能在 Run 中引用。
        </Typography.Text>
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
    </Stack>
  )
}
