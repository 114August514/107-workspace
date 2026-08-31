// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { Member, UserGroup } from '../../src/api/types'
import { MembersSection } from '../../src/components/usergroup/MembersSection'
import { UserGroupProvider } from '../../src/components/usergroup/UserGroupHeaderNav'
import { UserGroupPage } from '../../src/pages/UserGroupPage'

const ownerGroup: UserGroup = {
  id: 'grp_lab',
  name: 'Research Lab',
  description: '',
  created_by_id: 'usr_alice',
  created_at: '2026-08-17T00:00:00Z',
  role: 'owner',
  capabilities: ['user_group.view', 'user_group.update', 'member.view'],
}

const memberGroup: UserGroup = {
  ...ownerGroup,
  role: 'member',
  capabilities: ['user_group.view', 'member.view'],
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
]

function renderMembers(groupFixture: UserGroup, onMembershipChanged = vi.fn()) {
  vi.spyOn(api, 'getUserGroup').mockResolvedValue(groupFixture)
  vi.spyOn(api, 'listMembers').mockResolvedValue(members)
  return render(
    <MemoryRouter initialEntries={['/user-groups/grp_lab/members']}>
      <UserGroupProvider>
        <Routes>
          <Route
            path="/user-groups/:userGroupId"
            element={<UserGroupPage onMembershipChanged={onMembershipChanged} />}
          >
            <Route path="members" element={<MembersSection />} />
          </Route>
        </Routes>
      </UserGroupProvider>
    </MemoryRouter>,
  )
}

describe('成员退出 User Group', () => {
  beforeEach(() => {
    vi.spyOn(api, 'unreadCount').mockResolvedValue(0)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-21-20 Owner 不显示退出入口', async () => {
    renderMembers(ownerGroup)

    await screen.findByRole('region', { name: '成员' })
    expect(screen.queryByRole('heading', { name: '退出 User Group' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '退出 User Group' })).not.toBeInTheDocument()
  })

  it('REQ-21-21 Member 在确认前不调用退出接口，确认后退出并通知成员变化', async () => {
    const leave = vi.spyOn(api, 'leaveUserGroup').mockResolvedValue(undefined)
    const onMembershipChanged = vi.fn()
    renderMembers(memberGroup, onMembershipChanged)

    const leaveButton = await screen.findByRole('button', { name: '退出 User Group' })
    fireEvent.click(leaveButton)

    expect(leave).not.toHaveBeenCalled()

    const confirmInDialog = screen
      .getAllByRole('button', { name: '退出 User Group' })
      .find((button) => button.closest('[data-component="Dialog.FooterButton"]'))!
    fireEvent.click(confirmInDialog)

    await waitFor(() => expect(leave).toHaveBeenCalledWith('grp_lab'))
    await waitFor(() => expect(onMembershipChanged).toHaveBeenCalledTimes(1))
  })

  it('REQ-21-22 退出失败展示稳定文案且可重试', async () => {
    const leave = vi
      .spyOn(api, 'leaveUserGroup')
      .mockRejectedValueOnce(new Error('forbidden'))
      .mockResolvedValueOnce(undefined)
    renderMembers(memberGroup)

    const dialogConfirm = () =>
      screen
        .getAllByRole('button', { name: '退出 User Group' })
        .find((button) => button.closest('[data-component="Dialog.FooterButton"]'))!
    const panelLeave = () =>
      screen
        .getAllByRole('button', { name: '退出 User Group' })
        .find((button) => !button.closest('[data-component="Dialog.FooterButton"]'))!

    fireEvent.click(await screen.findByRole('button', { name: '退出 User Group' }))
    fireEvent.click(dialogConfirm())

    expect(await screen.findByText('退出失败。')).toBeInTheDocument()
    expect(screen.queryByText('forbidden')).not.toBeInTheDocument()

    fireEvent.click(panelLeave())
    fireEvent.click(dialogConfirm())
    await waitFor(() => expect(leave).toHaveBeenCalledTimes(2))
  })
})
