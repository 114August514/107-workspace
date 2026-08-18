import { PlusOutlined } from '@ant-design/icons'
import { Button, Card, Tabs, Tag } from 'antd'
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
      <AsyncSection loading={workspace.loading} error={workspace.error}>
        {workspace.data && (
          <PageHeader
            breadcrumb={[
              { title: <Link to="/">首页</Link> },
              {
                title: workspace.data.kind === 'personal' ? '个人资源' : workspace.data.name,
              },
            ]}
            title={workspace.data.kind === 'personal' ? '个人资源' : workspace.data.name}
            tags={
              <>
                <Tag color={workspace.data.kind === 'personal' ? undefined : 'blue'}>
                  {workspace.data.kind === 'personal' ? '个人资源' : 'User Group'}
                </Tag>
                <RoleTag role={workspace.data.role} />
              </>
            }
            description={
              workspace.data.kind === 'personal'
                ? '查看已有的个人 Project、运行环境与配置'
                : '查看这个 User Group 的 Project、运行环境与配置'
            }
            actions={
              workspace.data.kind === 'collaborative' &&
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
        defaultActiveKey="projects"
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
                  emptyText="还没有 Project"
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
            label: '默认运行环境',
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
            label: 'Variable 与 Secret',
            children: <Card>{workspace.data && <VariablePanel workspace={workspace.data} />}</Card>,
          },
          {
            key: 'activities',
            label: '活动',
            children: (
              <ListCard padded>
                <ActivityFeed
                  page={activities.data}
                  loading={activities.loading}
                  error={activities.error}
                  emptyText="还没有活动记录"
                />
              </ListCard>
            ),
          },
          {
            key: 'entitlements',
            label: '可用算力',
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
