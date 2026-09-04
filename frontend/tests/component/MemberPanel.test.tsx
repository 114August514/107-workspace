// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '../../src/api/client'
import type { Member, UserGroup } from '../../src/api/types'
import { MemberPanel } from '../../src/components/workspace/MemberPanel'
import { parseMemberImportFile } from '../../src/components/workspace/parseMemberImport'

const ownerGroup: UserGroup = {
  id: 'ugrp_lab',
  name: 'Research Lab',
  description: 'Governance only',
  created_by_id: 'usr_alice',
  created_at: '2026-08-17T00:00:00Z',
  role: 'owner',
  capabilities: [
    'user_group.view',
    'member.view',
    'member.invite',
    'member.remove',
    'member.role.manage',
    'ownership.transfer',
  ],
}

const members: Member[] = [
  {
    user_id: 'usr_alice',
    username: 'alice',
    display_name: 'Alice',
    role: 'owner',
    status: 'active',
    capabilities: [],
  },
  {
    user_id: 'usr_bob',
    username: 'bob',
    display_name: 'Bob',
    role: 'member',
    status: 'active',
    capabilities: ['member.remove', 'member.role.manage'],
  },
  {
    user_id: 'usr_carol',
    username: 'carol',
    display_name: 'Carol',
    role: 'admin',
    status: 'active',
    capabilities: ['member.remove', 'member.role.manage'],
  },
]

const adminGroup: UserGroup = {
  ...ownerGroup,
  role: 'admin',
  capabilities: ['user_group.view', 'member.view', 'member.invite', 'member.remove'],
}

const adminMembers: Member[] = [
  { ...members[0]!, capabilities: [] },
  { ...members[2]!, capabilities: [] },
  { ...members[1]!, capabilities: ['member.remove'] },
]

