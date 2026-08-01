import { List, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import type { Activity, ActivityPage } from '../../api/types'
import { AsyncSection } from '../common/AsyncSection'
import { RelativeTime } from '../common/Mono'
import { describeAction, describeDetail, showsTarget, targetPath } from './actions'

interface Props {
  page: ActivityPage | undefined
  loading: boolean
  error: Error | undefined
  emptyText?: string
}

/**
 * 活动流。
 *
 * 一条活动是一句话：**谁 · 做了什么 · 对什么 · 什么时候**。
 * 用 List 而不是 Table——每条的信息量不一样（有的带 detail，有的不带），
 * 塞进固定列里会有大片空白，而且这里不需要排序和筛选。
 */
export function ActivityFeed({ page, loading, error, emptyText }: Props) {
  return (
    <AsyncSection
      loading={loading}
      error={error}
      empty={page?.total === 0}
      emptyText={emptyText ?? '还没有活动记录'}
    >
      <List
        size="small"
        dataSource={page?.items ?? []}
        renderItem={(activity) => <ActivityLine activity={activity} />}
      />
    </AsyncSection>
  )
}

function ActivityLine({ activity }: { activity: Activity }) {
  const path = targetPath(activity)
  // 对象已经不在了链接就会 404，所以只有能定位到的才做成链接。
  // 文字本身已经把事情说清楚了，少个链接不影响读。
  const target: ReactNode = !showsTarget(activity) ? null : path ? (
    <Link to={path}>{activity.target_name}</Link>
  ) : (
    <Typography.Text strong>{activity.target_name}</Typography.Text>
  )
  const detail = describeDetail(activity)

  return (
    <List.Item>
      <div style={{ display: 'flex', width: '100%', gap: 12, alignItems: 'baseline' }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Typography.Text strong>{activity.actor_name}</Typography.Text>{' '}
          <Typography.Text type="secondary">{describeAction(activity.action)}</Typography.Text>{' '}
          {target}
          {detail && <Typography.Text type="secondary">{`（${detail}）`}</Typography.Text>}
        </div>
        <RelativeTime value={activity.created_at} />
      </div>
    </List.Item>
  )
}
