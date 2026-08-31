import { HomeIcon, OrganizationIcon } from '@primer/octicons-react'
import { Label, Link, Text } from '@primer/react'
import { Link as RouterLink, Outlet } from 'react-router-dom'

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
            <nav className={styles.breadcrumb} aria-label={copy.page.breadcrumbLabel}>
              <HomeIcon aria-hidden="true" />
              <Link as={RouterLink} to="/">
                {copy.page.home}
              </Link>
              <span aria-hidden="true">/</span>
              <span>{group.userGroup.name}</span>
            </nav>

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
            </header>

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
