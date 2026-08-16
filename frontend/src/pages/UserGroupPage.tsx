import { PlusOutlined } from '@ant-design/icons'
import { Button, Card, Tabs, Tag } from 'antd'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { can } from '../api/types'
import type { ActivityPage, LegacyWorkspaceContext, ProjectPage, UserGroup } from '../api/types'
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
import { MemberPanel } from '../components/workspace/MemberPanel'
import { VariablePanel } from '../components/workspace/VariablePanel'
import { tablePagination } from '../utils/pagination'

/** User Group governance surface; #21 owns the visual-system migration. */
export function UserGroupPage() {
  const { userGroupId = '' } = useParams()
  const userGroup = useAsync<UserGroup>(() => api.getUserGroup(userGroupId), [userGroupId])
  const legacyContext = useAsync<LegacyWorkspaceContext>(
    () => api.getLegacyWorkspaceContext(userGroupId),
    [userGroupId],
  )
  const [page, setPage] = useState(1)
  const projects = useAsync<ProjectPage>(
    () => api.listProjects(userGroupId, { page }),
    [userGroupId, page],
  )
  const activities = useAsync<ActivityPage>(
    () => api.listWorkspaceActivities(userGroupId, { page_size: 20 }),
    [userGroupId],
  )
  const [creating, setCreating] = useState(false)

  return (
    <Stack gap="large">
      <AsyncSection loading={userGroup.loading} error={userGroup.error}>
        {userGroup.data && (
          <PageHeader
            breadcrumb={[{ title: <Link to="/">首页</Link> }, { title: userGroup.data.name }]}
            title={userGroup.data.name}
            tags={
              <>
                <Tag color="blue">User Group</Tag>
                <RoleTag role={userGroup.data.role} />
              </>
            }
            description={userGroup.data.description || '这个 User Group 还没有填写说明'}
            actions={
              can(userGroup.data, 'project.create') && (
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
                  emptyText="这个 User Group 还没有 Project"
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
                {legacyContext.data && (
                  <DefaultEnvironmentPicker
                    workspace={legacyContext.data}
                    onChanged={legacyContext.reload}
                  />
                )}
              </Card>
            ),
          },
          {
            key: 'members',
            label: '成员',
            children: <Card>{userGroup.data && <MemberPanel workspace={userGroup.data} />}</Card>,
          },
          {
            key: 'config',
            label: '变量与 Secret',
            children: <Card>{userGroup.data && <VariablePanel workspace={userGroup.data} />}</Card>,
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
                  emptyText="这个 User Group 还没有活动记录"
                />
              </ListCard>
            ),
          },
          {
            key: 'entitlements',
            label: '资源权益',
            children: (
              <Card>
                <EntitlementPanel workspaceId={userGroupId} />
              </Card>
            ),
          },
        ]}
      />

      <CreateProjectModal
        open={creating}
        workspaceId={userGroupId}
        onClose={() => setCreating(false)}
        onCreated={() => projects.reload()}
      />
    </Stack>
  )
}
