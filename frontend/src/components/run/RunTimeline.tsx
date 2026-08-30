import { AlertFillIcon, CheckCircleFillIcon, DotFillIcon, StopIcon } from '@primer/octicons-react'
import { Text } from '@primer/react'

import type { RunDetail, RunEvent, RunEventType } from '../../api/types'
import { formatClockTime, formatTime } from '../../utils/format'
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

function EventVisual({ type }: { type: RunEventType }) {
  let Icon = CheckCircleFillIcon
  let label = '已完成'
  if (type === 'submit_failed' || type === 'error' || type === 'artifact_missing') {
    Icon = AlertFillIcon
    label = '异常'
  } else if (type === 'cancel_requested') {
    Icon = DotFillIcon
    label = '取消中'
  } else if (type === 'cancelled') {
    Icon = StopIcon
    label = '已取消'
  }
  return (
    <span className={styles.timelineIcon} role="img" aria-label={label}>
      <Icon size={16} aria-hidden />
    </span>
  )
}

function eventDescription(event: RunEvent, detail: RunDetail): string {
  const { run, snapshot } = detail
  switch (event.type) {
    case 'created':
      return '已固定本次运行快照'
    case 'submitted': {
      const target = [snapshot.scheduler.cluster, snapshot.scheduler.partition]
        .filter(Boolean)
        .join('/')
      return target ? `已提交到 ${target}` : '已提交到调度系统'
    }
    case 'submit_failed':
      return '未能提交到调度系统'
    case 'started':
      return '调度任务已开始运行'
    case 'finished':
      if (run.status === 'succeeded') return '运行成功'
      if (run.status === 'cancelled') return '运行已取消'
      if (run.status === 'failed' || run.status === 'submit_failed') return '运行失败'
      return '运行已结束'
    case 'cancel_requested':
      return '正在等待调度系统确认'
    case 'cancelled':
      return '运行已取消'
    case 'artifact_collected':
      return '运行产物已可用'
    case 'artifact_missing': {
      const path = /^收集路径 (.+) 不存在$/.exec(event.message)?.[1]
      return path ? `未找到运行产物：${path}` : '未找到预期的运行产物'
    }
    case 'error':
      return '调度系统暂时无法确认任务状态'
  }
}

/** 平台执行事件；stdout / stderr 在独立日志表面展示。 */
export function RunTimeline({ detail }: { detail: RunDetail }) {
  const { events } = detail
  if (events.length === 0) {
    return <Text className={styles.muted}>这个 Run 还没有执行事件。</Text>
  }

  return (
    <ol className={styles.timeline} aria-label="Run 执行事件">
      {events.map((event) => (
        <li key={event.id} className={styles.timelineItem}>
          <EventVisual type={event.type} />
          <div className={styles.timelineBody}>
            <div className={styles.timelineHeading}>
              <strong>{EVENT_LABEL[event.type]}</strong>
              <time dateTime={event.created_at} title={formatTime(event.created_at)}>
                {formatClockTime(event.created_at)}
              </time>
            </div>
            <Text as="p" className={styles.timelineMessage}>
              {eventDescription(event, detail)}
            </Text>
          </div>
        </li>
      ))}
    </ol>
  )
}
