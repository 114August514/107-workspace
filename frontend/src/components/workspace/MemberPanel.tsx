import { KebabHorizontalIcon, PersonAddIcon } from '@primer/octicons-react'
import {
  ActionList,
  ActionMenu,
  Banner,
  Button,
  ConfirmationDialog,
  Dialog,
  FormControl,
  Label,
  IconButton,
  Radio,
  RadioGroup,
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
const ASSIGNABLE_ROLES = ['admin', 'member'] as const satisfies readonly MembershipRole[]
const INVITABLE_ROLES = ['member', 'admin'] as const satisfies readonly MembershipRole[]

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
    <section className={styles.panel} aria-labelledby="user-group-members-title">
      <header className={styles.sectionHeader}>
        <h2 id="user-group-members-title" className={styles.sectionTitle}>
          {copy.page.membersTitle}
        </h2>
        <p className={styles.sectionDescription}>{copy.page.membersDescription}</p>
        {canManage ? (
          <Button
            className={styles.inviteAction}
            leadingVisual={PersonAddIcon}
            onClick={() => setInviteOpen(true)}
          >
            {copy.invite.action}
          </Button>
        ) : null}
      </header>

      <span className={styles.summary}>{copy.members.summary(items.length)}</span>

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
            const canRemove = canManage && !isOwner
            const canTransferOwnership = canTransfer && member.status === 'active' && !isOwner
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
                <div className={styles.governance}>
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
                    {canTransferOwnership || canRemove ? (
                      <MemberActionsMenu
                        member={member}
                        canTransfer={canTransferOwnership}
                        canRemove={canRemove}
                        disabled={pending !== null}
                        onTransfer={() => setConfirmation({ kind: 'transfer', member })}
                        onRemove={() => setConfirmation({ kind: 'remove', member })}
                      />
                    ) : null}
                  </div>
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
    </section>
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
      width="large"
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
          <RadioGroup
            name="invite-member-role"
            disabled={submitting}
            onChange={(selected) => {
              if (selected === 'admin' || selected === 'member') setRole(selected)
            }}
          >
            <RadioGroup.Label>{copy.invite.roleLabel}</RadioGroup.Label>
            {INVITABLE_ROLES.map((assignableRole) => (
              <FormControl
                key={assignableRole}
                disabled={submitting}
                id={`invite-member-role-${assignableRole}`}
              >
                <Radio value={assignableRole} checked={role === assignableRole} />
                <FormControl.Label>{membershipRoleLabel(assignableRole)}</FormControl.Label>
                <FormControl.Caption>
                  {copy.invite.roleDescription[assignableRole]}
                </FormControl.Caption>
              </FormControl>
            ))}
            <RadioGroup.Caption>{copy.invite.ownerCaption}</RadioGroup.Caption>
          </RadioGroup>
        </Stack>
      </form>
    </Dialog>
  )
}

function MemberActionsMenu({
  member,
  canTransfer,
  canRemove,
  disabled,
  onTransfer,
  onRemove,
}: {
  member: Member
  canTransfer: boolean
  canRemove: boolean
  disabled: boolean
  onTransfer: () => void
  onRemove: () => void
}) {
  return (
    <ActionMenu>
      <ActionMenu.Anchor>
        <IconButton
          icon={KebabHorizontalIcon}
          variant="invisible"
          aria-label={copy.actions.more(member.username)}
          disabled={disabled}
        />
      </ActionMenu.Anchor>
      <ActionMenu.Overlay align="end" width="auto">
        <ActionList>
          {canTransfer ? (
            <ActionList.Item disabled={disabled} onSelect={onTransfer}>
              {copy.transfer.confirm}
            </ActionList.Item>
          ) : null}
          {canTransfer && canRemove ? <ActionList.Divider /> : null}
          {canRemove ? (
            <ActionList.Item variant="danger" disabled={disabled} onSelect={onRemove}>
              {copy.remove.confirm}
            </ActionList.Item>
          ) : null}
        </ActionList>
      </ActionMenu.Overlay>
    </ActionMenu>
  )
}

function RoleMenu({
  value,
  label,
  disabled,
  onChange,
}: {
  value: MembershipRole
  label: string
  disabled: boolean
  onChange: (role: MembershipRole) => void
}) {
  return (
    <ActionMenu>
      <ActionMenu.Button variant="invisible" aria-label={label} disabled={disabled}>
        {membershipRoleLabel(value)}
      </ActionMenu.Button>
      <ActionMenu.Overlay width="auto">
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

function roleVariant(role: MembershipRole): 'attention' | 'accent' | 'default' {
  if (role === 'owner') return 'attention'
  if (role === 'admin') return 'accent'
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
