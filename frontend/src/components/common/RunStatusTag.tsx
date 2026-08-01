import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  LoadingOutlined,
  StopOutlined,
} from '@ant-design/icons'
import { Tag } from 'antd'
import type { ReactNode } from 'react'

import type { RunStatus } from '../../api/types'
import { runStatusColor, runStatusLabel } from '../../utils/runStatus'

/** 图标只有这里用得上；文案和配色在 utils/runStatus 里，活动流也要用同一份。 */
const RUN_STATUS_ICON: Record<RunStatus, ReactNode> = {
  queued: <ClockCircleOutlined />,
  running: <LoadingOutlined />,
  succeeded: <CheckCircleOutlined />,
  failed: <CloseCircleOutlined />,
  cancelled: <StopOutlined />,
  submit_failed: <ExclamationCircleOutlined />,
}

export function RunStatusTag({ status }: { status: RunStatus }) {
  return (
    <Tag color={runStatusColor(status)} icon={RUN_STATUS_ICON[status]}>
      {runStatusLabel(status)}
    </Tag>
  )
}
