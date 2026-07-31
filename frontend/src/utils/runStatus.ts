/**
 * Run 状态的展示名和配色，全站只在这里定义一次。
 *
 * 图标留在 `RunStatusTag` 里——只有它需要 ReactNode，
 * 放进来会让这个纯数据模块被迫依赖 React。
 */

import type { RunStatus } from '../api/types'

const RUN_STATUS: Record<RunStatus, { color: string; label: string }> = {
  queued: { color: 'default', label: '排队中' },
  running: { color: 'processing', label: '运行中' },
  succeeded: { color: 'success', label: '成功' },
  failed: { color: 'error', label: '失败' },
  cancelled: { color: 'warning', label: '已取消' },
  submit_failed: { color: 'error', label: '提交失败' },
}

export function runStatusLabel(status: RunStatus): string {
  return RUN_STATUS[status].label
}

export function runStatusColor(status: RunStatus): string {
  return RUN_STATUS[status].color
}

/** 判断一个字符串是不是合法的 Run 状态。用于把活动的 detail 翻成中文。 */
export function isRunStatus(value: string): value is RunStatus {
  return value in RUN_STATUS
}
