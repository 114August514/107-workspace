// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../../src/App'
import { api } from '../../src/api/client'
import type { DeletionImpact, Home, Member, UserGroup } from '../../src/api/types'
import { MembersSection } from '../../src/components/usergroup/MembersSection'
import { OverviewSection } from '../../src/components/usergroup/OverviewSection'
import {
  UserGroupHeaderNav,
  UserGroupProvider,
} from '../../src/components/usergroup/UserGroupHeaderNav'
import { UserGroupPage } from '../../src/pages/UserGroupPage'

const ownerGroup: UserGroup = {
  id: 'grp_lab',
  name: 'Research Lab',
  description: 'Governance only',
  created_by_id: 'usr_alice',
  created_at: '2026-08-17T00:00:00Z',
  role: 'owner',
  capabilities: [
    'user_group.view',
    'user_group.update',
    'member.view',
    'member.invite',
    'member.remove',
    'member.role.manage',
  ],
}

const deletableGroup: UserGroup = {
  ...ownerGroup,
  capabilities: [...(ownerGroup.capabilities ?? []), 'user_group.delete'],
}

const memberGroup: UserGroup = {
  ...ownerGroup,
  role: 'member',
  capabilities: ['user_group.view', 'member.view'],
}

const homeData = {
  user: { id: 'usr_alice', username: 'alice', display_name: 'Alice', email: null },
  user_groups: [ownerGroup],
  personal_execution_context: {
    owner: { kind: 'user', id: 'usr_alice', display_name: 'Alice' },
    entitlements: [],
  },
  recent_projects: [],
  recent_runs: [],
} satisfies Home

const member: Member = {
  user_id: 'usr_alice',
  username: 'alice',
  display_name: 'Alice',
  role: 'owner',
  status: 'active',
}

function renderUserGroupRoute(initialEntry: string) {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <UserGroupProvider>
        {/* 镜像 AppShell 结构:分区导航由 Provider 驱动渲染在页面之外 */}
        <UserGroupHeaderNav />
        <Routes>
          <Route path="/user-groups/:userGroupId" element={<UserGroupPage />}>
            <Route index element={<OverviewSection />} />
            <Route path="members" element={<MembersSection />} />
          </Route>
        </Routes>
      </UserGroupProvider>
    </MemoryRouter>,
  )
}

