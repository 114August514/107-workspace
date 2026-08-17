import { PlusOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Tabs, Tag } from 'antd'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { can } from '../api/types'
import type { ActivityPage, LegacyWorkspaceContext, ProjectPage } from '../api/types'
import { useAsync } from '../api/useAsync'
import { ActivityFeed } from '../components/activity/ActivityFeed'
import { AsyncSection } from '../components/common/AsyncSection'
import { RoleTag } from '../components/common/RoleTag'
import { ListCard } from '../components/layout/ListCard'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { CreateProjectModal } from '../components/project/CreateProjectModal'
import { ProjectTable } from '../components/project/ProjectTable'
import { DefaultEnvironmentPicker } from '../components/workspace/DefaultEnvironmentPicker'
import { EntitlementPanel } from '../components/workspace/EntitlementPanel'
import { VariablePanel } from '../components/workspace/VariablePanel'
import { tablePagination } from '../utils/pagination'

/** Bounded frontend compatibility for persisted Workspace links and downstream data. */
export function LegacyWorkspacePage() {
  const { workspaceId = '' } = useParams()
  const workspace = useAsync<LegacyWorkspaceContext>(
    () => api.getLegacyWorkspaceContext(workspaceId),
    [workspaceId],
  )
  const [page, setPage] = useState(1)
  const projects = useAsync<ProjectPage>(
    () => api.listProjects(workspaceId, { page }),
    [workspaceId, page],
  )
  const activities = useAsync<ActivityPage>(
    () => api.listWorkspaceActivities(workspaceId, { page_size: 20 }),
    [workspaceId],
  )
  const [creating, setCreating] = useState(false)

  return (
    <Stack gap="large">
      <Alert
        type="warning"
        showIcon
        message="旧 Workspace 下游兼容视图"
        description="此入口只保留尚未迁移的 Project、配置、环境、权益与活动访问；User Group 治理请使用 User Group 页面。"
      />

      <AsyncSection loading={workspace.loading} error={workspace.error}>
        {workspace.data && (
          <PageHeader
            breadcrumb={[{ title: <Link to="/">首页</Link> }, { title: workspace.data.name }]}
            title={workspace.data.name}
            tags={
              <>
                <Tag>Workspace 兼容</Tag>
                <RoleTag role={workspace.data.role} />
              </>
            }
            description="尚未迁移的 Workspace 下游数据入口"
            actions={
              can(workspace.data, 'project.create') && (
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
                  创建 Workspace Project
                </Button>
              )
            }
          />
        )}
      </AsyncSection>

      <Tabs
        defaultActiveKey="projects"
        items={[
          {
            key: 'projects',
            label: 'Workspace Project（兼容）',
            children: (
              <ListCard>
                <AsyncSection
                  loading={projects.loading}
                  error={projects.error}
                  empty={projects.data?.total === 0}
                  emptyText="这个旧 Workspace 还没有 Project"
                >
                  <ProjectTable
                    projects={projects.data?.items ?? []}
                    pagination={tablePagination(projects.data, setPage)}
                  />
                </AsyncSection>
              </ListCard>
            ),
          },
          {
            key: 'environment',
            label: 'Workspace 默认环境（兼容）',
            children: (
              <Card>
                {workspace.data && (
                  <DefaultEnvironmentPicker
                    workspace={workspace.data}
                    onChanged={workspace.reload}
                  />
                )}
              </Card>
            ),
          },
          {
            key: 'config',
            label: 'Workspace 变量与 Secret（兼容）',
            children: <Card>{workspace.data && <VariablePanel workspace={workspace.data} />}</Card>,
          },
          {
            key: 'activities',
            label: 'Workspace 活动（兼容）',
            children: (
              <ListCard padded>
                <ActivityFeed
                  page={activities.data}
                  loading={activities.loading}
                  error={activities.error}
                  emptyText="这个旧 Workspace 还没有活动记录"
                />
              </ListCard>
            ),
          },
          {
            key: 'entitlements',
            label: 'Workspace 资源权益（兼容）',
            children: (
              <Card>
                <EntitlementPanel workspaceId={workspaceId} />
              </Card>
            ),
          },
        ]}
      />

      <CreateProjectModal
        open={creating}
        workspaceId={workspaceId}
        onClose={() => setCreating(false)}
        onCreated={() => projects.reload()}
      />
    </Stack>
  )
}
