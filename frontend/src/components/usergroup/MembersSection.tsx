import { useOutletContext } from 'react-router-dom'

import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { MemberPanel } from '../workspace/MemberPanel'
import { LeaveGroupPanel } from './LeaveGroupPanel'
import styles from './assets.module.css'

export function MembersSection() {
  const { userGroup, reload, onMembershipChanged } = useOutletContext<UserGroupOutletContext>()
  return (
    <div className={styles.membersSection}>
      <MemberPanel userGroup={userGroup} onUserGroupChanged={reload} />
      {userGroup.role !== 'owner' ? (
        <LeaveGroupPanel
          userGroup={userGroup}
          onLeft={() => {
            onMembershipChanged?.()
          }}
        />
      ) : null}
    </div>
  )
}
