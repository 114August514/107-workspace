// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SharedResourcePage } from '../../src/pages/SharedResourcePage'
import type { SharedResourceDetail, Workspace } from '../../src/api/types'

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
const mockGetWorkspace = vi.hoisted(() => vi.fn())

vi.mock('../../src/api/client', () => ({
  api: {
    getSharedResource: mockGetSharedResource,
    getWorkspace: mockGetWorkspace,
  },
}))

// jsdom 没有 ResizeObserver，Primer 组件内部会用到。
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function makeWorkspace(caps: string[]): Workspace {
  return {
    id: 'ws_test',
    name: 'Test 空间',
    description: '',
    kind: 'collaborative',
    owner_id: 'owner',
    created_at: null,
    default_environment_version_id: null,
    capabilities: caps as Workspace['capabilities'],
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
    mockGetWorkspace.mockResolvedValue(
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
    mockGetWorkspace.mockResolvedValue(makeWorkspace(['workspace.view', 'shared_resource.view']))

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
    mockGetWorkspace.mockResolvedValue(
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
    mockGetWorkspace.mockResolvedValue(undefined)

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('预训练权重')).toBeInTheDocument()
    })
    expect(screen.getByText('平台资源')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '修改共享资源' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '发布版本' })).not.toBeInTheDocument()
  })

  it('已发布版本在表格中列出，并链接到版本详情', async () => {
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        versions: [
          {
            id: 'ver_1',
            shared_resource_id: 'res_test',
            label: 'v1',
            description: '首个版本',
            sequence: 1,
            file_count: 3,
            total_size: 1024,
            created_at: '2026-08-14T10:00:00Z',
            created_by: 'student',
          },
        ],
      }),
    )
    mockGetWorkspace.mockResolvedValue(makeWorkspace(['workspace.view', 'shared_resource.view']))

    renderPage()

    const link = await screen.findByRole('link', { name: 'v1' })
    expect(link).toHaveAttribute('href', '/shared-resource-versions/ver_1')
  })
})
