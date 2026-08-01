import { Timeline, Typography } from 'antd'
import dayjs from 'dayjs'

import type { RunEvent } from '../../api/types'

const EVENT_COLOR: Record<string, string> = {
  created: 'gray',
  submitted: 'blue',
  submit_failed: 'red',
  started: 'blue',
  finished: 'green',
  cancel_requested: 'orange',
  cancelled: 'orange',
  artifact_collected: 'green',
  artifact_missing: 'orange',
  error: 'red',
}

const EVENT_LABEL: Record<string, string> = {
  created: '创建 Run',
  submitted: '提交调度任务',
  submit_failed: '提交失败',
  started: '开始执行',
  finished: '执行结束',
  cancel_requested: '请求取消',
  cancelled: '已取消',
  artifact_collected: '收集 Artifact',
  artifact_missing: 'Artifact 缺失',
  error: '异常',
}

/** 平台产生的执行事件时间线，区别于用户程序的 stdout / stderr。 */
export function RunTimeline({ events }: { events: RunEvent[] }) {
  return (
    <Timeline
      items={events.map((event) => ({
        color: EVENT_COLOR[event.type] ?? 'gray',
        children: (
          <div>
            <Typography.Text strong>{EVENT_LABEL[event.type] ?? event.type}</Typography.Text>
            <Typography.Text type="secondary" style={{ marginInlineStart: 8 }}>
              {dayjs(event.created_at).format('HH:mm:ss')}
            </Typography.Text>
            <div>
              <Typography.Text type="secondary">{event.message}</Typography.Text>
            </div>
          </div>
        ),
      }))}
    />
  )
}
