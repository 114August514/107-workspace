// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { Member, UserGroup } from '../../src/api/types'
import { OverviewSection } from '../../src/components/usergroup/OverviewSection'
import { UserGroupProvider } from '../../src/components/usergroup/UserGroupHeaderNav'
import { UserGroupPage } from '../../src/pages/UserGroupPage'

const group: UserGroup = {
  id: 'grp_lab',
  name: 'Research Lab',
  description: 'Lab description',
  created_by_id: 'usr_alice',
  created_at: '2026-08-17T00:00:00Z',
  role: 'owner',
  capabilities: ['user_group.view', 'user_group.update', 'member.view'],
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

function renderOverview() {
  return render(
    <MemoryRouter initialEntries={['/user-groups/grp_lab']}>
      <UserGroupProvider>
        <Routes>
          <Route path="/user-groups/:userGroupId" element={<UserGroupPage />}>
            <Route index element={<OverviewSection />} />
          </Route>
        </Routes>
      </UserGroupProvider>
    </MemoryRouter>,
  )
}

describe('User Group 概览分区', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getUserGroup').mockResolvedValue(group)
    vi.spyOn(api, 'listMembers').mockResolvedValue(members)
    vi.spyOn(api, 'listProjects').mockResolvedValue({
      items: [
        {
          id: 'prj_group',
          name: 'Group Project',
          description: '',
          status: 'active',
          visibility: 'owner_scope',
          environment_version_id: null,
          default_run_configuration_id: null,
          created_by: 'usr_alice',
          created_at: '2026-08-17T00:00:00Z',
          updated_at: '2026-08-21T00:00:00Z',
          owner: { kind: 'user_group', id: 'grp_lab', display_name: 'Research Lab' },
        },
      ],
      page: 1,
      page_size: 200,
      total: 1,
      has_more: false,
    })
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-21-12 身份头展示名称、角色与成员数', async () => {
    renderOverview()

    await screen.findByRole('heading', { name: 'Research Lab' })
    expect(screen.getByText('Lab description')).toBeInTheDocument()
    await screen.findByText('2 位成员')
  })

  it('REQ-21-13 Project 仓库列表：名称与查看全部入口，且不展示其他模块', async () => {
    renderOverview()

    const projectHeading = await screen.findByRole('heading', { name: 'Project', level: 2 })
    const projectRow = projectHeading.closest('section')!
    const item = await within(projectRow).findByRole('link', { name: /Group Project/ })
    expect(item).toHaveAttribute('href', '/projects/prj_group')
    const viewAll = within(projectRow).getByRole('link', { name: '查看全部' })
    expect(viewAll).toHaveAttribute('href', '/user-groups/grp_lab/projects')

    expect(screen.queryByRole('heading', { name: '共享资源' })).toBeNull()
    expect(screen.queryByRole('heading', { name: '运行环境' })).toBeNull()
    expect(screen.queryByRole('heading', { name: '近期活动' })).toBeNull()
    expect(screen.queryByRole('heading', { name: '基本信息' })).toBeNull()
  })

  it('REQ-21-14 无成员时不展示成员行', async () => {
    vi.spyOn(api, 'listMembers').mockResolvedValue([])

    renderOverview()

    await screen.findByRole('heading', { name: 'Project', level: 2 })
    expect(screen.queryByText(/位成员/)).toBeNull()
  })

  it('REQ-21-15 Project 列表失败时展示错误与重试，身份头仍渲染', async () => {
    vi.spyOn(api, 'listProjects').mockRejectedValue(new Error('boom'))

    renderOverview()

    await screen.findByRole('heading', { name: 'Research Lab' })
    await screen.findByRole('button', { name: '重试' })
  })
})
