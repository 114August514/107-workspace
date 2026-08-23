// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App, ProductRoutes } from '../../src/App'
import { api } from '../../src/api/client'
import type {
  ActivityPage,
  Home,
  LegacyWorkspaceContext,
  Member,
  ProjectPage,
  UserGroup,
} from '../../src/api/types'
import { UserGroupPage } from '../../src/pages/UserGroupPage'

const group: UserGroup = {
  id: 'grp_lab',
  name: 'Research Lab',
  description: 'Governance only',
  created_by_id: 'usr_alice',
  created_at: '2026-08-17T00:00:00Z',
  role: 'owner',
  capabilities: ['user_group.view', 'member.view', 'member.manage'],
}

const homeState = {
  data: {
    user: { id: 'usr_alice', username: 'alice', display_name: 'Alice', email: null },
    user_groups: [group],
    personal_resource_context_id: 'ws_personal_alice',
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
    vi.spyOn(api, 'getLegacyWorkspaceContext').mockResolvedValue({
      ...group,
      kind: 'collaborative',
      owner_id: 'usr_alice',
      default_environment_version_id: null,
      capabilities: ['user_group.view', 'project.view', 'project.create'],
    } as LegacyWorkspaceContext)
    vi.spyOn(api, 'listProjects').mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
      has_more: false,
    } as ProjectPage)
    vi.spyOn(api, 'listWorkspaceActivities').mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
      has_more: false,
    } as ActivityPage)
    vi.spyOn(api, 'listEntitlements').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])
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
    expect(document.body.textContent).not.toMatch(/旧|Workspace|Legacy|兼容/)
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

  it('renders a collaborative resource context with normal product labels', async () => {
    render(
      <MemoryRouter initialEntries={['/workspaces/grp_lab']}>
        <ProductRoutes username="alice" home={homeState} />
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: 'Research Lab' })
    expect(screen.getByText('User Group')).toBeInTheDocument()
    expect(screen.getByText('Project')).toBeInTheDocument()
    expect(screen.getByText('默认运行环境')).toBeInTheDocument()
    expect(screen.getByText('活动')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: '可用算力' }))
    expect(screen.getByText('这里显示你本人拥有的算力方案使用资格')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Resource Entitlement 属于用户本人，提交 Run 时按发起用户的资格校验；成员身份不会转移算力资格。',
      ),
    ).toBeInTheDocument()
    expect(await screen.findByText('你当前没有可用的算力方案资格')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /创建 Project/ })).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/旧|Workspace|Legacy|兼容|迁移/)
  })

  it('keeps existing personal data accessible without a create Project action', async () => {
    vi.mocked(api.getLegacyWorkspaceContext).mockResolvedValueOnce({
      id: 'ws_personal_alice',
      name: 'Alice personal data',
      kind: 'personal',
      owner_id: 'usr_alice',
      default_environment_version_id: null,
      role: 'owner',
      capabilities: ['project.view', 'project.create'],
    })

    render(
      <MemoryRouter initialEntries={['/workspaces/ws_personal_alice']}>
        <ProductRoutes username="alice" home={homeState} />
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: '个人资源' })
    expect(screen.getByText('Project')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /创建 Project/ })).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/旧|Workspace|Legacy|兼容/)
  })
})
