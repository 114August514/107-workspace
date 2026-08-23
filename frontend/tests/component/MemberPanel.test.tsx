// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '../../src/api/client'
import type { Member, UserGroup } from '../../src/api/types'
import { MemberPanel } from '../../src/components/workspace/MemberPanel'

const ownerGroup: UserGroup = {
  id: 'ugrp_lab',
  name: 'Research Lab',
  description: 'Governance only',
  created_by_id: 'usr_alice',
  created_at: '2026-08-17T00:00:00Z',
  role: 'owner',
  capabilities: ['user_group.view', 'member.view', 'member.manage', 'ownership.transfer'],
}

const members: Member[] = [
  {
    user_id: 'usr_alice',
    username: 'alice',
    display_name: 'Alice',
    role: 'owner',
    status: 'active',
  },
  {
    user_id: 'usr_bob',
    username: 'bob',
    display_name: 'Bob',
    role: 'member',
    status: 'active',
  },
  {
    user_id: 'usr_carol',
    username: 'carol',
    display_name: 'Carol',
    role: 'admin',
    status: 'invited',
  },
]

describe('MemberPanel governance', () => {
  beforeEach(() => {
    vi.spyOn(api, 'listMembers').mockResolvedValue(members)
    vi.spyOn(api, 'inviteMember').mockResolvedValue(members[2]!)
    vi.spyOn(api, 'changeMemberRole').mockResolvedValue({ ...members[1]!, role: 'admin' })
    vi.spyOn(api, 'removeMember').mockResolvedValue(undefined)
    vi.spyOn(api, 'transferUserGroupOwnership').mockResolvedValue(undefined)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-63-03 shows only canonical roles without exposing owner/invited mutation', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    const alice = await screen.findByTestId('member-usr_alice')
    const bob = screen.getByTestId('member-usr_bob')
    const carol = screen.getByTestId('member-usr_carol')

    expect(within(alice).getByText('所有者')).toBeInTheDocument()
    expect(within(alice).getByText('已加入')).toBeInTheDocument()
    expect(within(alice).queryByRole('button', { name: /修改 .* 的角色/ })).not.toBeInTheDocument()
    const bobRole = within(bob).getByRole('button', { name: '修改 bob 的角色，当前成员' })
    expect(bobRole).toBeInTheDocument()
    expect(within(carol).queryByRole('button', { name: /修改 .* 的角色/ })).not.toBeInTheDocument()
    expect(within(carol).queryByRole('button', { name: /转让给/ })).not.toBeInTheDocument()
    expect(within(carol).getByRole('button', { name: '移除 carol' })).toBeInTheDocument()
  })

  it('REQ-63-04 invites a member and reports a server failure in the dialog', async () => {
    let rejectInvite!: (error: unknown) => void
    vi.mocked(api.inviteMember).mockImplementationOnce(
      () =>
        new Promise<Member>((_resolve, reject) => {
          rejectInvite = reject
        }),
    )
    render(<MemberPanel userGroup={ownerGroup} />)

    await screen.findByText('Alice')
    fireEvent.click(screen.getByRole('button', { name: '邀请成员' }))
    expect(screen.getAllByRole('radio')).toHaveLength(2)
    expect(screen.getByRole('radio', { name: '成员' })).toBeChecked()
    expect(screen.getByText('可以参与 User Group 中的项目、资源与计算工作')).toBeInTheDocument()
    expect(screen.getByText('具有成员能力，并可以管理成员和 User Group')).toBeInTheDocument()
    const username = screen.getByLabelText(/用户名/)
    fireEvent.change(username, { target: { value: 'carol' } })
    fireEvent.click(screen.getByRole('radio', { name: '管理员' }))
    expect(screen.getByRole('radio', { name: '管理员' })).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: '发送邀请' }))

    await waitFor(() => expect(api.inviteMember).toHaveBeenCalledWith('ugrp_lab', 'carol', 'admin'))
    expect(username).toBeDisabled()
    expect(screen.getByRole('radio', { name: '成员' })).toBeDisabled()
    expect(screen.getByRole('radio', { name: '管理员' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '发送邀请' })).toBeDisabled()

    rejectInvite(new ApiError(409, 'conflict', 'unstable backend invite message', []))
    expect(await screen.findByText('邀请发送失败。')).toBeInTheDocument()
    expect(screen.getByText('请确认用户名和角色后重试。')).toBeInTheDocument()
    expect(screen.queryByText('unstable backend invite message')).not.toBeInTheDocument()
  })

  it('keeps focus on an empty invite username and does not call the API', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    await screen.findByText('Alice')
    fireEvent.click(screen.getByRole('button', { name: '邀请成员' }))
    fireEvent.click(screen.getByRole('button', { name: '发送邀请' }))

    expect(await screen.findByText('请填写用户名')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /用户名/ })).toHaveFocus()
    expect(api.inviteMember).not.toHaveBeenCalled()
  })

  it('REQ-63-04 closes a successful invite flow, reports the result, and reloads members', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    await screen.findByText('Alice')
    fireEvent.click(screen.getByRole('button', { name: '邀请成员' }))
    fireEvent.change(screen.getByLabelText(/用户名/), { target: { value: 'dave' } })
    fireEvent.click(screen.getByRole('button', { name: '发送邀请' }))

    expect(await screen.findByText('已向 dave 发送邀请')).toBeInTheDocument()
    expect(api.inviteMember).toHaveBeenCalledWith('ugrp_lab', 'dave', 'member')
    expect(screen.queryByRole('dialog', { name: '邀请成员' })).not.toBeInTheDocument()
    expect(api.listMembers).toHaveBeenCalledTimes(2)
  })

  it('REQ-63-05 changes an active member role and reloads server-authoritative data', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    const role = await screen.findByRole('button', { name: '修改 bob 的角色，当前成员' })
    fireEvent.click(role)
    expect(await screen.findAllByRole('menuitemradio')).toHaveLength(2)
    fireEvent.click(screen.getByRole('menuitemradio', { name: '管理员' }))

    await waitFor(() =>
      expect(api.changeMemberRole).toHaveBeenCalledWith('ugrp_lab', 'usr_bob', 'admin'),
    )
    expect(await screen.findByText('bob 的角色已改为管理员')).toBeInTheDocument()
    expect(api.listMembers).toHaveBeenCalledTimes(2)
  })

  it('disables role menus while a server-authoritative role mutation is pending', async () => {
    let resolveChange!: (member: Member) => void
    vi.mocked(api.changeMemberRole).mockImplementationOnce(
      () =>
        new Promise<Member>((resolve) => {
          resolveChange = resolve
        }),
    )
    render(<MemberPanel userGroup={ownerGroup} />)

    const role = await screen.findByRole('button', { name: '修改 bob 的角色，当前成员' })
    fireEvent.click(role)
    fireEvent.click(await screen.findByRole('menuitemradio', { name: '管理员' }))

    expect(role).toBeDisabled()
    resolveChange({
      display_name: 'Bob',
      role: 'admin',
      status: 'active',
      user_id: 'usr_bob',
      username: 'bob',
    })
    await waitFor(() => expect(role).toBeEnabled())
  })

  it('uses stable action copy when a role change fails and lets the user try again', async () => {
    vi.mocked(api.changeMemberRole).mockRejectedValueOnce(
      new ApiError(409, 'conflict', 'unstable backend role message', []),
    )
    render(<MemberPanel userGroup={ownerGroup} />)

    const role = await screen.findByRole('button', { name: '修改 bob 的角色，当前成员' })
    fireEvent.click(role)
    fireEvent.click(await screen.findByRole('menuitemradio', { name: '管理员' }))

    expect(await screen.findByText('角色修改失败。')).toBeInTheDocument()
    expect(screen.getByText('请确认成员仍在 User Group 中并重试。')).toBeInTheDocument()
    expect(screen.queryByText('unstable backend role message')).not.toBeInTheDocument()
    expect(role).toBeEnabled()
  })

  it('REQ-63-06 requires explicit danger confirmation before removing a member', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    const bob = await screen.findByTestId('member-usr_bob')
    fireEvent.click(within(bob).getByRole('button', { name: '移除 bob' }))
    expect(api.removeMember).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '移除成员' }))

    await waitFor(() => expect(api.removeMember).toHaveBeenCalledWith('ugrp_lab', 'usr_bob'))
    expect(await screen.findByText('已移除 bob')).toBeInTheDocument()
  })

  it('adds the stable capability-gated ownership transfer with explicit confirmation', async () => {
    const onUserGroupChanged = vi.fn()
    render(<MemberPanel userGroup={ownerGroup} onUserGroupChanged={onUserGroupChanged} />)

    const bob = await screen.findByTestId('member-usr_bob')
    fireEvent.click(within(bob).getByRole('button', { name: '转让给 bob' }))
    expect(api.transferUserGroupOwnership).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '转让所有权' }))

    await waitFor(() =>
      expect(api.transferUserGroupOwnership).toHaveBeenCalledWith('ugrp_lab', 'usr_bob'),
    )
    expect(await screen.findByText('已将 User Group 所有权转让给 bob')).toBeInTheDocument()
    expect(onUserGroupChanged).toHaveBeenCalledOnce()
  })

  it('REQ-63-07 hides governance actions when capability is absent', async () => {
    render(
      <MemberPanel
        userGroup={{
          ...ownerGroup,
          role: 'member',
          capabilities: ['user_group.view', 'member.view'],
        }}
      />,
    )

    await screen.findByText('Alice')
    expect(screen.queryByRole('button', { name: '邀请成员' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /修改 .* 的角色/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /移除|转让/ })).not.toBeInTheDocument()
  })

  it('REQ-63-08 gives an actionable empty state', async () => {
    vi.mocked(api.listMembers).mockResolvedValueOnce([])
    render(<MemberPanel userGroup={ownerGroup} />)

    expect(await screen.findByText('这个 User Group 还没有成员。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '邀请成员' })).toBeInTheDocument()
  })

  it('REQ-63-08 exposes a retry path after members fail to load', async () => {
    vi.mocked(api.listMembers)
      .mockRejectedValueOnce(new Error('network unavailable'))
      .mockResolvedValueOnce(members)
    render(<MemberPanel userGroup={ownerGroup} />)

    expect(await screen.findByText('请求失败。')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重试' }))

    expect(await screen.findByText('Alice')).toBeInTheDocument()
    expect(api.listMembers).toHaveBeenCalledTimes(2)
  })
})
