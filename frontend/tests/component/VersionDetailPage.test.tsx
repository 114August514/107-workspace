// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { VersionDetailPage } from '../../src/pages/VersionDetailPage'
import type { Project, ProjectVersionDetail, LegacyWorkspaceContext } from '../../src/api/types'

/**
 * VersionDetailPage 权限可见性。
 *
 * 守的是 Issue #12 §5 的要求：Viewer / 无对应权限用户不应该看到
 * 「运行此版本」和「恢复到此版本」入口。
 * 「派生」按钮始终可见——派生只需要能看见版本，写权限是目标空间的事。
 */

const mockGetVersion = vi.hoisted(() => vi.fn())
const mockGetProject = vi.hoisted(() => vi.fn())
const mockGetLegacyWorkspaceContext = vi.hoisted(() => vi.fn())
const mockListUserGroups = vi.hoisted(() => vi.fn())
const mockListVersions = vi.hoisted(() => vi.fn())
const mockDiffVersions = vi.hoisted(() => vi.fn())

vi.mock('../../src/api/client', () => ({
  api: {
    getVersion: mockGetVersion,
    getProject: mockGetProject,
    getLegacyWorkspaceContext: mockGetLegacyWorkspaceContext,
    listUserGroups: mockListUserGroups,
    listVersions: mockListVersions,
    diffVersions: mockDiffVersions,
  },
}))

const version: ProjectVersionDetail = {
  id: 'pv_test1',
  project_id: 'prj_test',
  label: 'v1',
  sequence: 1,
  message: 'initial',
  created_at: '2026-08-12T00:00:00Z',
  created_by: 'student',
  file_count: 1,
  total_size: 100,
  files: [{ path: 'train.py', content_hash: 'abc', size: 100 }],
}

const project: Project = {
  id: 'prj_test',
  workspace_id: 'ws_test',
  owner: { kind: 'user_group', id: 'ws_test', display_name: 'Test Workspace' },
  name: 'Test Project',
  description: '',
  status: 'active',
  visibility: 'owner_scope',
  created_at: null,
  updated_at: null,
  created_by: 'student',
  environment_version_id: null,
  default_run_configuration_id: null,
}

function makeWorkspace(caps: string[]): LegacyWorkspaceContext {
  return {
    id: 'ws_test',
    name: 'Test Workspace',
    kind: 'collaborative',
    owner_id: 'owner',
    default_environment_version_id: null,
    capabilities: caps as LegacyWorkspaceContext['capabilities'],
    role: 'viewer',
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/versions/pv_test1']}>
      <VersionDetailPage />
    </MemoryRouter>,
  )
}

describe('VersionDetailPage 权限可见性', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  // ForkModal 和 VersionDiffPanel 始终挂载（即使 modal/drawer 关闭），
  // 它们的 useAsync 会在 mount 时调用 API，需要给默认 mock 返回值。
  beforeEach(() => {
    mockListUserGroups.mockResolvedValue([])
    mockListVersions.mockResolvedValue({
      items: [],
      page: 1,
      page_size: 20,
      total: 0,
      has_more: false,
    })
    mockDiffVersions.mockResolvedValue([])
  })

  it('Viewer 看不到「运行此版本」和「恢复到此版本」，但能看到「派生」', async () => {
    mockGetVersion.mockResolvedValue(version)
    mockGetProject.mockResolvedValue(project)
    // Viewer 只有 view 权限，没有 run.submit 和 project.content.write
    mockGetLegacyWorkspaceContext.mockResolvedValue(
      makeWorkspace(['user_group.view', 'project.view', 'run.view']),
    )

    renderPage()

    // antd Button 对双字符中文标签会插入间距，可访问名变成「派 生」
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /派\s*生/ })).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: /运行此版本/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /恢复到此版本/ })).not.toBeInTheDocument()
  })

  it('有 run.submit 权限的用户能看到「运行此版本」', async () => {
    mockGetVersion.mockResolvedValue(version)
    mockGetProject.mockResolvedValue(project)
    mockGetLegacyWorkspaceContext.mockResolvedValue(
      makeWorkspace(['user_group.view', 'project.view', 'run.view', 'run.submit']),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '运行此版本' })).toBeInTheDocument()
    })
  })

  it('有 project.content.write 权限的用户能看到「恢复到此版本」', async () => {
    mockGetVersion.mockResolvedValue(version)
    mockGetProject.mockResolvedValue(project)
    mockGetLegacyWorkspaceContext.mockResolvedValue(
      makeWorkspace(['user_group.view', 'project.view', 'run.view', 'project.content.write']),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '恢复到此版本' })).toBeInTheDocument()
    })
  })
})