describe('UserGroupPage 分区导航信息架构', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getUserGroup').mockResolvedValue(ownerGroup)
    vi.spyOn(api, 'listMembers').mockResolvedValue([member])
    vi.spyOn(api, 'home').mockResolvedValue(homeData)
    vi.spyOn(api, 'unreadCount').mockResolvedValue(0)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-21-01 header 呈现组身份，分区导航包含全部 Owner 可见面', async () => {
    renderUserGroupRoute('/user-groups/grp_lab')

    await screen.findByRole('heading', { name: 'Research Lab' })
    expect(screen.getAllByText('所有者').length).toBeGreaterThan(0)
    expect(screen.getByText('Governance only')).toBeInTheDocument()

    const nav = screen.getByRole('navigation', { name: 'User Group 分区导航' })
    const links = within(nav).getAllByRole('link')
    const labels = links.map((link) => link.textContent)
    expect(labels).toEqual([
      'Overview',
      'Project',
      'Shared Resource',
      'Environment',
      'Members',
      'Settings',
    ])
  })

  it('REQ-21-02 基础 URL 渲染概览分区，成员分区渲染成员治理面板', async () => {
    renderUserGroupRoute('/user-groups/grp_lab/members')

    const membersSection = await screen.findByRole('region', { name: '成员' })
    const membersHeading = within(membersSection).getByRole('heading', { name: '成员' })
    expect(
      within(membersHeading.parentElement!).getByRole('button', { name: '邀请成员' }),
    ).toBeVisible()
    expect(
      within(membersSection).getByText('管理成员及其在这个 User Group 中的权限。'),
    ).toBeVisible()
  })

  it('REQ-21-21 当前分区在导航中带 aria-current 选中态', async () => {
    renderUserGroupRoute('/user-groups/grp_lab/members')

    const nav = await screen.findByRole('navigation', { name: 'User Group 分区导航' })
    const membersLink = within(nav).getByRole('link', { name: 'Members' })
    expect(membersLink).toHaveAttribute('aria-current', 'page')
    expect(within(nav).getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current')
    expect(within(nav).getByRole('link', { name: 'Project' })).not.toHaveAttribute('aria-current')
  })

  it('REQ-21-22 基础 URL 下概览分区带 aria-current 选中态', async () => {
    renderUserGroupRoute('/user-groups/grp_lab')

    await screen.findByRole('heading', { name: 'Research Lab' })
    const nav = screen.getByRole('navigation', { name: 'User Group 分区导航' })
    expect(within(nav).getByRole('link', { name: 'Overview' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(within(nav).getByRole('link', { name: 'Members' })).not.toHaveAttribute('aria-current')
  })

  it('REQ-21-03 Member 角色显示设置分区以便退出', async () => {
    vi.spyOn(api, 'getUserGroup').mockResolvedValue(memberGroup)
    renderUserGroupRoute('/user-groups/grp_lab')

    await screen.findByRole('heading', { name: 'Research Lab' })
    const nav = screen.getByRole('navigation', { name: 'User Group 分区导航' })
    expect(within(nav).getByRole('link', { name: 'Settings' })).toHaveAttribute(
      'href',
      '/user-groups/grp_lab/settings',
    )
    expect(within(nav).getByText('Overview')).toBeInTheDocument()
    expect(within(nav).getByText('Members')).toBeInTheDocument()
  })

  it('REQ-21-04 不出现旧导航与 Workspace 术语', async () => {
    renderUserGroupRoute('/user-groups/grp_lab')

    await screen.findByRole('heading', { name: 'Research Lab' })
    expect(screen.queryByRole('navigation', { name: 'User Group 内容' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '查看 Project 与配置' })).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/Workspace|旧|Legacy|兼容/)
    expect(screen.queryByRole('complementary', { name: 'User Group 身份' })).not.toBeInTheDocument()
  })

  it('REQ-21-05 与 AppShell 组合时保持单一 main landmark 与新页面引导', async () => {
    render(
      <MemoryRouter initialEntries={['/user-groups/grp_lab']}>
        <App />
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: 'Research Lab' })
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(screen.getByRole('complementary', { name: '页面引导' })).toHaveTextContent(
      '这里管理 User Group 的成员、设置和组拥有的 Project、共享资源与运行环境；资源详情在各自页面打开。',
    )
  })

  it('显示删除影响并要求危险确认', async () => {
    vi.mocked(api.getUserGroup).mockResolvedValue(deletableGroup)
    const impact: DeletionImpact = {
      resource_type: 'user_group',
      resource_id: 'grp_lab',
      resource_name: 'Research Lab',
      can_delete: true,
      problems: [],
      items: [
        { kind: 'memberships', count: 1 },
        { kind: 'projects', count: 0 },
      ],
    }
    vi.spyOn(api, 'getUserGroupDeletionImpact').mockResolvedValue(impact)
    const deleteGroup = vi.spyOn(api, 'deleteUserGroup').mockResolvedValue()

    renderUserGroupRoute('/user-groups/grp_lab')

    await screen.findByRole('button', { name: '删除 User Group' })
    screen.getByRole('button', { name: '删除 User Group' }).click()
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText('Membership：1')).toBeInTheDocument()
    expect(
      within(dialog).getByText('删除会结束这个 User Group 的 Membership、授权和配置生命周期。'),
    ).toBeInTheDocument()
    within(dialog).getByRole('button', { name: '删除 User Group' }).click()
    await waitFor(() => expect(deleteGroup).toHaveBeenCalledWith('grp_lab'))
  })
})
