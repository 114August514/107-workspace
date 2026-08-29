import { HomeIcon, OrganizationIcon } from '@primer/octicons-react'
import { Label, Link, Text, UnderlineNav } from '@primer/react'
import { Link as RouterLink, Outlet, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import type { UserGroup } from '../api/types'
import { can } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
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
  const { userGroupId = '' } = useParams()
  const userGroup = useAsync<UserGroup>(() => api.getUserGroup(userGroupId), [userGroupId])

  return (
    <div className={styles.page}>
      <AsyncState
        loading={userGroup.loading && !userGroup.data}
        loadingText={copy.page.loading}
        error={toAsyncError(userGroup.error)}
        onRetry={userGroup.reload}
      >
        {userGroup.data ? (
          <>
            <nav className={styles.breadcrumb} aria-label={copy.page.breadcrumbLabel}>
              <HomeIcon aria-hidden="true" />
              <Link as={RouterLink} to="/">
                {copy.page.home}
              </Link>
              <span aria-hidden="true">/</span>
              <span>{userGroup.data.name}</span>
            </nav>

            <header className={styles.header}>
              <div className={styles.titleRow}>
                <OrganizationIcon className={styles.titleIcon} size={24} aria-hidden="true" />
                <h1 className={styles.title}>{userGroup.data.name}</h1>
                <Label variant="accent">{copy.page.kind}</Label>
                <Label variant={userGroup.data.role === 'owner' ? 'attention' : 'default'}>
                  {userGroupRoleLabel(userGroup.data.role)}
                </Label>
              </div>
              <Text as="p" className={styles.description}>
                {userGroup.data.description || copy.page.fallbackDescription}
              </Text>
            </header>

            <UserGroupSectionNav userGroup={userGroup.data} />

            <div className={styles.sectionContent}>
              <Outlet
                context={
                  {
                    userGroup: userGroup.data,
                    reload: userGroup.reload,
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

function UserGroupSectionNav({ userGroup }: { userGroup: UserGroup }) {
  const showSettings = can(userGroup, 'user_group.update')
  return (
    <UnderlineNav aria-label={copy.page.navLabel} variant="flush">
      <UnderlineNav.Item as={RouterLink} to=".">
        {copy.nav.overview}
      </UnderlineNav.Item>
      <UnderlineNav.Item as={RouterLink} to="members">
        {copy.nav.members}
      </UnderlineNav.Item>
      {showSettings ? (
        <UnderlineNav.Item as={RouterLink} to="settings">
          {copy.nav.settings}
        </UnderlineNav.Item>
      ) : null}
    </UnderlineNav>
  )
}
