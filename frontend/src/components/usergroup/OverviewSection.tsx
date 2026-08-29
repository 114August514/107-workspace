import { Link as RouterLink, useOutletContext } from 'react-router-dom'

import { api } from '../../api/client'
import { toAsyncError, type AsyncErrorView } from '../../api/errors'
import type { Member } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { ActivityList } from '../activity/ActivityList'
import { AsyncState } from '../common/AsyncState'
import { PrimerListCard } from '../primer/PrimerListCard'
import { formatTime } from '../../utils/format'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { loadGroupEnvironments, loadGroupProjects, loadGroupSharedResources } from './groupAssets'
import { userGroupRoleLabel } from './userGroupCopy'
import styles from './overview.module.css'

export function OverviewSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const members = useAsync<Member[]>(() => api.listMembers(userGroup.id), [userGroup.id])
  const activities = useAsync(
    () => api.listUserGroupActivities(userGroup.id, { page_size: 10 }),
    [userGroup.id],
  )
  const projects = useAsync(() => loadGroupProjects(userGroup.id), [userGroup.id])
  const resources = useAsync(() => loadGroupSharedResources(userGroup.id), [userGroup.id])
  const environments = useAsync(() => loadGroupEnvironments(userGroup.id), [userGroup.id])

  const creator = members.data?.find((member) => member.user_id === userGroup.created_by_id)

  return (
    <div className={styles.overview}>
      <section className={styles.section} aria-labelledby="user-group-overview-title">
        <h2 id="user-group-overview-title" className={styles.sectionTitle}>
          基本信息
        </h2>
        <AsyncState
          loading={members.loading && !members.data}
          loadingText="正在加载基本信息…"
          error={toAsyncError(members.error)}
          onRetry={members.reload}
        >
          <dl className={styles.infoGrid}>
            <dt>创建者</dt>
            <dd>{creator?.display_name || creator?.username || userGroup.created_by_id}</dd>
            <dt>创建时间</dt>
            <dd>{userGroup.created_at ? formatTime(userGroup.created_at) : '—'}</dd>
            <dt>我的角色</dt>
            <dd>{userGroupRoleLabel(userGroup.role)}</dd>
            <dt>成员</dt>
            <dd>{members.data ? `${members.data.length} 位` : '—'}</dd>
          </dl>
        </AsyncState>
      </section>

      <AssetSummaryCard
        title="Project"
        count={projects.data?.items.length}
        truncated={projects.data?.truncated}
        loading={projects.loading}
        error={toAsyncError(projects.error)}
        onRetry={projects.reload}
        to="projects"
      />
      <AssetSummaryCard
        title="共享资源"
        count={resources.data?.length}
        loading={resources.loading}
        error={toAsyncError(resources.error)}
        onRetry={resources.reload}
        to="shared-resources"
      />
      <AssetSummaryCard
        title="运行环境"
        count={environments.data?.length}
        loading={environments.loading}
        error={toAsyncError(environments.error)}
        onRetry={environments.reload}
        to="environments"
      />

      <PrimerListCard
        title="近期活动"
        extra={
          <RouterLink className={styles.cardLink} to="members">
            查看成员
          </RouterLink>
        }
        padded
      >
        <AsyncState
          loading={activities.loading && !activities.data}
          loadingText="正在加载近期活动…"
          error={toAsyncError(activities.error)}
          onRetry={activities.reload}
          empty={!activities.loading && activities.data?.items.length === 0}
          emptyText="暂无活动记录。"
          emptyDescription="成员变动、版本与 Run 操作会出现在这里。"
        >
          {activities.data ? <ActivityList activities={activities.data.items} /> : null}
        </AsyncState>
      </PrimerListCard>
    </div>
  )
}

function AssetSummaryCard({
  title,
  count,
  truncated,
  loading,
  error,
  onRetry,
  to,
}: {
  title: string
  count?: number
  truncated?: boolean
  loading: boolean
  error: AsyncErrorView | undefined
  onRetry: () => void
  to: string
}) {
  return (
    <PrimerListCard
      title={title}
      extra={
        <RouterLink className={styles.cardLink} to={to}>
          查看全部
        </RouterLink>
      }
      padded
    >
      <AsyncState
        loading={loading && count === undefined}
        loadingText={`正在加载${title}…`}
        error={error}
        onRetry={onRetry}
        empty={!loading && count === 0}
        emptyText={`这个 User Group 还没有${title}。`}
      >
        {count !== undefined ? (
          <p className={styles.countLine}>
            {truncated ? '超过 ' : ''}
            {count} 个条目
            {truncated ? '（列表过长，仅统计前一部分）' : ''}
          </p>
        ) : null}
      </AsyncState>
    </PrimerListCard>
  )
}
