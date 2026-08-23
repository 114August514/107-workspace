/**
 * 角色的展示名和配色，全站只在这里定义一次。
 *
 * 这张表只管**怎么显示**。能做什么由后端下发的 capabilities 决定，
 * 不要从角色反推权限，否则前后端会各自维护一份授权策略并逐渐失配。
 */

import type { MembershipRole } from '../api/types'

interface RoleStyle {
  color: string
  label: string
}

const ROLE_STYLE: Record<MembershipRole, RoleStyle> = {
  owner: { color: 'gold', label: '所有者' },
  admin: { color: 'blue', label: '管理员' },
  member: { color: 'default', label: '成员' },
}

export function roleLabel(role: MembershipRole): string {
  return ROLE_STYLE[role].label
}

export function roleColor(role: MembershipRole): string {
  return ROLE_STYLE[role].color
}
