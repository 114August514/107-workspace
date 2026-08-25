import {
  AlertFillIcon,
  CheckCircleFillIcon,
  ClockIcon,
  DotFillIcon,
  StopIcon,
  XCircleFillIcon,
} from '@primer/octicons-react'
import { Label, type LabelProps } from '@primer/react'
import type { ComponentType } from 'react'

import type { RunStatus } from '../../api/types'
import { runStatusLabel } from '../../utils/runStatus'
import styles from '../run/run.module.css'

interface StatusStyle {
  variant: LabelProps['variant']
  icon: ComponentType<{ size?: number; 'aria-hidden'?: boolean }>
}

const RUN_STATUS_STYLE: Record<RunStatus, StatusStyle> = {
  queued: { variant: 'secondary', icon: ClockIcon },
  running: { variant: 'accent', icon: DotFillIcon },
  succeeded: { variant: 'success', icon: CheckCircleFillIcon },
  failed: { variant: 'danger', icon: XCircleFillIcon },
  cancelled: { variant: 'attention', icon: StopIcon },
  submit_failed: { variant: 'danger', icon: AlertFillIcon },
}

/** Run 状态只在这里组合文案、Primer 语义色和图标。 */
export function RunStatusTag({ status }: { status: RunStatus }) {
  const style = RUN_STATUS_STYLE[status]
  const Icon = style.icon
  return (
    <Label variant={style.variant} className={styles.statusLabel}>
      <Icon size={12} aria-hidden />
      {runStatusLabel(status)}
    </Label>
  )
}
