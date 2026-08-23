// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ProductRoutes } from '../../src/App'
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

  it('shows governance with a normal resource entry and no implementation wording', async () => {
    render(
      <MemoryRouter initialEntries={['/user-groups/grp_lab']}>
        <Routes>
          <Route path="/user-groups/:userGroupId" element={<UserGroupPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: 'Research Lab' })

    expect(screen.getAllByText('成员').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: '查看 Project 与配置' })).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/旧|Workspace|Legacy|兼容/)
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
