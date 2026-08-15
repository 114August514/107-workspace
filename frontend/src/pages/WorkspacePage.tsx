import { PlusOutlined } from '@ant-design/icons'
import { Button, Card, Tabs, Tag } from 'antd'
import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { can } from '../api/types'
import type { ActivityPage, ProjectPage, Workspace } from '../api/types'
import { useAsync } from '../api/useAsync'
import { ActivityFeed } from '../components/activity/ActivityFeed'
import { AsyncSection } from '../components/common/AsyncSection'
import { RoleTag } from '../components/common/RoleTag'
import { ListCard } from '../components/layout/ListCard'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { tablePagination } from '../utils/pagination'
import { CreateProjectModal } from '../components/project/CreateProjectModal'
import { ProjectTable } from '../components/project/ProjectTable'
import { DefaultEnvironmentPicker } from '../components/workspace/DefaultEnvironmentPicker'
import { EntitlementPanel } from '../components/workspace/EntitlementPanel'
import { MemberPanel } from '../components/workspace/MemberPanel'
import { VariablePanel } from '../components/workspace/VariablePanel'
import { SharedResourcePanel } from '../components/sharedresource/SharedResourcePanel'

export function WorkspacePage() {
  const { workspaceId = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  // 深链路：/workspaces/:id/shared-resources 选中「共享资源」tab，其余落到默认。
  // tab 切换时同步 URL，让刷新/收藏/复制链接保留当前 tab。
  const activeTab = location.pathname.endsWith('/shared-resources')
    ? 'shared-resources'
    : 'projects'
  const workspace = useAsync<Workspace>(() => api.getWorkspace(workspaceId), [workspaceId])
  const [page, setPage] = useState(1)
  const projects = useAsync<ProjectPage>(
    () => api.listProjects(workspaceId, { page }),
    [workspaceId, page],
  )
  const [creating, setCreating] = useState(false)
  const activities = useAsync<ActivityPage>(
    () => api.listWorkspaceActivities(workspaceId, { page_size: 20 }),
    [workspaceId],
  )

  return (
    <Stack gap="large">
      <AsyncSection loading={workspace.loading} error={workspace.error}>
        {workspace.data && (
          <PageHeader
            breadcrumb={[{ title: <Link to="/">首页</Link> }, { title: workspace.data.name }]}
            title={workspace.data.name}
            tags={
              <>
                {workspace.data.kind === 'personal' ? (
                  <Tag>个人空间</Tag>
                ) : (
                  <Tag color="blue">协作空间</Tag>
                )}
                {workspace.data.role && <RoleTag role={workspace.data.role} />}
              </>
            }
            description={workspace.data.description || '这个 Workspace 还没有填写说明'}
            actions={
              can(workspace.data, 'project.create') && (
                <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
                  创建 Project
                </Button>
              )
            }
          />
        )}
      </AsyncSection>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          // 只有共享资源 tab 有独立深链路；其余 tab 回到 Workspace 基础路由。
          navigate(key === 'shared-resources' ? `shared-resources` : `.`, {
            replace: true,
          })
        }}
        items={[
          {
            key: 'projects',
            label: 'Project',
            children: (
              <ListCard>
                <AsyncSection
                  loading={projects.loading}
                  error={projects.error}
                  empty={projects.data?.total === 0}
                  emptyText="这个 Workspace 还没有 Project"
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
            label: '默认环境',
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
            key: 'members',
            label: '成员',
            children: <Card>{workspace.data && <MemberPanel workspace={workspace.data} />}</Card>,
          },
          {
            key: 'shared-resources',
            label: '共享资源',
            children: (
              <Card>{workspace.data && <SharedResourcePanel workspace={workspace.data} />}</Card>
            ),
          },
          {
            key: 'config',
            label: '变量与 Secret',
            children: <Card>{workspace.data && <VariablePanel workspace={workspace.data} />}</Card>,
          },
          {
            key: 'activities',
            label: '近期活动',
            children: (
              <ListCard padded>
                <ActivityFeed
                  page={activities.data}
                  loading={activities.loading}
                  error={activities.error}
                  emptyText="这个 Workspace 还没有活动记录"
                />
              </ListCard>
            ),
          },
          {
            key: 'entitlements',
            label: '资源权益',
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
