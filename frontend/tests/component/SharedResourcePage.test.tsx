// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SharedResourcePage } from '../../src/pages/SharedResourcePage'
import type {
  SharedResourceDetail,
  SharedResourceVersion,
  SharedResourceVersionDetail,
} from '../../src/api/types'

/**
 * SharedResourcePage 用户可观察行为。
 *
 * 守的是 Issue #5 / #39 的要求：
 * - 资源展示 canonical User / UserGroup owner，不再推断 Platform owner；
 * - 操作入口由 owner context 的 capability 决定，后端逐请求校验，前端只收敛入口；
 * - 空态只对有发布权限的用户展示 CTA，且不绑定控件物理位置。
 *
 * 断言用角色和可见文案，不绑定 Primer 私有 DOM/class（见 frontend/README.md）。
 */

const mockGetSharedResource = vi.hoisted(() => vi.fn())
const mockGetSharedResourceVersion = vi.hoisted(() => vi.fn())

vi.mock('../../src/api/client', () => ({
  api: {
    getSharedResource: mockGetSharedResource,
    getSharedResourceVersion: mockGetSharedResourceVersion,
  },
}))

// jsdom 没有 ResizeObserver，Primer 组件内部会用到。
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

function makeResource(overrides: Partial<SharedResourceDetail> = {}): SharedResourceDetail {
  return {
    id: 'res_test',
    name: '预训练权重',
    description: 'imagenet-subset',
    owner: { kind: 'user_group', id: 'ws_test', display_name: 'Test 空间' },
    created_at: '2026-08-14T10:00:00Z',
    use_qualifications: [{ scope: 'owner', eligible_project_owner: null, grants: [] }],
    versions: [],
    capabilities: ['shared_resource.view'],
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
  path = 'train.py',
): SharedResourceVersionDetail {
  return {
    ...makeVersionSummary(id, label, sequence),
    files: [{ path, content_hash: 'abc', size: 100 }],
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
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        versions: [],
        capabilities: ['shared_resource.view', 'shared_resource.version.create'],
      }),
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
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        versions: [],
        capabilities: [
          'shared_resource.view',
          'shared_resource.manage',
          'shared_resource.version.create',
        ],
      }),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '修改共享资源' })).toBeInTheDocument()
    })
  })

  it('无法解析 owner context 时保持只读，但仍展示 canonical owner', async () => {
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        owner: { kind: 'user', id: 'usr_alice', display_name: 'Alice' },
      }),
    )

    renderPage()

    await waitFor(() => {
      expect(screen.getByText('预训练权重')).toBeInTheDocument()
    })
    expect(screen.getByText('归属：Alice')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '修改共享资源' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '发布版本' })).not.toBeInTheDocument()
  })

  it('已发布版本列在左侧列表，默认选中最新版本的详情', async () => {
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        versions: [makeVersionSummary('ver_2', 'v2', 2), makeVersionSummary('ver_1', 'v1', 1)],
      }),
    )
    mockGetSharedResourceVersion.mockResolvedValue(makeVersionDetail('ver_2', 'v2', 2))

    renderPage()

    expect(await screen.findByRole('button', { name: /v2/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /v1/ })).toBeInTheDocument()
    expect(screen.getByText('最新')).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'train.py' })).toBeInTheDocument()
  })

  it('点击左侧版本切换右侧详情', async () => {
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        versions: [makeVersionSummary('ver_2', 'v2', 2), makeVersionSummary('ver_1', 'v1', 1)],
      }),
    )
    mockGetSharedResourceVersion.mockImplementation((id: string) =>
      Promise.resolve(
        id === 'ver_1'
          ? makeVersionDetail('ver_1', 'v1', 1, 'old.py')
          : makeVersionDetail('ver_2', 'v2', 2),
      ),
    )

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: /v1/ }))
    expect(await screen.findByRole('button', { name: 'old.py' })).toBeInTheDocument()
  })

  it('面包屑使用当前 User Group route', async () => {
    mockGetSharedResource.mockResolvedValue(makeResource())

    renderPage()

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Test 空间' })).toHaveAttribute(
        'href',
        '/user-groups/ws_test',
      )
    })
    expect(screen.getByText('共享资源')).toBeInTheDocument()
  })
})

describe('SharedResourcePage 使用资格展示（Issue #55）', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', ResizeObserverStub)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('Owner 资格明确限定为资源 Owner 相同的 Project', async () => {
    mockGetSharedResource.mockResolvedValue(makeResource())

    renderPage()

    expect(await screen.findByText('资源 Owner 范围')).toBeInTheDocument()
    expect(
      screen.getByText('你具备在 Owner 与此资源相同的 Project 中引用它的资格。'),
    ).toBeInTheDocument()
  })

  it('直接 User Grant 说明可跟随 actor，而不冒充全局 Preflight 结果', async () => {
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        use_qualifications: [
          {
            scope: 'user_grant',
            eligible_project_owner: null,
            grants: [
              {
                id: 'grant_1',
                grantee: { kind: 'user', id: 'usr_bob', display_name: 'Bob' },
                target_all: false,
                created_at: '2026-08-20T10:00:00Z',
              },
            ],
          },
        ],
      }),
    )

    renderPage()

    expect(await screen.findByText('个人 USE 授权')).toBeInTheDocument()
    expect(
      screen.getByText('Owner 已直接授权给你；可在你有权提交的任何 Project 中引用它。'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('这里仅说明当前账号的使用资格，不代表具体 Run 已通过 Preflight。'),
    ).toBeInTheDocument()
    expect(screen.getByText(/USE 授权：授予 Bob（仅限此资源）/)).toBeInTheDocument()
  })

  it('UserGroup Grant 展示 exact eligible Project.owner context', async () => {
    mockGetSharedResource.mockResolvedValue(
      makeResource({
        use_qualifications: [
          {
            scope: 'user_group_grant',
            eligible_project_owner: { kind: 'user_group', id: 'grp_ml' },
            grants: [
              {
                id: 'grant_2',
                grantee: { kind: 'user_group', id: 'grp_ml', display_name: 'ML 组' },
                target_all: true,
                created_at: '2026-08-20T10:00:00Z',
              },
            ],
          },
        ],
      }),
    )

    renderPage()

    expect(await screen.findByText('ML 组 USE 授权')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Owner 已授权给「ML 组」；需保持该组有效成员身份，并在该组作为 Owner 的 Project 中引用它。',
      ),
    ).toBeInTheDocument()
    expect(screen.getByText(/USE 授权：授予 ML 组（覆盖 Owner 全部资产）/)).toBeInTheDocument()
  })
})
