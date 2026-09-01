import {
  AlertFillIcon,
  CheckCircleFillIcon,
  ClockIcon,
  DotFillIcon,
  StopIcon,
  XCircleFillIcon,
} from '@primer/octicons-react'
import { Label, type LabelProps } from '@primer/react'
import type { ComponentType, CSSProperties } from 'react'

import type { RunStatus } from '../../api/types'
import { runStatusLabel } from '../../utils/runStatus'
import styles from '../run/run.module.css'

interface StatusStyle {
  variant: LabelProps['variant']
  icon: ComponentType<{
    size?: number
    'aria-hidden'?: boolean
    'aria-label'?: string
    title?: string
    style?: CSSProperties
  }>
  color: string
}

const RUN_STATUS_STYLE: Record<RunStatus, StatusStyle> = {
  queued: { variant: 'secondary', icon: ClockIcon, color: 'var(--fgColor-muted)' },
  running: { variant: 'accent', icon: DotFillIcon, color: 'var(--fgColor-accent)' },
  succeeded: { variant: 'success', icon: CheckCircleFillIcon, color: 'var(--fgColor-success)' },
  failed: { variant: 'danger', icon: XCircleFillIcon, color: 'var(--fgColor-danger)' },
  cancelled: { variant: 'attention', icon: StopIcon, color: 'var(--fgColor-attention)' },
  submit_failed: { variant: 'danger', icon: AlertFillIcon, color: 'var(--fgColor-danger)' },
}

/** Run 状态只在这里组合文案、Primer 语义色和图标。 */
export function RunStatusTag({
  status,
  compact = false,
}: {
  status: RunStatus
  compact?: boolean
}) {
  const style = RUN_STATUS_STYLE[status]
  const Icon = style.icon
  const label = runStatusLabel(status)
  if (compact) {
    return <Icon size={16} aria-label={label} title={label} style={{ color: style.color }} />
  }

  return (
    <Label variant={style.variant} className={styles.statusLabel}>
      <Icon size={12} aria-hidden />
      {label}
    </Label>
  )
}
