import { Tag } from 'antd'

import type { MembershipRole } from '../../api/types'
import { membershipRoleLabel } from '../workspace/memberCopy'

const ROLE_COLOR: Record<MembershipRole, string> = {
  owner: 'gold',
  admin: 'blue',
  member: 'default',
}

export function RoleTag({ role, prefix }: { role: MembershipRole; prefix?: string }) {
  const label = membershipRoleLabel(role)
  return <Tag color={ROLE_COLOR[role]}>{prefix ? `${prefix}${label}` : label}</Tag>
}
