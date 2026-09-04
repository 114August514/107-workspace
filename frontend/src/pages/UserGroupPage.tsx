import { OrganizationIcon } from '@primer/octicons-react'
import { Banner, Button, Dialog, Label, Stack, Text } from '@primer/react'
import { useState } from 'react'
import { Outlet, matchPath, useLocation, useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import { can, type DeletionImpact, type UserGroup } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { userGroupGovernanceCopy as governanceCopy } from '../components/workspace/memberCopy'
import { useCurrentUserGroup } from '../components/usergroup/userGroupContext'
import {
  userGroupPageCopy as pageCopy,
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
  const navigate = useNavigate()
  const [deleteOpen, setDeleteOpen] = useState(false)
  const isOverview = matchPath('/user-groups/:userGroupId', pathname) !== null

  return (
    <div className={styles.page}>
      <AsyncState
        loading={group.loading && !group.userGroup}
        loadingText={pageCopy.page.loading}
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
                {can(group.userGroup, 'user_group.delete') ? (
                  <Button variant="danger" onClick={() => setDeleteOpen(true)}>
                    {governanceCopy.delete.action}
                  </Button>
                ) : null}
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
            {deleteOpen ? (
              <DeleteUserGroupDialog
                userGroup={group.userGroup}
                onClose={() => setDeleteOpen(false)}
                onDeleted={() => navigate('/')}
              />
            ) : null}
          </div>
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
      title={governanceCopy.delete.title(userGroup.name)}
      width="large"
      onClose={() => {
        if (!submitting) onClose()
      }}
      footerButtons={[
        {
          content: governanceCopy.delete.cancel,
          disabled: submitting,
          onClick: onClose,
        },
        {
          content: governanceCopy.delete.confirm,
          buttonType: 'danger',
          loading: submitting,
          disabled: !canConfirm,
          onClick: () => void submit(),
        },
      ]}
    >
      <Stack gap="normal">
        <Text as="p">{governanceCopy.delete.description}</Text>
        {impact.loading ? <Text>{governanceCopy.delete.loading}</Text> : null}
        {impact.data ? (
          <>
            <Text as="h3">{governanceCopy.delete.impactTitle}</Text>
            <ul>
              {items
                .filter((item) => item.count > 0)
                .map((item) => (
                  <li key={item.kind}>
                    {governanceCopy.delete.itemLabels[item.kind] ?? item.kind}：{item.count}
                  </li>
                ))}
            </ul>
            {items.every((item) => item.count === 0) ? (
              <Text>{governanceCopy.delete.empty}</Text>
            ) : null}
            {problems.length > 0 ? (
              <Banner variant="critical">
                <Banner.Title>{governanceCopy.delete.blockedTitle}</Banner.Title>
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
