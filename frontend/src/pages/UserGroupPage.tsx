import { HomeIcon, OrganizationIcon } from '@primer/octicons-react'
import { Label, Link, Text } from '@primer/react'
import { Link as RouterLink, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import type { UserGroup } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { MemberPanel } from '../components/workspace/MemberPanel'
import {
  membershipRoleLabel,
  userGroupGovernanceCopy as copy,
} from '../components/workspace/memberCopy'
import styles from './UserGroupPage.module.css'

/** User Group identity and Membership governance only. */
export function UserGroupPage() {
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

            <div className={styles.contextLayout}>
              <aside className={styles.identityRail} aria-label={copy.page.identityLabel}>
                <header className={styles.identityHeader}>
                  <OrganizationIcon className={styles.titleIcon} size={24} aria-hidden="true" />
                  <h1 className={styles.title}>{userGroup.data.name}</h1>
                </header>
                <div className={styles.identityLabels}>
                  <Label variant="accent">{copy.page.kind}</Label>
                  <Label variant={userGroup.data.role === 'owner' ? 'attention' : 'default'}>
                    {membershipRoleLabel(userGroup.data.role)}
                  </Label>
                </div>
                <Text as="p" className={styles.description}>
                  {userGroup.data.description || copy.page.fallbackDescription}
                </Text>
                <div className={styles.sectionIndicator}>
                  <span className={styles.currentSection}>{copy.page.membersTitle}</span>
                </div>
              </aside>

              <section className={styles.membersSurface} aria-labelledby="user-group-members-title">
                <div className={styles.sectionHeader}>
                  <h2 id="user-group-members-title" className={styles.sectionTitle}>
                    {copy.page.membersTitle}
                  </h2>
                  <p className={styles.sectionDescription}>{copy.page.membersDescription}</p>
                </div>
                <MemberPanel userGroup={userGroup.data} onUserGroupChanged={userGroup.reload} />
              </section>
            </div>
          </>
        ) : null}
      </AsyncState>
    </div>
  )
}
