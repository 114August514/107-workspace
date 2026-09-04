import { KebabHorizontalIcon, PersonAddIcon } from '@primer/octicons-react'
import {
  ActionList,
  ActionMenu,
  Banner,
  Button,
  ConfirmationDialog,
  Dialog,
  FormControl,
  IconButton,
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
import { parseMemberImportFile } from './parseMemberImport'
import styles from './MemberPanel.module.css'

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
  const canInvite = can(userGroup, 'member.invite')
  const canTransfer = can(userGroup, 'ownership.transfer')

  const changeRole = async (member: Member, role: 'admin' | 'member') => {
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
          {copy.members.title}
        </h2>
        <p className={styles.sectionDescription}>{copy.members.description}</p>
        {canInvite ? (
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
        emptyDescription={copy.members.emptyDescription(canInvite)}
      >
        <ul className={styles.memberList} aria-label={copy.members.listLabel}>
          {items.map((member) => {
            const canChangeRole = can(member, 'member.role.manage')
            const canRemove = can(member, 'member.remove')
            const canTransferOwnership =
              canTransfer && member.status === 'active' && member.role !== 'owner'
            const nextRole = canChangeRole ? nextMembershipRole(member.role) : null
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
                    <span className={styles.roleText}>{membershipRoleLabel(member.role)}</span>
                  </div>
                  <div className={styles.status}>
                    <Label size="small" variant={statusVariant(member.status)}>
                      {membershipStatusLabel(member.status)}
                    </Label>
                  </div>
                  <div className={styles.actions}>
                    {nextRole || canTransferOwnership || canRemove ? (
                      <MemberActionsMenu
                        member={member}
                        nextRole={nextRole}
                        canTransfer={canTransferOwnership}
                        canRemove={canRemove}
                        disabled={pending !== null}
                        onChangeRole={(role) => void changeRole(member, role)}
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
          onInvited={({ invited, failed }) => {
            if (failed.length === 0) {
              setFeedback({
                variant: 'success',
                title:
                  invited.length === 1
                    ? copy.invite.success(invited[0]!)
                    : copy.invite.successMany(invited.length),
              })
            } else {
              setFeedback({
                variant: 'critical',
                title: copy.invite.partial(invited.length, failed.length),
                description: failed.join('、'),
              })
            }
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
  onInvited: (result: { invited: string[]; failed: string[] }) => void
}) {
  const usernameRef = useRef<HTMLInputElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const [username, setUsername] = useState('')
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [importedUsernames, setImportedUsernames] = useState<string[]>([])
  const [importError, setImportError] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitFailed, setSubmitFailed] = useState(false)
  const namesToInvite =
    importedUsernames.length > 0 ? importedUsernames : username.trim() ? [username.trim()] : []

  const loadFile = async (file: File) => {
    setImportError(null)
    setUsernameError(null)
    setImporting(true)
    try {
      const names = await parseMemberImportFile(file)
      if (names.length === 0) {
        setImportedUsernames([])
        setImportError(copy.invite.importEmpty)
        return
      }
      setImportedUsernames(names)
    } catch {
      setImportedUsernames([])
      setImportError(copy.invite.importError)
    } finally {
      setImporting(false)
    }
  }

  const submit = async () => {
    if (namesToInvite.length === 0) {
      setUsernameError(copy.invite.usernameRequired)
      usernameRef.current?.focus()
      return
    }
    setUsernameError(null)
    setSubmitFailed(false)
    setSubmitting(true)
    const invited: string[] = []
    const failed: string[] = []
    try {
      for (const name of namesToInvite) {
        try {
          await api.inviteMember(userGroup.id, name)
          invited.push(name)
        } catch {
          failed.push(name)
        }
      }
      if (invited.length === 0) {
        setSubmitFailed(true)
        return
      }
      onInvited({ invited, failed })
      onClose()
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
          content:
            namesToInvite.length > 1
              ? copy.invite.submitMany(namesToInvite.length)
              : copy.invite.submit,
          buttonType: 'primary',
          loading: submitting,
          disabled: submitting || importing,
          onClick: () => void submit(),
        },
      ]}
    >
      <form
        autoComplete="off"
        onSubmit={(event) => {
          event.preventDefault()
          if (!submitting && !importing) void submit()
        }}
      >
        <Stack gap="normal">
          {submitFailed ? (
            <Banner variant="critical">
              <Banner.Title>{copy.invite.failureTitle}</Banner.Title>
              <Banner.Description>{copy.invite.failureNext}</Banner.Description>
            </Banner>
          ) : null}
          <FormControl
            required={importedUsernames.length === 0}
            disabled={submitting}
            id="invite-member-username"
          >
            <FormControl.Label>{copy.invite.usernameLabel}</FormControl.Label>
            <TextInput
              ref={usernameRef}
              block
              name="invite-member-username"
              autoComplete="off"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder={copy.invite.usernamePlaceholder}
            />
            {usernameError ? (
              <FormControl.Validation variant="error">{usernameError}</FormControl.Validation>
            ) : null}
          </FormControl>
          <FormControl disabled={submitting || importing}>
            <FormControl.Label htmlFor="invite-member-file">
              {copy.invite.importLabel}
            </FormControl.Label>
            <input
              ref={fileRef}
              className={styles.fileInput}
              id="invite-member-file"
              aria-label={copy.invite.importLabel}
              type="file"
              accept=".csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ''
                if (file) void loadFile(file)
              }}
            />
            <FormControl.Caption>{copy.invite.importCaption}</FormControl.Caption>
            {importError ? (
              <FormControl.Validation variant="error">{importError}</FormControl.Validation>
            ) : null}
          </FormControl>
          {importedUsernames.length > 0 ? (
            <p className={styles.importSummary}>
              {copy.invite.importCount(importedUsernames.length)}
              {importedUsernames.slice(0, 8).join('、')}
              {importedUsernames.length > 8 ? '…' : ''}
            </p>
          ) : null}
        </Stack>
      </form>
    </Dialog>
  )
}

function MemberActionsMenu({
  member,
  nextRole,
  canTransfer,
  canRemove,
  disabled,
  onChangeRole,
  onTransfer,
  onRemove,
}: {
  member: Member
  nextRole: 'admin' | 'member' | null
  canTransfer: boolean
  canRemove: boolean
  disabled: boolean
  onChangeRole: (role: 'admin' | 'member') => void
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
          {nextRole ? (
            <ActionList.Item disabled={disabled} onSelect={() => onChangeRole(nextRole)}>
              {copy.role.action(nextRole)}
            </ActionList.Item>
          ) : null}
          {nextRole && (canTransfer || canRemove) ? <ActionList.Divider /> : null}
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

function nextMembershipRole(role: MembershipRole): 'admin' | 'member' | null {
  if (role === 'member') return 'admin'
  if (role === 'admin') return 'member'
  return null
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
