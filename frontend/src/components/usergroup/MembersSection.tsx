import { useOutletContext } from 'react-router-dom'

import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { MemberPanel } from '../workspace/MemberPanel'

export function MembersSection() {
  const { userGroup, reload } = useOutletContext<UserGroupOutletContext>()
  return <MemberPanel userGroup={userGroup} onUserGroupChanged={reload} />
}
