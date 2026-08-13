import { PlusOutlined } from '@ant-design/icons'
import { Button, Space, Tabs } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { SharedResource, Workspace } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncSection } from '../common/AsyncSection'
import { ListCard } from '../layout/ListCard'
import { CreateSharedResourceModal } from './CreateSharedResourceModal'
import { SharedResourceTable } from './SharedResourceTable'

interface Props {
  workspace: Workspace
}

export function SharedResourcePanel({ workspace }: Props) {
  const navigate = useNavigate()
  // 创建资源需要 manage 能力；version.create 由详情页的发布按钮再单独判断。
  const canManage = can(workspace, 'shared_resource.manage')

  const ownResources = useAsync<SharedResource[]>(
    () => api.listWorkspaceSharedResources(workspace.id),
    [workspace.id],
  )
  const platformResources = useAsync<SharedResource[]>(() => api.listPlatformSharedResources(), [])
  const [creating, setCreating] = useState(false)

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      {canManage && (
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
            创建 Shared Resource
          </Button>
        </Space>
      )}

      <Tabs
        defaultActiveKey="own"
        items={[
          {
            key: 'own',
            label: '本空间',
            children: (
              <ListCard>
                <AsyncSection
                  loading={ownResources.loading}
                  error={ownResources.error}
                  empty={(ownResources.data ?? []).length === 0}
                  emptyText="这个 Workspace 还没有 Shared Resource"
                >
                  <SharedResourceTable resources={ownResources.data ?? []} />
                </AsyncSection>
              </ListCard>
            ),
          },
          {
            key: 'platform',
            label: '平台公共',
            children: (
              <ListCard>
                <AsyncSection
                  loading={platformResources.loading}
                  error={platformResources.error}
                  empty={(platformResources.data ?? []).length === 0}
                  emptyText="平台还没有公共资源"
                >
                  <SharedResourceTable resources={platformResources.data ?? []} />
                </AsyncSection>
              </ListCard>
            ),
          },
        ]}
      />

      <CreateSharedResourceModal
        open={creating}
        workspaceId={workspace.id}
        onClose={() => setCreating(false)}
        onCreated={(resource) => {
          // 成功提示由 Modal 自己负责（和 CreateProjectModal 一致），这里只刷新列表并跳详情。
          ownResources.reload()
          navigate(`/shared-resources/${resource.id}`)
        }}
      />
    </Space>
  )
}
