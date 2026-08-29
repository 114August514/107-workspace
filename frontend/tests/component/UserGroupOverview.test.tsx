// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { ActivityPage, Member, UserGroup } from '../../src/api/types'
import { OverviewSection } from '../../src/components/usergroup/OverviewSection'
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

const activities: ActivityPage = {
  items: [
    {
      id: 'act-1',
      action: 'member_joined',
      actor_id: 'usr_bob',
      actor_name: 'Bob',
      created_at: '2026-08-18T00:00:00Z',
      detail: '',
      target_id: 'usr_bob',
      target_name: 'Bob',
      target_type: 'member',
    },
    {
      id: 'act-2',
      action: 'project_created',
      actor_id: 'usr_alice',
      actor_name: 'Alice',
      created_at: '2026-08-19T00:00:00Z',
      detail: '',
      target_id: 'prj_group',
      target_name: 'Group Project',
      target_type: 'project',
    },
  ],
  page: 1,
  page_size: 10,
  total: 2,
  has_more: false,
}

function renderOverview() {
  return render(
    <MemoryRouter initialEntries={['/user-groups/grp_lab']}>
      <Routes>
        <Route path="/user-groups/:userGroupId" element={<UserGroupPage />}>
          <Route index element={<OverviewSection />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('User Group 概览分区', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getUserGroup').mockResolvedValue(group)
    vi.spyOn(api, 'listMembers').mockResolvedValue(members)
    vi.spyOn(api, 'listUserGroupActivities').mockResolvedValue(activities)
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
          updated_at: null,
          owner: { kind: 'user_group', id: 'grp_lab', display_name: 'Research Lab' },
        },
      ],
      page: 1,
      page_size: 200,
      total: 1,
      has_more: false,
    })
    vi.spyOn(api, 'listSharedResources').mockResolvedValue([])
    vi.spyOn(api, 'environments').mockResolvedValue([])
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-21-12 汇总基本信息：创建者经成员解析、成员数与我的角色', async () => {
    renderOverview()

    const section = await screen.findByRole('region', { name: '基本信息' })
    await screen.findByText('Alice', { selector: 'dd' })
    expect(within(section).getByText('2 位')).toBeInTheDocument()
    expect(within(section).getByText('所有者')).toBeInTheDocument()
  })

  it('REQ-21-13 资产计数卡来自组拥有过滤并提供查看全部入口', async () => {
    renderOverview()

    const projectHeading = await screen.findByRole('heading', { name: 'Project', level: 3 })
    const projectCard = projectHeading.closest('div')!.parentElement!
    await within(projectCard).findByText('1 个条目')
    const viewAll = within(projectCard).getByRole('link', { name: '查看全部' })
    expect(viewAll).toHaveAttribute('href', '/user-groups/grp_lab/projects')

    const resourceHeading = screen.getByRole('heading', { name: '共享资源', level: 3 })
    const resourceCard = resourceHeading.closest('div')!.parentElement!
    await within(resourceCard).findByText('这个 User Group 还没有共享资源。')
  })

  it('REQ-21-14 活动卡按 page_size 10 拉取并渲染活动句子', async () => {
    renderOverview()

    const activityHeading = await screen.findByRole('heading', { name: '近期活动', level: 3 })
    expect(api.listUserGroupActivities).toHaveBeenCalledWith('grp_lab', { page_size: 10 })
    await within(activityHeading.parentElement!.parentElement!).findByText(/加入了 User Group/)
    const activityCard = activityHeading.closest('div')!.parentElement!
    const projectLink = within(activityCard).getByRole('link', { name: /Group Project/ })
    expect(projectLink).toHaveAttribute('href', '/projects/prj_group')
  })

  it('REQ-21-15 单卡失败不影响其他卡渲染', async () => {
    vi.spyOn(api, 'listSharedResources').mockRejectedValue(new Error('boom'))

    renderOverview()

    const basicSection = await screen.findByRole('region', { name: '基本信息' })
    await screen.findByText('Alice', { selector: 'dd' })
    expect(basicSection).toBeInTheDocument()
    const resourceHeading = await screen.findByRole('heading', { name: '共享资源', level: 3 })
    const resourceCard = resourceHeading.closest('div')!.parentElement!
    expect(within(resourceCard).getByRole('button', { name: '重试' })).toBeInTheDocument()
    const activityHeading = screen.getByRole('heading', { name: '近期活动', level: 3 })
    const activityCard = activityHeading.closest('div')!.parentElement!
    await within(activityCard).findByText(/加入了 User Group/)
  })
})
