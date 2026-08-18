import { Tag } from 'antd'

import type { MembershipRole } from '../../api/types'
import { roleColor, roleLabel } from '../../utils/roles'

export function RoleTag({ role, prefix }: { role: MembershipRole; prefix?: string }) {
  const label = roleLabel(role)
  return <Tag color={roleColor(role)}>{prefix ? `${prefix}${label}` : label}</Tag>
}
