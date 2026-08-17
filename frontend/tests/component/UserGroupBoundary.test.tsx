// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ProductRoutes } from '../../src/App'
import { api } from '../../src/api/client'
import type {
  ActivityPage,
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
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('shows governance and keeps legacy downstream scopes off the User Group surface', async () => {
    render(
      <MemoryRouter initialEntries={['/user-groups/grp_lab']}>
        <Routes>
          <Route path="/user-groups/:userGroupId" element={<UserGroupPage />} />
        </Routes>
      </MemoryRouter>,
    )

    await screen.findByRole('heading', { name: 'Research Lab' })

    expect(screen.getAllByText('成员').length).toBeGreaterThan(0)
    expect(screen.queryByText('Project')).not.toBeInTheDocument()
    expect(screen.queryByText('默认环境')).not.toBeInTheDocument()
    expect(screen.queryByText('变量与 Secret')).not.toBeInTheDocument()
    expect(screen.queryByText('近期活动')).not.toBeInTheDocument()
    expect(screen.queryByText('资源权益')).not.toBeInTheDocument()
  })

  it('routes a persisted Workspace target to the bounded compatibility page', async () => {
    render(
      <MemoryRouter initialEntries={['/workspaces/grp_lab']}>
        <ProductRoutes username="alice" />
      </MemoryRouter>,
    )

    expect(await screen.findByText('旧 Workspace 下游兼容视图')).toBeInTheDocument()
    expect(screen.getByText('Workspace Project（兼容）')).toBeInTheDocument()
    expect(screen.queryByText('我的 User Group')).not.toBeInTheDocument()
  })
})
