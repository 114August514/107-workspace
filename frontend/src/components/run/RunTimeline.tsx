import { AlertFillIcon, CheckCircleFillIcon, ClockIcon, DotFillIcon } from '@primer/octicons-react'
import { Text } from '@primer/react'

import type { RunEvent, RunEventType } from '../../api/types'
import { formatTime } from '../../utils/format'
import styles from './run.module.css'

const EVENT_LABEL: Record<RunEventType, string> = {
  created: '创建 Run',
  submitted: '提交调度任务',
  submit_failed: '提交失败',
  started: '开始执行',
  finished: '执行结束',
  cancel_requested: '请求取消',
  cancelled: '已取消',
  artifact_collected: '收集运行产物',
  artifact_missing: '运行产物缺失',
  error: '异常',
}

function EventIcon({ type }: { type: RunEventType }) {
  if (type === 'submit_failed' || type === 'error' || type === 'artifact_missing') {
    return <AlertFillIcon size={16} aria-hidden />
  }
  if (type === 'finished' || type === 'artifact_collected') {
    return <CheckCircleFillIcon size={16} aria-hidden />
  }
  if (type === 'created') return <ClockIcon size={16} aria-hidden />
  return <DotFillIcon size={16} aria-hidden />
}

/** 平台执行事件；stdout / stderr 在独立日志表面展示。 */
export function RunTimeline({ events }: { events: RunEvent[] }) {
  if (events.length === 0) {
    return <Text className={styles.muted}>这个 Run 还没有执行事件。</Text>
  }

  return (
    <ol className={styles.timeline} aria-label="Run 执行事件">
      {events.map((event) => (
        <li key={event.id} className={styles.timelineItem}>
          <span className={styles.timelineIcon}>
            <EventIcon type={event.type} />
          </span>
          <div className={styles.timelineBody}>
            <div className={styles.timelineHeading}>
              <strong>{EVENT_LABEL[event.type]}</strong>
              <time dateTime={event.created_at} title={formatTime(event.created_at)}>
                {formatTime(event.created_at)}
              </time>
            </div>
            <Text as="p" className={styles.timelineMessage}>
              {event.message}
            </Text>
          </div>
        </li>
      ))}
    </ol>
  )
}
