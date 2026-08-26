/**
 * 通知类型的图标和配色。
 *
 * 用 `Record<NotificationType, ...>` 而不是 switch 加 default：
 * 后端新增一种通知，这张表少一个键**编译期就会报错**。
 * 有 default 的话新类型会悄悄显示成兜底图标，没人发现。
 */

import type { LabelProps } from '@primer/react'

import type { Notification, NotificationType } from '../../api/types'

interface Style {
  /** Primer Label 的语义色，对应通知的严重程度。 */
  variant: LabelProps['variant']
  label: string
}

const NOTIFICATION_STYLE: Record<NotificationType, Style> = {
  user_group_invited: { variant: 'accent', label: '邀请' },
  member_removed: { variant: 'danger', label: '成员变动' },
  role_changed: { variant: 'attention', label: '角色变更' },
  ownership_received: { variant: 'attention', label: '所有权' },
  run_succeeded: { variant: 'success', label: 'Run 成功' },
  run_failed: { variant: 'danger', label: 'Run 失败' },
  run_submit_failed: { variant: 'danger', label: '提交失败' },
}

export function notificationLabel(type: NotificationType): string {
  return NOTIFICATION_STYLE[type].label
}

export function notificationVariant(type: NotificationType): LabelProps['variant'] {
  return NOTIFICATION_STYLE[type].variant
}

/**
 * 点这条通知去哪里。
 *
 * 返回 null 表示不做成链接——比如「你被移出了 User Group」，
 * 你已经无法访问它，链过去只会是 404。
 */
export function notificationPath(notification: Notification): string | null {
  if (!notification.target_id || !notification.target_type) return null
  switch (notification.target_type) {
    case 'user_group':
      return `/user-groups/${notification.target_id}`
    case 'project':
      return `/projects/${notification.target_id}`
    case 'run':
      return `/runs/${notification.target_id}`
    case 'project_version':
      return `/versions/${notification.target_id}`
    case 'shared_resource':
      return `/shared-resources/${notification.target_id}`
    case 'shared_resource_version':
      return `/shared-resource-versions/${notification.target_id}`
    case 'member':
      return null
  }
}
