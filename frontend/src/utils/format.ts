/** 展示用的格式化函数。 */

import dayjs from 'dayjs'

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes / 1024
  let index = 0
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index += 1
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[index]}`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 1) return '< 1 秒'
  const total = Math.round(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const rest = total % 60
  if (hours > 0) return minutes > 0 ? `${hours} 小时 ${minutes} 分` : `${hours} 小时`
  if (minutes > 0) return rest > 0 ? `${minutes} 分 ${rest} 秒` : `${minutes} 分钟`
  return `${rest} 秒`
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  return dayjs(value).format('YYYY-MM-DD HH:mm:ss')
}

export function formatTimelineTime(value: string | null | undefined): string {
  if (!value) return '—'
  return dayjs(value).format('HH:mm:ss')
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return '—'
  const then = dayjs(value)
  const minutes = dayjs().diff(then, 'minute')
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`
  return then.format('YYYY-MM-DD')
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  return dayjs(value).format('YYYY-MM-DD')
}

export function formatMemory(megabytes: number): string {
  return megabytes >= 1024 && megabytes % 1024 === 0 ? `${megabytes / 1024} GB` : `${megabytes} MB`
}

/** 运行时限用整分钟表达，不要退化成「15 分 0 秒」这种读起来别扭的写法。 */
export function formatMinutes(minutes: number): string {
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (rest === 0) return `${hours} 小时`
  return `${hours} 小时 ${rest} 分钟`
}

/** 把算力请求整理成一行可读文本。 */
export function describeComputeRequest(request: {
  nodes: number
  cpus: number
  memory_mb: number
  gpus: number
  time_limit_minutes: number
}): string {
  const parts = [
    `${request.nodes} 节点`,
    `${request.cpus} 核`,
    formatMemory(request.memory_mb),
    `最长 ${formatMinutes(request.time_limit_minutes)}`,
  ]
  if (request.gpus > 0) parts.splice(3, 0, `${request.gpus} 张 GPU`)
  return parts.join(' · ')
}
