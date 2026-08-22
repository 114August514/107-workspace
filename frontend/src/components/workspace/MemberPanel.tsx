import { PersonAddIcon } from '@primer/octicons-react'
import {
  ActionList,
  ActionMenu,
  Banner,
  Button,
  ConfirmationDialog,
  Dialog,
  FormControl,
  Label,
  Stack,
  TextInput,
} from '@primer/react'
import { useRef, useState } from 'react'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import { can } from '../../api/types'
import type { Member, MembershipRole, MembershipStatus, UserGroup } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import {
  membershipRoleLabel,
  membershipStatusLabel,
  userGroupGovernanceCopy as copy,
} from './memberCopy'
import { AsyncState } from '../common/AsyncState'
import styles from './MemberPanel.module.css'

/**
 * Owner 不在普通 Role 选择中。唯一 Owner 只能由稳定的 transfer-ownership
 * 用例改变，前端不提供制造第二个 Owner 的入口。
 */
const ASSIGNABLE_ROLES = ['admin', 'member', 'viewer'] as const satisfies readonly MembershipRole[]

interface Props {
  userGroup: UserGroup
  onUserGroupChanged?: () => void
}

interface Feedback {
  variant: 'success' | 'critical'
  title: string
  description?: string
}

interface Confirmation {
  kind: 'remove' | 'transfer'
  member: Member
}

export function MemberPanel({ userGroup, onUserGroupChanged }: Props) {
  const members = useAsync<Member[]>(() => api.listMembers(userGroup.id), [userGroup.id])
  const [inviteOpen, setInviteOpen] = useState(false)
  const [pending, setPending] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null)
  const canManage = can(userGroup, 'member.manage')
  const canTransfer = can(userGroup, 'ownership.transfer')

  const changeRole = async (member: Member, role: MembershipRole) => {
    setPending(`role:${member.user_id}`)
    setFeedback(null)
    try {
      await api.changeMemberRole(userGroup.id, member.user_id, role)
      setFeedback({
        variant: 'success',
        title: copy.role.success(member.username, role),
      })
      members.reload()
    } catch {
      setFeedback({
        variant: 'critical',
        title: copy.role.failureTitle,
        description: copy.role.failureNext,
      })
    } finally {
      setPending(null)
    }
  }

  const confirmGovernanceAction = async () => {
    if (!confirmation) return
    const { kind, member } = confirmation
    setPending(`${kind}:${member.user_id}`)
    setFeedback(null)
    try {
      if (kind === 'remove') {
        await api.removeMember(userGroup.id, member.user_id)
        setFeedback({ variant: 'success', title: copy.remove.success(member.username) })
      } else {
        await api.transferUserGroupOwnership(userGroup.id, member.user_id)
        setFeedback({
          variant: 'success',
          title: copy.transfer.success(member.username),
        })
        onUserGroupChanged?.()
      }
      setConfirmation(null)
      members.reload()
    } catch {
      const failure = kind === 'remove' ? copy.remove : copy.transfer
      setConfirmation(null)
      setFeedback({
        variant: 'critical',
        title: failure.failureTitle,
        description: failure.failureNext,
      })
    } finally {
      setPending(null)
    }
  }

  const items = members.data ?? []

  return (
    <div className={styles.panel}>
      <div className={styles.toolbar}>
        <span className={styles.summary}>{copy.members.summary(items.length)}</span>
        {canManage ? (
          <Button leadingVisual={PersonAddIcon} onClick={() => setInviteOpen(true)}>
            {copy.invite.action}
          </Button>
        ) : null}
      </div>

      {feedback ? (
        <Banner variant={feedback.variant} onDismiss={() => setFeedback(null)}>
          <Banner.Title>{feedback.title}</Banner.Title>
          {feedback.description ? (
            <Banner.Description>{feedback.description}</Banner.Description>
          ) : null}
        </Banner>
      ) : null}

      <AsyncState
        loading={members.loading}
        loadingText={copy.members.loading}
        error={toAsyncError(members.error)}
        onRetry={members.reload}
        empty={items.length === 0}
        emptyText={copy.members.emptyTitle}
        emptyDescription={copy.members.emptyDescription(canManage)}
      >
        <ul className={styles.memberList} aria-label={copy.members.listLabel}>
          {items.map((member) => {
            const isOwner = member.role === 'owner'
            const canChangeRole = canManage && member.status === 'active' && !isOwner
            return (
              <li
                key={member.user_id}
                className={styles.memberRow}
                data-testid={`member-${member.user_id}`}
              >
                <div className={styles.identity}>
                  <span className={styles.displayName}>
                    {member.display_name || member.username}
                  </span>
                  <span className={styles.username}>@{member.username}</span>
                </div>
                <div className={styles.role}>
                  {canChangeRole ? (
                    <RoleMenu
                      value={member.role}
                      label={`${copy.role.controlLabel(member.username)}，当前${membershipRoleLabel(member.role)}`}
                      disabled={pending !== null}
                      onChange={(role) => void changeRole(member, role)}
                    />
                  ) : (
                    <Label size="small" variant={roleVariant(member.role)}>
                      {membershipRoleLabel(member.role)}
                    </Label>
                  )}
                </div>
                <div className={styles.status}>
                  <Label size="small" variant={statusVariant(member.status)}>
                    {membershipStatusLabel(member.status)}
                  </Label>
                </div>
                <div className={styles.actions}>
                  {canTransfer && member.status === 'active' && !isOwner ? (
                    <Button
                      size="small"
                      disabled={pending !== null}
                      onClick={() => setConfirmation({ kind: 'transfer', member })}
                    >
                      {copy.transfer.action(member.username)}
                    </Button>
                  ) : null}
                  {canManage && !isOwner ? (
                    <Button
                      size="small"
                      variant="danger"
                      disabled={pending !== null}
                      onClick={() => setConfirmation({ kind: 'remove', member })}
                    >
                      {copy.remove.action(member.username)}
                    </Button>
                  ) : null}
                </div>
              </li>
            )
          })}
        </ul>
      </AsyncState>

      {inviteOpen ? (
        <InviteMemberDialog
          userGroup={userGroup}
          onClose={() => setInviteOpen(false)}
          onInvited={(username) => {
            setFeedback({ variant: 'success', title: copy.invite.success(username) })
            members.reload()
          }}
        />
      ) : null}

      {confirmation ? (
        <ConfirmationDialog
          title={
            confirmation.kind === 'remove'
              ? copy.remove.confirmTitle(confirmation.member.username)
              : copy.transfer.confirmTitle(confirmation.member.username)
          }
          confirmButtonContent={
            confirmation.kind === 'remove' ? copy.remove.confirm : copy.transfer.confirm
          }
          confirmButtonType="danger"
          confirmButtonLoading={pending === `${confirmation.kind}:${confirmation.member.user_id}`}
          cancelButtonContent={copy.invite.cancel}
          onClose={(gesture) => {
            if (pending !== null) return
            if (gesture === 'confirm') void confirmGovernanceAction()
            else setConfirmation(null)
          }}
        >
          {confirmation.kind === 'remove' ? copy.remove.consequence : copy.transfer.consequence}
        </ConfirmationDialog>
      ) : null}
    </div>
  )
}

