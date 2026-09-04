import { Link as RouterLink } from 'react-router-dom'

import type { Activity } from '../../api/types'
import { formatRelative, formatTime } from '../../utils/format'
import { describeAction, showsTarget, targetPath } from './actions'
import styles from './ActivityList.module.css'

interface Props {
  activities: Activity[]
}

/** User Group 概览使用的活动列表；Project 页面仍由 antd ActivityFeed 承载至 #20。 */
export function ActivityList({ activities }: Props) {
  return (
    <ul className={styles.list} aria-label="近期活动">
      {activities.map((activity) => {
        const path = targetPath(activity)
        const actionText = (
          <>
            {describeAction(activity.action)}
            {showsTarget(activity) ? ` ${activity.target_name}` : null}
          </>
        )
        return (
          <li key={activity.id} className={styles.item}>
            {path ? (
              <RouterLink className={styles.action} to={path}>
                {actionText}
              </RouterLink>
            ) : (
              <span className={styles.action}>{actionText}</span>
            )}
            <span className={styles.actor}>{activity.actor_name}</span>
            <time
              className={styles.time}
              dateTime={activity.created_at}
              title={formatTime(activity.created_at)}
            >
              {formatRelative(activity.created_at)}
            </time>
          </li>
        )
      })}
    </ul>
  )
}
