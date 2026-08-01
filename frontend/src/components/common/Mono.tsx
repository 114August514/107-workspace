import { Tooltip, Typography } from 'antd'

import { fontFamilyCode } from '../../theme'
import { formatRelative, formatTime } from '../../utils/format'

interface MonoProps {
  children: string
  /** 只显示前若干个字符。ID 很长而前几位已经够区分了。 */
  truncate?: number
  copyable?: boolean
}

/**
 * 标识符：ID、路径、命令、调度任务号。
 *
 * 一律等宽显示。这不是装饰——等宽字体下 `run_0980` 和 `run_098O` 一眼能看出
 * 不一样，比例字体下看不出来。**用户要拿这些串去和别处比对**，
 * 比如把 Run ID 报给助教、把调度任务号贴到集群命令里。
 */
export function Mono({ children, truncate, copyable }: MonoProps) {
  const shown = truncate && children.length > truncate ? children.slice(0, truncate) : children
  const element = (
    <Typography.Text
      style={{ fontFamily: fontFamilyCode, fontSize: 12 }}
      copyable={copyable ? { text: children } : false}
    >
      {shown}
    </Typography.Text>
  )
  // 截断了就得让人能看到完整值，否则复制出来的和看到的对不上
  return shown === children ? element : <Tooltip title={children}>{element}</Tooltip>
}

/**
 * 相对时间，悬停显示准确时刻。
 *
 * 「3 小时前」适合扫，「2026-07-26 14:03:11」适合排查。两个都要，
 * 所以默认显示前者，把后者放进 tooltip。
 */
export function RelativeTime({ value }: { value: string | null | undefined }) {
  if (!value) return <Typography.Text type="secondary">—</Typography.Text>
  return (
    <Tooltip title={formatTime(value)}>
      <Typography.Text type="secondary">{formatRelative(value)}</Typography.Text>
    </Tooltip>
  )
}
