// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../../src/App'
import { api } from '../../src/api/client'
import type { Home, Member, UserGroup } from '../../src/api/types'
import { UserGroupPage } from '../../src/pages/UserGroupPage'

const group: UserGroup = {
  id: 'grp_lab',
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
  ],
}

const homeState = {
  data: {
    user: { id: 'usr_alice', username: 'alice', display_name: 'Alice', email: null },
    user_groups: [group],
    personal_execution_context: {
      owner: { kind: 'user', id: 'usr_alice', display_name: 'Alice' },
      entitlements: [],
    },
    recent_projects: [],
    recent_runs: [],
  } satisfies Home,
  loading: false,
  error: undefined,
  reload: vi.fn(),
}

const member: Member = {
  user_id: 'usr_alice',
  username: 'alice',
  display_name: 'Alice',
  role: 'owner',
  status: 'active',
}

describe('UserGroupPage governance boundary', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getUserGroup').mockResolvedValue(group)
    vi.spyOn(api, 'listMembers').mockResolvedValue([member])
    vi.spyOn(api, 'home').mockResolvedValue(homeState.data)
    vi.spyOn(api, 'unreadCount').mockResolvedValue(0)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-63-01/02 keeps identity and membership governance on one Primer surface', async () => {
    render(
      <MemoryRouter initialEntries={['/user-groups/grp_lab']}>
        <Routes>
          <Route path="/user-groups/:userGroupId" element={<UserGroupPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: 'Research Lab' })

    expect(screen.getByText('User Group')).toBeInTheDocument()
    expect(screen.getAllByText('所有者').length).toBeGreaterThan(0)
    expect(screen.getByText('Governance only')).toBeInTheDocument()
    const membersSection = screen.getByRole('region', { name: '成员' })
    const membersHeading = within(membersSection).getByRole('heading', { name: '成员' })
    expect(
      within(membersHeading.parentElement!).getByRole('button', { name: '邀请成员' }),
    ).toBeVisible()
    expect(
      within(membersSection).getByText('管理成员及其在这个 User Group 中的权限。'),
    ).toBeVisible()
    const identityRail = screen.getByRole('complementary', { name: 'User Group 身份' })
    expect(within(identityRail).getByText('成员')).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'User Group 内容' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '查看 Project 与配置' })).not.toBeInTheDocument()
  })

  it('REQ-63-01 composes with AppShell using exactly one main landmark', async () => {
    render(
      <MemoryRouter initialEntries={['/user-groups/grp_lab']}>
        <App />
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: 'Research Lab' })
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getByRole('complementary', { name: '页面引导' })).toHaveTextContent(
      '这里管理 User Group 的成员与协作关系。Project、资源和运行配置在各自页面中管理。',
    )
  })
})
