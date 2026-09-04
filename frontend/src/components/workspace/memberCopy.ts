/**
 * User Group identity and Membership governance copy.
 *
 * This module owns stable visible language only. Capability checks remain server-provided,
 * and dynamic user/group names stay at call sites.
 */
import type { MembershipRole, MembershipStatus } from '../../api/types'

const ROLE_LABEL: Record<MembershipRole, string> = {
  owner: '所有者',
  admin: '管理员',
  member: '成员',
}

const STATUS_LABEL: Record<MembershipStatus, string> = {
  invited: '待确认',
  active: '已加入',
  left: '已退出',
  removed: '已移除',
}

export function membershipRoleLabel(role: MembershipRole): string {
  return ROLE_LABEL[role]
}

export function membershipStatusLabel(status: MembershipStatus): string {
  return STATUS_LABEL[status]
}

export const userGroupGovernanceCopy = {
  page: {
    loading: '正在加载 User Group…',
    fallbackDescription: '这个 User Group 还没有填写说明。',
    kind: 'User Group',
    breadcrumbLabel: '面包屑',
    identityLabel: 'User Group 身份',
    home: '首页',
    membersTitle: '成员',
    membersDescription: '管理成员及其在这个 User Group 中的权限。',
  },
  members: {
    listLabel: '成员列表',
    loading: '正在加载成员…',
    summary: (count: number) => `${count} 位成员`,
    emptyTitle: '这个 User Group 还没有成员。',
    emptyDescription: (canManage: boolean) =>
      canManage ? '邀请成员后，他们会在接受邀请后加入。' : '有管理权限的成员可以发送邀请。',
  },
  invite: {
    action: '邀请成员',
    title: '邀请成员',
    usernameLabel: '用户名',
    usernamePlaceholder: '例如：student',
    usernameRequired: '请填写用户名',
    cancel: '取消',
    submit: '发送邀请',
    success: (username: string) => `已向 ${username} 发送邀请`,
    failureTitle: '邀请发送失败。',
    failureNext: '请确认用户名后重试。',
  },
  actions: {
    more: (username: string) => `${username} 的更多操作`,
  },
  role: {
    action: (role: 'admin' | 'member') => (role === 'admin' ? '设为管理员' : '设为成员'),
    success: (username: string, role: 'admin' | 'member') =>
      `已将 ${username} ${role === 'admin' ? '设为管理员' : '设为成员'}`,
    failureTitle: '角色修改失败。',
    failureNext: '请确认成员仍在 User Group 中并重试。',
  },
  remove: {
    confirmTitle: (username: string) => `移除 ${username}？`,
    confirm: '移除成员',
    consequence: '移除后，该成员会立刻失去这个 User Group 的访问权。',
    success: (username: string) => `已移除 ${username}`,
    failureTitle: '成员移除失败。',
    failureNext: '请确认成员状态和你的管理权限后重试。',
  },
  transfer: {
    confirmTitle: (username: string) => `将所有权转让给 ${username}？`,
    confirm: '转让所有权',
    consequence: '转让后，你将变为管理员，新 Owner 将获得转让所有权与全部成员治理权限。',
    success: (username: string) => `已将 User Group 所有权转让给 ${username}`,
    failureTitle: '所有权转让失败。',
    failureNext: '请确认目标仍是已加入成员，并确认你仍是当前 Owner 后重试。',
  },
  delete: {
    action: '删除 User Group',
    title: (name: string) => `删除 User Group“${name}”？`,
    description: '删除会结束这个 User Group 的 Membership、授权和配置生命周期。',
    loading: '正在读取删除影响…',
    impactTitle: '将处理以下记录',
    blockedTitle: '当前不能删除',
    empty: '没有需要额外处理的归属对象。',
    confirm: '删除 User Group',
    cancel: '取消',
    success: 'User Group 已删除',
    failureTitle: 'User Group 删除失败。',
    itemLabels: {
      projects: 'Project',
      environments: 'Environment',
      shared_resources: 'Shared Resource',
      variables: 'Variable',
      secrets: 'Secret',
      memberships: 'Membership',
      grants: 'USE Grant',
      activities: 'Activity',
      notifications: 'Notification',
    } as Record<string, string>,
  },
} as const