describe('MemberPanel governance', () => {
  beforeEach(() => {
    vi.spyOn(api, 'listMembers').mockResolvedValue(members)
    vi.spyOn(api, 'inviteMember').mockResolvedValue(members[1]!)
    vi.spyOn(api, 'changeMemberRole').mockResolvedValue({ ...members[1]!, role: 'admin' })
    vi.spyOn(api, 'removeMember').mockResolvedValue(undefined)
    vi.spyOn(api, 'transferUserGroupOwnership').mockResolvedValue(undefined)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-66-01 invites by username as a fixed Member without role controls', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    await screen.findByText('Alice')
    fireEvent.click(screen.getByRole('button', { name: '邀请成员' }))
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    expect(screen.queryByText('角色')).not.toBeInTheDocument()
    expect(screen.queryByText('Owner 只能通过所有权转让产生。')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/用户名/), { target: { value: 'dave' } })
    fireEvent.click(screen.getByRole('button', { name: '发送邀请' }))

    expect(await screen.findByText('已向 dave 发送邀请')).toBeInTheDocument()
    expect(api.inviteMember).toHaveBeenCalledWith('ugrp_lab', 'dave')
    expect(api.listMembers).toHaveBeenCalledTimes(2)
  })

  it('parses CSV usernames from a headered first column', async () => {
    const file = new File(['username\neve\nfrank\n'], 'members.csv', { type: 'text/csv' })
    await expect(parseMemberImportFile(file)).resolves.toEqual(['eve', 'frank'])
  })

  it('从 CSV 批量导入用户名并逐个发送邀请', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)
    await screen.findByText('Alice')
    fireEvent.click(screen.getByRole('button', { name: '邀请成员' }))

    const file = new File(['username\neve\nfrank\n'], 'members.csv', { type: 'text/csv' })
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })

    expect(await screen.findByText(/将邀请 2 人/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '发送 2 个邀请' }))

    expect(await screen.findByText('已向 2 人发送邀请')).toBeInTheDocument()
    expect(api.inviteMember).toHaveBeenCalledWith('ugrp_lab', 'eve')
    expect(api.inviteMember).toHaveBeenCalledWith('ugrp_lab', 'frank')
  })

  it('REQ-66-02 renders roles as static identity and projects target capabilities into actions', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    const alice = await screen.findByTestId('member-usr_alice')
    const bob = screen.getByTestId('member-usr_bob')
    const carol = screen.getByTestId('member-usr_carol')
    expect(within(alice).getByText('所有者')).toBeInTheDocument()
    expect(within(bob).getByText('成员')).toBeInTheDocument()
    expect(within(carol).getByText('管理员')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /修改 .* 的角色/ })).not.toBeInTheDocument()
    expect(
      within(alice).queryByRole('button', { name: 'alice 的更多操作' }),
    ).not.toBeInTheDocument()

    fireEvent.click(within(bob).getByRole('button', { name: 'bob 的更多操作' }))
    expect(await screen.findByRole('menuitem', { name: '设为管理员' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '转让所有权' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '移除成员' })).toBeInTheDocument()
  })

  it('REQ-66-03 changes the one applicable role and reloads server-authoritative members', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    const bob = await screen.findByTestId('member-usr_bob')
    fireEvent.click(within(bob).getByRole('button', { name: 'bob 的更多操作' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '设为管理员' }))

    await waitFor(() =>
      expect(api.changeMemberRole).toHaveBeenCalledWith('ugrp_lab', 'usr_bob', 'admin'),
    )
    expect(await screen.findByText('已将 bob 设为管理员')).toBeInTheDocument()
    expect(api.listMembers).toHaveBeenCalledTimes(2)
  })

  it('REQ-66-03 demotes an Admin through the same capability-projected action', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    const carol = await screen.findByTestId('member-usr_carol')
    fireEvent.click(within(carol).getByRole('button', { name: 'carol 的更多操作' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '设为成员' }))

    await waitFor(() =>
      expect(api.changeMemberRole).toHaveBeenCalledWith('ugrp_lab', 'usr_carol', 'member'),
    )
    expect(await screen.findByText('已将 carol 设为成员')).toBeInTheDocument()
  })

  it('REQ-66-04 lets Admin perform only daily actions projected by each target fixture', async () => {
    vi.mocked(api.listMembers).mockResolvedValue(adminMembers)
    render(<MemberPanel userGroup={adminGroup} />)

    const owner = await screen.findByTestId('member-usr_alice')
    const admin = screen.getByTestId('member-usr_carol')
    const member = screen.getByTestId('member-usr_bob')
    expect(within(owner).queryByRole('button', { name: /更多操作/ })).not.toBeInTheDocument()
    expect(within(admin).queryByRole('button', { name: /更多操作/ })).not.toBeInTheDocument()
    fireEvent.click(within(member).getByRole('button', { name: 'bob 的更多操作' }))
    expect(await screen.findByRole('menuitem', { name: '移除成员' })).toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: /设为/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('menuitem', { name: '转让所有权' })).not.toBeInTheDocument()
  })

  it('REQ-66-05 keeps ownership transfer separate and explicitly confirmed', async () => {
    const onUserGroupChanged = vi.fn()
    render(<MemberPanel userGroup={ownerGroup} onUserGroupChanged={onUserGroupChanged} />)

    const bob = await screen.findByTestId('member-usr_bob')
    fireEvent.click(within(bob).getByRole('button', { name: 'bob 的更多操作' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '转让所有权' }))
    expect(api.transferUserGroupOwnership).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '转让所有权' }))

    await waitFor(() =>
      expect(api.transferUserGroupOwnership).toHaveBeenCalledWith('ugrp_lab', 'usr_bob'),
    )
    expect(await screen.findByText('已将 User Group 所有权转让给 bob')).toBeInTheDocument()
    expect(onUserGroupChanged).toHaveBeenCalledOnce()
  })

  it('REQ-66-06 explicitly confirms removal projected by the target capability', async () => {
    render(<MemberPanel userGroup={ownerGroup} />)

    const bob = await screen.findByTestId('member-usr_bob')
    fireEvent.click(within(bob).getByRole('button', { name: 'bob 的更多操作' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '移除成员' }))
    expect(api.removeMember).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '移除成员' }))

    await waitFor(() => expect(api.removeMember).toHaveBeenCalledWith('ugrp_lab', 'usr_bob'))
    expect(await screen.findByText('已移除 bob')).toBeInTheDocument()
  })

  it('REQ-66-07 uses stable invite failure guidance', async () => {
    vi.mocked(api.inviteMember).mockRejectedValueOnce(
      new ApiError(409, 'conflict', 'unstable backend invite message', []),
    )
    render(<MemberPanel userGroup={ownerGroup} />)
    await screen.findByText('Alice')
    fireEvent.click(screen.getByRole('button', { name: '邀请成员' }))
    fireEvent.change(screen.getByLabelText(/用户名/), { target: { value: 'dave' } })
    fireEvent.click(screen.getByRole('button', { name: '发送邀请' }))
    expect(await screen.findByText('邀请发送失败。')).toBeInTheDocument()
    expect(screen.getByText('请确认用户名后重试。')).toBeInTheDocument()
    expect(screen.queryByText('unstable backend invite message')).not.toBeInTheDocument()
  })

  it('REQ-66-07 uses stable role failure guidance and keeps the action retryable', async () => {
    vi.mocked(api.changeMemberRole).mockRejectedValueOnce(
      new ApiError(409, 'conflict', 'unstable backend role message', []),
    )
    render(<MemberPanel userGroup={ownerGroup} />)

    const bob = await screen.findByTestId('member-usr_bob')
    fireEvent.click(within(bob).getByRole('button', { name: 'bob 的更多操作' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '设为管理员' }))

    expect(await screen.findByText('角色修改失败。')).toBeInTheDocument()
    expect(screen.getByText('请确认成员仍在 User Group 中并重试。')).toBeInTheDocument()
    expect(screen.queryByText('unstable backend role message')).not.toBeInTheDocument()
    expect(within(bob).getByRole('button', { name: 'bob 的更多操作' })).toBeEnabled()
  })
})
