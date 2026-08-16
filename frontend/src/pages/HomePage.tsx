import { PlusOutlined } from '@ant-design/icons'
import { Button } from 'antd'
import { useState } from 'react'

import { api } from '../api/client'
import type { Home } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncSection } from '../components/common/AsyncSection'
import { ListCard } from '../components/layout/ListCard'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { ProjectTable } from '../components/project/ProjectTable'
import { RunTable } from '../components/run/RunTable'
import { CreateUserGroupModal } from '../components/workspace/CreateUserGroupModal'
import { InvitationList } from '../components/workspace/InvitationList'
import { UserGroupTable } from '../components/workspace/UserGroupTable'

/** 个人首页：我的 User Group、最近的 Project 和最近发起的 Run。 */
export function HomePage({ username }: { username: string }) {
  const home = useAsync<Home>(() => api.home(), [username])
  const [creating, setCreating] = useState(false)

  return (
    <Stack gap="large">
      <PageHeader
        title={home.data ? `${home.data.user.display_name}，欢迎回来` : '首页'}
        description="从这里进入 Project，配置运行方案，提交计算作业——不需要自己写 sbatch。"
        actions={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
            创建 User Group
          </Button>
        }
      />

      {/* 邀请排在空间列表前面：它是需要用户做决定的事，
          而下面几块只是「已经有什么」。没有邀请时整块不渲染。 */}
      <InvitationList username={username} onResponded={() => home.reload()} />

      <ListCard title="我的 User Group">
        <AsyncSection
          loading={home.loading}
          error={home.error}
          empty={(home.data?.user_groups ?? []).length === 0}
        >
          <UserGroupTable userGroups={home.data?.user_groups ?? []} />
        </AsyncSection>
      </ListCard>

      <ListCard title="最近使用的 Project">
        <AsyncSection
          loading={home.loading}
          error={home.error}
          empty={(home.data?.recent_projects ?? []).length === 0}
          emptyText="还没有 Project。进入一个 User Group 创建第一个吧。"
        >
          <ProjectTable projects={home.data?.recent_projects ?? []} />
        </AsyncSection>
      </ListCard>

      <ListCard title="最近提交的 Run">
        <AsyncSection
          loading={home.loading}
          error={home.error}
          empty={(home.data?.recent_runs ?? []).length === 0}
          emptyText="还没有提交过 Run"
        >
          <RunTable runs={home.data?.recent_runs ?? []} />
        </AsyncSection>
      </ListCard>

      <CreateUserGroupModal
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={() => home.reload()}
      />
    </Stack>
  )
}
