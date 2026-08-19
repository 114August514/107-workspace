// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SharedResourcePage } from '../../src/pages/SharedResourcePage'
import type {
  LegacyWorkspaceContext,
  SharedResourceDetail,
  SharedResourceVersion,
  SharedResourceVersionDetail,
} from '../../src/api/types'

/**
 * SharedResourcePage 用户可观察行为。
 *
 * 守的是 Issue #5 / #25 的要求：
 * - Platform 资源是只读的，不显示「修改共享资源」和「发布版本」；
 * - 操作入口由 capability 决定，后端逐请求校验，前端只收敛入口；
 * - 空态只对有发布权限的用户展示 CTA，且不绑定控件物理位置。
 *
 * 断言用角色和可见文案，不绑定 Primer 私有 DOM/class（见 frontend/README.md）。
 */

const mockGetSharedResource = vi.hoisted(() => vi.fn())
const mockGetLegacyWorkspaceContext = vi.hoisted(() => vi.fn())
const mockGetSharedResourceVersion = vi.hoisted(() => vi.fn())

vi.mock('../../src/api/client', () => ({
  api: {
    getSharedResource: mockGetSharedResource,
    getLegacyWorkspaceContext: mockGetLegacyWorkspaceContext,
    getSharedResourceVersion: mockGetSharedResourceVersion,
  },
}))

// jsdom 没有 ResizeObserver，Primer 组件内部会用到。
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function makeWorkspace(caps: string[]): LegacyWorkspaceContext {
  return {
    id: 'ws_test',
    name: 'Test 空间',
    kind: 'collaborative',
    owner_id: 'owner',
    default_environment_version_id: null,
    capabilities: caps as LegacyWorkspaceContext['capabilities'],
    role: 'admin',
  }
}

function makeResource(overrides: Partial<SharedResourceDetail> = {}): SharedResourceDetail {
  return {
    id: 'res_test',
    name: '预训练权重',
    description: 'imagenet-subset',
    is_platform_owned: false,
    owner_workspace_id: 'ws_test',
    created_at: '2026-08-14T10:00:00Z',
    versions: [],
    ...overrides,
  }
}

function makeVersionSummary(id: string, label: string, sequence: number): SharedResourceVersion {
  return {
    id,
    shared_resource_id: 'res_test',
    label,
    description: '',
    sequence,
    file_count: 1,
    total_size: 100,
    created_at: '2026-08-14T10:00:00Z',
    created_by: 'student',
  }
}

function makeVersionDetail(
  id: string,
  label: string,
  sequence: number,
): SharedResourceVersionDetail {
  return {
    ...makeVersionSummary(id, label, sequence),
    files: [{ path: 'train.py', content_hash: 'abc', size: 100 }],
  }
}

