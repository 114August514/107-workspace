import { Button, Dialog, Banner, Label, Link, Stack, Text } from '@primer/react'
import { HomeIcon, OrganizationIcon } from '@primer/octicons-react'
import { useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import { can, type DeletionImpact, type UserGroup } from '../api/types'
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
  const navigate = useNavigate()
  const [deleteOpen, setDeleteOpen] = useState(false)
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
                {can(userGroup.data, 'user_group.delete') ? (
                  <Button variant="danger" onClick={() => setDeleteOpen(true)}>
                    {copy.delete.action}
                  </Button>
                ) : null}
                <div className={styles.sectionIndicator}>
                  <span className={styles.currentSection}>{copy.page.membersTitle}</span>
                </div>
              </aside>

              <MemberPanel userGroup={userGroup.data} onUserGroupChanged={userGroup.reload} />
            </div>
            {deleteOpen ? (
              <DeleteUserGroupDialog
                userGroup={userGroup.data}
                onClose={() => setDeleteOpen(false)}
                onDeleted={() => navigate('/')}
              />
            ) : null}
          </>
        ) : null}
      </AsyncState>
    </div>
  )
}

function DeleteUserGroupDialog({
  userGroup,
  onClose,
  onDeleted,
}: {
  userGroup: UserGroup
  onClose: () => void
  onDeleted: () => void
}) {
  const impact = useAsync<DeletionImpact>(
    () => api.getUserGroupDeletionImpact(userGroup.id),
    [userGroup.id],
  )
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<Error | undefined>()
  const viewError = toAsyncError(submitError ?? impact.error)
  const canConfirm = impact.data?.can_delete === true && !submitting
  const items = impact.data?.items ?? []
  const problems = impact.data?.problems ?? []

  const submit = async () => {
    if (!canConfirm) return
    setSubmitting(true)
    setSubmitError(undefined)
    try {
      await api.deleteUserGroup(userGroup.id)
      onDeleted()
    } catch (error) {
      setSubmitError(error instanceof Error ? error : new Error('delete failed'))
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      title={copy.delete.title(userGroup.name)}
      width="large"
      onClose={() => {
        if (!submitting) onClose()
      }}
      footerButtons={[
        { content: copy.delete.cancel, disabled: submitting, onClick: onClose },
        {
          content: copy.delete.confirm,
          buttonType: 'danger',
          loading: submitting,
          disabled: !canConfirm,
          onClick: () => void submit(),
        },
      ]}
    >
      <Stack gap="normal">
        <Text as="p">{copy.delete.description}</Text>
        {impact.loading ? <Text>{copy.delete.loading}</Text> : null}
        {impact.data ? (
          <>
            <Text as="h3">{copy.delete.impactTitle}</Text>
            <ul>
              {items
                .filter((item) => item.count > 0)
                .map((item) => (
                  <li key={item.kind}>
                    {copy.delete.itemLabels[item.kind] ?? item.kind}：{item.count}
                  </li>
                ))}
            </ul>
            {items.every((item) => item.count === 0) ? <Text>{copy.delete.empty}</Text> : null}
            {problems.length > 0 ? (
              <Banner variant="critical">
                <Banner.Title>{copy.delete.blockedTitle}</Banner.Title>
                <Banner.Description>
                  <ul>
                    {problems.map((problem) => (
                      <li key={problem}>{problem}</li>
                    ))}
                  </ul>
                </Banner.Description>
              </Banner>
            ) : null}
          </>
        ) : null}
        {viewError ? (
          <Banner variant="critical">
            <Banner.Title>{viewError.message}</Banner.Title>
            {viewError.problems?.map((problem) => (
              <Banner.Description key={problem}>{problem}</Banner.Description>
            ))}
            {impact.error && !submitError ? (
              <Banner.PrimaryAction onClick={() => void impact.reload()}>
                重试读取影响
              </Banner.PrimaryAction>
            ) : null}
          </Banner>
        ) : null}
      </Stack>
    </Dialog>
  )
}
