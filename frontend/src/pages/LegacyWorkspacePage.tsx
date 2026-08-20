import { PlusOutlined } from '@ant-design/icons'
import { Button, Card, Tabs, Tag } from 'antd'
import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

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
import { SharedResourcePanel } from '../components/sharedresource/SharedResourcePanel'
import { tablePagination } from '../utils/pagination'

/** Bounded frontend compatibility for persisted Workspace links and downstream data. */
export function LegacyWorkspacePage() {
  const { workspaceId = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  // 深链路：/workspaces/:id/shared-resources 初始选中「共享资源」tab，其余落到默认。
  // 其余 tab 没有独立路由，选中态必须由本地 state 持有——activeKey 只从 URL 推导的话，
  // 点击无路由的 tab 导航回基础路由后 activeKey 永远停在 projects，tab 像点不动。
  const [selectedTab, setSelectedTab] = useState(() =>
    location.pathname.endsWith('/shared-resources') ? 'shared-resources' : 'projects',
  )
  // 空间之间跳转时按新 URL 重新推导选中 tab，避免沿用上一个空间的选中态。
  useEffect(() => {
    setSelectedTab(
      location.pathname.endsWith('/shared-resources') ? 'shared-resources' : 'projects',
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId])
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
        activeKey={selectedTab}
        onChange={(key) => {
          setSelectedTab(key)
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
            key: 'shared-resources',
            label: '共享资源',
            children: (
              <Card>{workspace.data && <SharedResourcePanel workspace={workspace.data} />}</Card>
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
                <EntitlementPanel />
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
