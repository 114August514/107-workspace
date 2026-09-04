import { OrganizationIcon, PeopleIcon } from '@primer/octicons-react'
import { Label, Text } from '@primer/react'
import { Outlet, matchPath, useLocation } from 'react-router-dom'

import { api } from '../api/client'
import type { Member, UserGroup } from '../api/types'
import { toAsyncError } from '../api/errors'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { useCurrentUserGroup } from '../components/usergroup/userGroupContext'
import {
  userGroupPageCopy as copy,
  userGroupRoleLabel,
} from '../components/usergroup/userGroupCopy'
import styles from './UserGroupPage.module.css'

export interface UserGroupOutletContext {
  userGroup: UserGroup
  reload: () => void
  onMembershipChanged?: () => void
}

function GroupMemberCount({ groupId }: { groupId: string }) {
  const members = useAsync<Member[]>(() => api.listMembers(groupId), [groupId])
  if (!members.data) return null
  const active = members.data.filter((member) => member.status === 'active').length
  if (active === 0) return null
  return (
    <Text as="p" className={styles.memberCount}>
      <PeopleIcon className={styles.memberCountIcon} size={16} aria-hidden="true" />
      {`${active} 位成员`}
    </Text>
  )
}

export function UserGroupPage({ onMembershipChanged }: { onMembershipChanged?: () => void }) {
  const group = useCurrentUserGroup()
  const { pathname } = useLocation()
  const isOverview = matchPath('/user-groups/:userGroupId', pathname) !== null

  return (
    <div className={styles.page}>
      <AsyncState
        loading={group.loading && !group.userGroup}
        loadingText={copy.page.loading}
        error={toAsyncError(group.error)}
        onRetry={group.reload}
      >
        {group.userGroup ? (
          <>
            {isOverview ? (
              <header className={styles.header}>
                <div className={styles.titleRow}>
                  <OrganizationIcon className={styles.titleIcon} size={24} aria-hidden="true" />
                  <h1 className={styles.title}>{group.userGroup.name}</h1>
                  <Label variant="accent">{copy.page.kind}</Label>
                  <Label variant={group.userGroup.role === 'owner' ? 'attention' : 'default'}>
                    {userGroupRoleLabel(group.userGroup.role)}
                  </Label>
                </div>
                <Text as="p" className={styles.description}>
                  {group.userGroup.description || copy.page.fallbackDescription}
                </Text>
                <GroupMemberCount groupId={group.userGroup.id} />
              </header>
            ) : null}

            <div className={styles.sectionContent}>
              <Outlet
                context={
                  {
                    userGroup: group.userGroup,
                    reload: group.reload,
                    onMembershipChanged,
                  } satisfies UserGroupOutletContext
                }
              />
            </div>
          </>
        ) : null}
      </AsyncState>
    </div>
  )
}
