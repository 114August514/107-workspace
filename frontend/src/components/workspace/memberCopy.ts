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
  viewer: '只读',
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
    membersDescription: '查看 Membership 的 Role 与 Status，并按后端授权治理成员。',
  },
  members: {
    listLabel: '成员列表',
    loading: '正在加载成员…',
    summary: (count: number) => (count > 0 ? `${count} 位成员与待确认邀请` : '成员与待确认邀请'),
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
    roleLabel: '角色',
    ownerCaption: 'Owner 只能通过明确的所有权转让产生。',
    cancel: '取消',
    submit: '发送邀请',
    success: (username: string) => `已向 ${username} 发送邀请`,
    failureTitle: '邀请发送失败。',
    failureNext: '请确认用户名和角色后重试。',
  },
  role: {
    controlLabel: (username: string) => `修改 ${username} 的角色`,
    success: (username: string, role: MembershipRole) =>
      `${username} 的角色已改为${membershipRoleLabel(role)}`,
    failureTitle: '角色修改失败。',
    failureNext: '请确认成员仍在 User Group 中并重试。',
  },
  remove: {
    action: (username: string) => `移除 ${username}`,
    confirmTitle: (username: string) => `移除 ${username}？`,
    confirm: '移除成员',
    consequence: '移除后，该成员会立刻失去这个 User Group 的访问权。',
    success: (username: string) => `已移除 ${username}`,
    failureTitle: '成员移除失败。',
    failureNext: '请确认成员状态和你的管理权限后重试。',
  },
  transfer: {
    action: (username: string) => `转让给 ${username}`,
    confirmTitle: (username: string) => `将所有权转让给 ${username}？`,
    confirm: '转让所有权',
    consequence: '转让后，你将变为管理员，新 Owner 将获得转让所有权与全部成员治理权限。',
    success: (username: string) => `已将 User Group 所有权转让给 ${username}`,
    failureTitle: '所有权转让失败。',
    failureNext: '请确认目标仍是已加入成员，并确认你仍是当前 Owner 后重试。',
  },
} as const