function InviteMemberDialog({
  userGroup,
  onClose,
  onInvited,
}: {
  userGroup: UserGroup
  onClose: () => void
  onInvited: (username: string) => void
}) {
  const usernameRef = useRef<HTMLInputElement>(null)
  const [username, setUsername] = useState('')
  const [role, setRole] = useState<MembershipRole>('member')
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitFailed, setSubmitFailed] = useState(false)
  const submit = async () => {
    const trimmed = username.trim()
    if (!trimmed) {
      setUsernameError(copy.invite.usernameRequired)
      usernameRef.current?.focus()
      return
    }
    setUsernameError(null)
    setSubmitFailed(false)
    setSubmitting(true)
    try {
      await api.inviteMember(userGroup.id, trimmed, role)
      onInvited(trimmed)
      onClose()
    } catch {
      setSubmitFailed(true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog
      title={copy.invite.title}
      initialFocusRef={usernameRef}
      onClose={() => {
        if (!submitting) onClose()
      }}
      footerButtons={[
        { content: copy.invite.cancel, disabled: submitting, onClick: onClose },
        {
          content: copy.invite.submit,
          buttonType: 'primary',
          loading: submitting,
          disabled: submitting,
          onClick: () => void submit(),
        },
      ]}
    >
      <form
        onSubmit={(event) => {
          event.preventDefault()
          if (!submitting) void submit()
        }}
      >
        <Stack gap="normal">
          {submitFailed ? (
            <Banner variant="critical">
              <Banner.Title>{copy.invite.failureTitle}</Banner.Title>
              <Banner.Description>{copy.invite.failureNext}</Banner.Description>
            </Banner>
          ) : null}
          <FormControl required disabled={submitting} id="invite-member-username">
            <FormControl.Label>{copy.invite.usernameLabel}</FormControl.Label>
            <TextInput
              ref={usernameRef}
              block
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder={copy.invite.usernamePlaceholder}
            />
            {usernameError ? (
              <FormControl.Validation variant="error">{usernameError}</FormControl.Validation>
            ) : null}
          </FormControl>
          <FormControl disabled={submitting} id="invite-member-role">
            <FormControl.Label>{copy.invite.roleLabel}</FormControl.Label>
            <RoleMenu
              value={role}
              label={`选择邀请角色，当前${membershipRoleLabel(role)}`}
              disabled={submitting}
              onChange={setRole}
              block
            />
            <FormControl.Caption>{copy.invite.ownerCaption}</FormControl.Caption>
          </FormControl>
        </Stack>
      </form>
    </Dialog>
  )
}

function RoleMenu({
  value,
  label,
  disabled,
  onChange,
  block = false,
}: {
  value: MembershipRole
  label: string
  disabled: boolean
  onChange: (role: MembershipRole) => void
  block?: boolean
}) {
  return (
    <ActionMenu>
      <ActionMenu.Button
        aria-label={label}
        disabled={disabled}
        className={block ? styles.roleMenuButtonBlock : styles.roleMenuButton}
      >
        {membershipRoleLabel(value)}
      </ActionMenu.Button>
      <ActionMenu.Overlay>
        <ActionList selectionVariant="single">
          {ASSIGNABLE_ROLES.map((role) => (
            <ActionList.Item
              key={role}
              selected={role === value}
              disabled={disabled}
              onSelect={() => {
                if (role !== value) onChange(role)
              }}
            >
              {membershipRoleLabel(role)}
            </ActionList.Item>
          ))}
        </ActionList>
      </ActionMenu.Overlay>
    </ActionMenu>
  )
}

function roleVariant(role: MembershipRole): 'attention' | 'accent' | 'default' | 'secondary' {
  if (role === 'owner') return 'attention'
  if (role === 'admin') return 'accent'
  if (role === 'viewer') return 'secondary'
  return 'default'
}

function statusVariant(status: MembershipStatus): 'success' | 'attention' | 'secondary' | 'danger' {
  const variants: Record<MembershipStatus, 'success' | 'attention' | 'secondary' | 'danger'> = {
    invited: 'attention',
    active: 'success',
    left: 'secondary',
    removed: 'danger',
  }
  return variants[status]
}