function renderPage(resourceId = 'res_test') {
  return render(
    <MemoryRouter initialEntries={[`/shared-resources/${resourceId}`]}>
      <Routes>
        <Route path="/shared-resources/:resourceId" element={<SharedResourcePage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SharedResourcePage 权限与空态', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', ResizeObserverStub)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('有发布权限时显示「发布版本」，空态给出 CTA 且不绑定物理位置', async () => {
    mockGetSharedResource.mockResolvedValue(makeResource({ versions: [] }))
    mockGetLegacyWorkspaceContext.mockResolvedValue(
      makeWorkspace(['workspace.view', 'shared_resource.view', 'shared_resource.version.create']),
    )

    renderPage()

    // 「发布版本」同时出现在页头操作和空态 CTA 里——两处都是合法入口。
    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: '发布版本' }).length).toBeGreaterThan(0)
    })
    // 空态说明告诉下一步，而不是「点击右上角」。
    expect(screen.getByText('这个共享资源还没有已发布版本。')).toBeInTheDocument()
    expect(screen.getByText('发布首个版本后，Project 才能引用这个共享资源。')).toBeInTheDocument()
    // 空态 CTA 也是发布版本，所以至少有两个发布入口
    expect(screen.getAllByRole('button', { name: '发布版本' }).length).toBeGreaterThan(1)
    expect(screen.queryByText(/右上角/)).not.toBeInTheDocument()
  })

  it('无发布权限时不显示「发布版本」，空态也不给 CTA', async () => {
    mockGetSharedResource.mockResolvedValue(makeResource({ versions: [] }))
    mockGetLegacyWorkspaceContext.mockResolvedValue(
      makeWorkspace(['workspace.view', 'shared_resource.view']),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('预训练权重')).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: '发布版本' })).not.toBeInTheDocument()
    expect(
      screen.queryByText('发布首个版本后，Project 才能引用这个共享资源。'),
    ).not.toBeInTheDocument()
    // 有 manage 权限时才显示修改入口
    expect(screen.queryByRole('button', { name: '修改共享资源' })).not.toBeInTheDocument()
  })

  it('有 manage 权限时显示「修改共享资源」', async () => {
    mockGetSharedResource.mockResolvedValue(makeResource({ versions: [] }))
    mockGetLegacyWorkspaceContext.mockResolvedValue(
      makeWorkspace([
        'workspace.view',
        'shared_resource.view',
        'shared_resource.manage',
        'shared_resource.version.create',
      ]),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '修改共享资源' })).toBeInTheDocument()
    })
  })

  it('Platform 资源只读：不显示修改和发布，但能看见资源', async () => {
    mockGetSharedResource.mockResolvedValue(
      makeResource({ is_platform_owned: true, owner_workspace_id: null }),
    )
    // Platform 资源不加载 workspace（owner_workspace_id 为 null）
    mockGetLegacyWorkspaceContext.mockResolvedValue(undefined)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('预训练权重')).toBeInTheDocument()
    })
    expect(screen.getByText('平台资源')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '修改共享资源' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '发布版本' })).not.toBeInTheDocument()
  })

  it('已发布版本列在左侧列表，默认选中最新版本的详情', async () => {
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        versions: [makeVersionSummary('ver_2', 'v2', 2), makeVersionSummary('ver_1', 'v1', 1)],
      }),
    )
    mockGetLegacyWorkspaceContext.mockResolvedValue(
      makeWorkspace(['workspace.view', 'shared_resource.view']),
    )
    mockGetSharedResourceVersion.mockResolvedValue(makeVersionDetail('ver_2', 'v2', 2))

    renderPage()

    expect(await screen.findByRole('button', { name: /v2/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /v1/ })).toBeInTheDocument()
    expect(screen.getByText('最新')).toBeInTheDocument()
    // 右侧详情默认加载最新版本，不去请求旧版本
    await waitFor(() => {
      expect(mockGetSharedResourceVersion).toHaveBeenCalledWith('ver_2')
    })
    expect(mockGetSharedResourceVersion).not.toHaveBeenCalledWith('ver_1')
  })

  it('点击左侧版本切换右侧详情', async () => {
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        versions: [makeVersionSummary('ver_2', 'v2', 2), makeVersionSummary('ver_1', 'v1', 1)],
      }),
    )
    mockGetLegacyWorkspaceContext.mockResolvedValue(
      makeWorkspace(['workspace.view', 'shared_resource.view']),
    )
    mockGetSharedResourceVersion.mockResolvedValue(makeVersionDetail('ver_2', 'v2', 2))

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: /v1/ }))
    await waitFor(() => {
      expect(mockGetSharedResourceVersion).toHaveBeenCalledWith('ver_1')
    })
  })

  it('面包屑引导回到所属工作区的「共享资源」深链路', async () => {
    mockGetSharedResource.mockResolvedValue(makeResource())
    mockGetLegacyWorkspaceContext.mockResolvedValue(
      makeWorkspace(['workspace.view', 'shared_resource.view']),
    )

    renderPage()

    // 面包屑：首页 → Test 空间 → 共享资源（当前页不在面包屑里）
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Test 空间' })).toHaveAttribute(
        'href',
        '/workspaces/ws_test',
      )
    })
    expect(screen.getByRole('link', { name: '共享资源' })).toHaveAttribute(
      'href',
      '/workspaces/ws_test/shared-resources',
    )
    // 当前页「预训练权重」由 TitleArea 呈现为 h1 标题，不是链接
    const current = screen.getByRole('heading', { name: '预训练权重', level: 1 })
    expect(current).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '预训练权重' })).not.toBeInTheDocument()
    // 归属标签跟在标题旁
    expect(screen.getByText('空间资源')).toBeInTheDocument()
  })
})
