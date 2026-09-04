import { OrganizationIcon } from '@primer/octicons-react'
import { Label } from '@primer/react'
import { Outlet, matchPath, useLocation } from 'react-router-dom'

import type { UserGroup } from '../api/types'
import { toAsyncError } from '../api/errors'
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
          <div className={isOverview ? styles.overviewInner : undefined}>
            {isOverview ? (
              <header className={styles.header}>
                <span className={styles.avatar} aria-hidden="true">
                  <OrganizationIcon size={32} />
                </span>
                <div className={styles.identity}>
                  <div className={styles.titleRow}>
                    <h1 className={styles.title}>{group.userGroup.name}</h1>
                    <Label variant={group.userGroup.role === 'owner' ? 'attention' : 'default'}>
                      {userGroupRoleLabel(group.userGroup.role)}
                    </Label>
                  </div>
                </div>
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
          </div>
        ) : null}
      </AsyncState>
    </div>
  )
}
