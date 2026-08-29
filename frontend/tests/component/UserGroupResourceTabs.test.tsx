// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from '../../src/api/client'
import type { Environment, Project, SharedResource, UserGroup } from '../../src/api/types'
import { EnvironmentsSection } from '../../src/components/usergroup/EnvironmentsSection'
import { ProjectsSection } from '../../src/components/usergroup/ProjectsSection'
import { SharedResourcesSection } from '../../src/components/usergroup/SharedResourcesSection'
import { UserGroupPage } from '../../src/pages/UserGroupPage'

const group: UserGroup = {
  id: 'grp_lab',
  name: 'Research Lab',
  description: '',
  created_by_id: 'usr_alice',
  created_at: '2026-08-17T00:00:00Z',
  role: 'owner',
  capabilities: ['user_group.view', 'user_group.update', 'member.view'],
}

function ownerRef(id: string, name: string) {
  return { kind: 'user_group' as const, id, display_name: name }
}

const groupProject: Project = {
  id: 'prj_group',
  name: 'Group Project',
  description: 'Owned by the group',
  status: 'active',
  visibility: 'owner_scope',
  environment_version_id: null,
  default_run_configuration_id: null,
  created_by: 'usr_alice',
  created_at: '2026-08-17T00:00:00Z',
  updated_at: '2026-08-20T00:00:00Z',
  owner: ownerRef('grp_lab', 'Research Lab'),
}

const otherProject: Project = {
  ...groupProject,
  id: 'prj_other',
  name: 'Other Group Project',
  owner: ownerRef('grp_other', 'Other Lab'),
}

const userProject: Project = {
  ...groupProject,
  id: 'prj_user',
  name: 'Personal Project',
  owner: { kind: 'user', id: 'usr_alice', display_name: 'Alice' },
}

const archivedProject: Project = {
  ...groupProject,
  id: 'prj_archived',
  name: 'Archived Project',
  status: 'archived',
}

const groupResource: SharedResource = {
  id: 'sr_group',
  name: 'Group Dataset',
  description: 'Dataset owned by the group',
  created_at: '2026-08-17T00:00:00Z',
  owner: ownerRef('grp_lab', 'Research Lab'),
  use_qualifications: [],
}

const groupEnvironment: Environment = {
  id: 'env_group',
  name: 'Group Env',
  description: 'Environment owned by the group',
  owner: ownerRef('grp_lab', 'Research Lab'),
  versions: [
    {
      id: 'ev1',
      version: 'v1',
      available: true,
      description: '',
      environment_id: 'env_group',
      image: 'python:3.12',
      setup_command: '',
    },
    {
      id: 'ev2',
      version: 'v2',
      available: false,
      description: '',
      environment_id: 'env_group',
      image: 'python:3.12',
      setup_command: '',
    },
  ],
}

function renderSection(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/user-groups/:userGroupId" element={<UserGroupPage />}>
          <Route path="projects" element={<ProjectsSection />} />
          <Route path="shared-resources" element={<SharedResourcesSection />} />
          <Route path="environments" element={<EnvironmentsSection />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('User Group 资源分区', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getUserGroup').mockResolvedValue(group)
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-21-06 Project 分区只显示组拥有的 Project 并链接详情页', async () => {
    const listProjects = vi
      .spyOn(api, 'listProjects')
      .mockResolvedValue({
        items: [groupProject, otherProject, userProject],
        page: 1,
        page_size: 200,
        total: 3,
        has_more: false,
      })

    renderSection('/user-groups/grp_lab/projects')

    const link = await screen.findByRole('link', { name: /Group Project/ })
    expect(link).toHaveAttribute('href', '/projects/prj_group')
    expect(listProjects).toHaveBeenCalledWith({ page: 1, page_size: 200 })
    expect(screen.queryByText('Other Group Project')).not.toBeInTheDocument()
    expect(screen.queryByText('Personal Project')).not.toBeInTheDocument()
  })

  it('REQ-21-07 Project 分区跟随分页并标记归档状态', async () => {
    vi.spyOn(api, 'listProjects')
      .mockResolvedValueOnce({
        items: [groupProject],
        page: 1,
        page_size: 200,
        total: 2,
        has_more: true,
      })
      .mockResolvedValueOnce({
        items: [archivedProject],
        page: 2,
        page_size: 200,
        total: 2,
        has_more: false,
      })

    renderSection('/user-groups/grp_lab/projects')

    const archivedLink = await screen.findByRole('link', { name: /Archived Project/ })
    expect(within(archivedLink).getByText('已归档')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Group Project/ })).toBeInTheDocument()
  })

  it('REQ-21-08 Project 分区错误时展示稳定错误并提供重试', async () => {
    const listProjects = vi
      .spyOn(api, 'listProjects')
      .mockRejectedValueOnce(new ApiError(500, 'internal_error', 'Project 列表加载失败', []))
      .mockResolvedValueOnce({
        items: [groupProject],
        page: 1,
        page_size: 200,
        total: 1,
        has_more: false,
      })

    renderSection('/user-groups/grp_lab/projects')

    const retry = await screen.findByRole('button', { name: '重试' })
    expect(screen.getByText('Project 列表加载失败')).toBeInTheDocument()
    expect(listProjects).toHaveBeenCalledTimes(1)

    retry.click()
    await screen.findByRole('link', { name: /Group Project/ })
    expect(listProjects).toHaveBeenCalledTimes(2)
  })

  it('REQ-21-09 共享资源分区过滤并链接详情页', async () => {
    const otherResource = {
      ...groupResource,
      id: 'sr_other',
      name: 'Other Resource',
      owner: ownerRef('grp_other', 'Other Lab'),
    }
    vi.spyOn(api, 'listSharedResources').mockResolvedValue([groupResource, otherResource])

    renderSection('/user-groups/grp_lab/shared-resources')

    const link = await screen.findByRole('link', { name: /Group Dataset/ })
    expect(link).toHaveAttribute('href', '/shared-resources/sr_group')
    expect(screen.queryByText('Other Resource')).not.toBeInTheDocument()
  })

  it('REQ-21-10 运行环境分区显示版本可用计数', async () => {
    const otherEnv = {
      ...groupEnvironment,
      id: 'env_other',
      name: 'Other Env',
      owner: ownerRef('grp_other', 'Other Lab'),
    }
    vi.spyOn(api, 'environments').mockResolvedValue([groupEnvironment, otherEnv])

    renderSection('/user-groups/grp_lab/environments')

    const link = await screen.findByRole('link', { name: /Group Env/ })
    expect(link).toHaveAttribute('href', '/environments/env_group')
    expect(within(link).getByText('1/2 个版本可用')).toBeInTheDocument()
    expect(screen.queryByText('Other Env')).not.toBeInTheDocument()
  })

  it('REQ-21-11 空状态文案区分三种资源', async () => {
    vi.spyOn(api, 'listProjects').mockResolvedValue({
      items: [],
      page: 1,
      page_size: 200,
      total: 0,
      has_more: false,
    })
    renderSection('/user-groups/grp_lab/projects')
    expect(await screen.findByText('这个 User Group 还没有 Project。')).toBeInTheDocument()
    cleanup()

    vi.spyOn(api, 'listSharedResources').mockResolvedValue([])
    renderSection('/user-groups/grp_lab/shared-resources')
    expect(await screen.findByText('这个 User Group 还没有共享资源。')).toBeInTheDocument()
    cleanup()

    vi.spyOn(api, 'environments').mockResolvedValue([])
    renderSection('/user-groups/grp_lab/environments')
    expect(await screen.findByText('这个 User Group 还没有运行环境。')).toBeInTheDocument()
  })
})
