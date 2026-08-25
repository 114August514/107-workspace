import { Label, Text } from '@primer/react'

import type { SharedResourceAvailability } from '../../api/types'

/**
 * Shared Resource 可用状态展示（Issue #55）。
 *
 * 状态与解释全部来自后端 availability contract，前端不根据 id 或
 * Membership 推断；文案解释资格来源，而不是只抛「Grant」术语。
 */

export function AvailabilityLabel({ availability }: { availability: SharedResourceAvailability }) {
  if (!availability.usable) {
    return <Label variant="danger">不可用</Label>
  }
  switch (availability.source) {
    case 'owner':
      return <Label variant="success">可用</Label>
    case 'user_grant':
      return <Label variant="success">可用 · 授权</Label>
    case 'user_group_grant':
      return <Label variant="success">可用 · 组授权</Label>
    default:
      return <Label variant="success">可用</Label>
  }
}

function availabilityNote(availability: SharedResourceAvailability): string {
  if (!availability.usable) {
    return '当前没有有效的使用资格，这个资源不能用于 Run。'
  }
  switch (availability.source) {
    case 'owner':
      return '你在这个资源的 Owner 范围内，可以直接使用。'
    case 'user_grant':
      return 'Owner 已向你授予使用授权，你可以在自己的 Project 中引用它。'
    case 'user_group_grant': {
      const groups = availability.grants
        .filter((grant) => grant.grantee.kind === 'user_group')
        .map((grant) => `「${grant.grantee.display_name}」`)
      const subject = groups.length > 0 ? groups.join('、') : '你所在的组'
      return `Owner 已向${subject}授予使用授权；实际使用要求你保持该组的有效成员身份。`
    }
    default:
      return '你在这个资源的 Owner 范围内，可以直接使用。'
  }
}

export function AvailabilityNotice({ availability }: { availability: SharedResourceAvailability }) {
  return (
    <div>
      <Text as="p">{availabilityNote(availability)}</Text>
      {availability.grants.map((grant) => (
        <Text as="p" key={grant.id} size="small">
          使用授权：授予 {grant.grantee.display_name}
          {grant.target_all ? '（覆盖 Owner 全部资产）' : '（仅限此资源）'}
        </Text>
      ))}
    </div>
  )
}
