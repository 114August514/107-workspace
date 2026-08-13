/**
 * 活动动作的中文说法，以及点进去去哪里。
 *
 * 用 `Record<ActivityAction, ...>` 而不是 switch 加 default：
 * 后端新增一个动作，契约里的联合类型跟着变，这张表少一个键**编译期就会报错**。
 * 有 default 的话新动作会悄悄显示成兜底文案，没人发现。
 */

import type { Activity, ActivityAction } from '../../api/types'
import { isRunStatus, runStatusLabel } from '../../utils/runStatus'

const ACTION_TEXT: Record<ActivityAction, string> = {
  workspace_created: '创建了空间',
  workspace_updated: '修改了空间设置',
  member_invited: '邀请了',
  member_joined: '加入了空间',
  member_left: '退出了空间',
  member_removed: '移除了',
  member_role_changed: '修改了角色',
  ownership_transferred: '把空间所有权转让给',
  project_created: '创建了 Project',
  project_updated: '修改了 Project',
  project_forked: '派生出 Project',
  version_saved: '保存了版本',
  version_restored: '恢复到版本',
  run_submitted: '提交了 Run',
  run_cancelled: '取消了 Run',
  run_finished: '的 Run 结束了',
  shared_resource_created: '创建了 Shared Resource',
  shared_resource_updated: '修改了 Shared Resource',
  shared_resource_version_published: '发布了版本',
}

export function describeAction(action: ActivityAction): string {
  return ACTION_TEXT[action]
}

/**
 * 活动指向的对象在前端的地址。
 *
 * 返回 null 表示这个对象没有独立页面（比如成员），或者链接过去也没意义。
 */
export function targetPath(activity: Activity): string | null {
  switch (activity.target_type) {
    case 'workspace':
      return `/workspaces/${activity.target_id}`
    case 'project':
      return `/projects/${activity.target_id}`
    case 'run':
      return `/runs/${activity.target_id}`
    case 'project_version':
      // 版本没有独立页面，跳到它所属的 Project
      return activity.project_id ? `/projects/${activity.project_id}` : null
    case 'shared_resource':
      return `/shared-resources/${activity.target_id}`
    case 'shared_resource_version':
      return `/shared-resource-versions/${activity.target_id}`
    case 'member':
      return null
  }
}

/**
 * 活动自己带的对象名要不要显示。
 *
 * 「加入了空间」「退出了空间」这两类里，操作者就是对象本人，
 * 再把名字重复一遍会读成「guest 加入了空间 guest」。
 */
export function showsTarget(activity: Activity): boolean {
  return activity.actor_id !== activity.target_id
}

/**
 * 补充说明的展示文本。
 *
 * `run_finished` 的 detail 存的是 Run 状态的原始取值（后端写的是
 * `run.status.value`）。这里翻成中文，用的是全站同一份状态文案。
 * 认不出来就原样显示——总比显示不出来强。
 */
export function describeDetail(activity: Activity): string {
  if (activity.action === 'run_finished' && isRunStatus(activity.detail)) {
    return runStatusLabel(activity.detail)
  }
  return activity.detail
}
