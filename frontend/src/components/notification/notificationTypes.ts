/**
 * 通知类型的图标和配色。
 *
 * 用 `Record<NotificationType, ...>` 而不是 switch 加 default：
 * 后端新增一种通知，这张表少一个键**编译期就会报错**。
 * 有 default 的话新类型会悄悄显示成兜底图标，没人发现。
 */

import type { Notification, NotificationType } from '../../api/types'

interface Style {
  /** antd Badge / Tag 的颜色名。 */
  color: string
  label: string
}

const NOTIFICATION_STYLE: Record<NotificationType, Style> = {
  workspace_invited: { color: 'blue', label: '邀请' },
  user_group_invited: { color: 'blue', label: '邀请' },
  member_removed: { color: 'red', label: '成员变动' },
  role_changed: { color: 'gold', label: '角色变更' },
  ownership_received: { color: 'gold', label: '所有权' },
  run_succeeded: { color: 'green', label: 'Run 成功' },
  run_failed: { color: 'red', label: 'Run 失败' },
  run_submit_failed: { color: 'red', label: '提交失败' },
}

export function notificationLabel(type: NotificationType): string {
  return NOTIFICATION_STYLE[type].label
}

export function notificationColor(type: NotificationType): string {
  return NOTIFICATION_STYLE[type].color
}

/**
 * 点这条通知去哪里。
 *
 * 返回 null 表示不做成链接——比如「你被移出了空间」，
 * 他已经看不到那个空间，链过去只会是 404。
 */
export function notificationPath(notification: Notification): string | null {
  if (!notification.target_id || !notification.target_type) return null
  switch (notification.target_type) {
    case 'workspace':
      return `/workspaces/${notification.target_id}`
    case 'user_group':
      return `/user-groups/${notification.target_id}`
    case 'project':
      return `/projects/${notification.target_id}`
    case 'run':
      return `/runs/${notification.target_id}`
    case 'project_version':
      return notification.workspace_id ? `/workspaces/${notification.workspace_id}` : null
    case 'shared_resource':
      return null
    case 'shared_resource_version':
      return null
    case 'member':
      return null
  }
}
