// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError, NetworkError, reportUnauthorized } from '../../src/api/client'
import type { Home } from '../../src/api/types'
import { App } from '../../src/App'
import { resetAuthFetchForTests } from '../../src/auth/AuthProvider'

const homeData: Home = {
  user: { id: 'u-1', username: 'student', display_name: '同学', email: 'student@mail.ustc.edu.cn' },
  user_groups: [
    {
      id: 'grp-1',
      name: '计算物理课题组',
      description: '',
      created_by_id: 'u-1',
      created_at: '2026-08-15T10:00:00Z',
      role: 'owner',
      capabilities: [],
    },
  ],
  personal_execution_context: {
    owner: { kind: 'user', id: 'u-1', display_name: '同学' },
    entitlements: [],
  },
  recent_projects: [],
  recent_runs: [],
}

function renderApp(entry = '/') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <App />
    </MemoryRouter>,
  )
}

function loginButtons() {
  return screen.getAllByRole('button', { name: '统一身份认证登录' })
}

function mockSignedInApis(home: Home = homeData) {
  vi.spyOn(api, 'home').mockResolvedValue(home)
  vi.spyOn(api, 'listInvitations').mockResolvedValue([])
  vi.spyOn(api, 'computePlans').mockResolvedValue([])
  vi.spyOn(api, 'unreadCount').mockResolvedValue(0)
}

afterEach(() => {
  cleanup()
  resetAuthFetchForTests()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('启动时的认证状态', () => {
  it('确认登录前只显示加载状态，不挂载业务页面或通知', () => {
    vi.spyOn(api, 'home').mockImplementation(() => new Promise<Home>(() => {}))
    const invitations = vi.spyOn(api, 'listInvitations')
    const unread = vi.spyOn(api, 'unreadCount')

    renderApp()

    expect(screen.getByRole('status')).toHaveTextContent('正在确认登录状态…')
    expect(screen.queryByText('同学，欢迎回来')).toBeNull()
    expect(screen.queryByRole('button', { name: '通知' })).toBeNull()
    expect(screen.queryByRole('button', { name: '创建 User Group' })).toBeNull()
    expect(invitations).not.toHaveBeenCalled()
    expect(unread).not.toHaveBeenCalled()
  })

  it('GET /me 成功后进入现有个人首页', async () => {
    mockSignedInApis()
    renderApp()

    expect(await screen.findByRole('heading', { name: '同学，欢迎回来' })).toBeVisible()
    expect(screen.getByRole('button', { name: '当前用户 同学' })).toBeVisible()
    expect(screen.getByRole('button', { name: '创建 User Group' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '统一身份认证登录' })).toBeNull()
  })

  it('只有 401 转为未登录公开首页', async () => {
    vi.spyOn(api, 'home').mockRejectedValue(
      new ApiError(401, 'authentication_required', '未提供有效的 USTC CAS 身份', []),
    )
    const invitations = vi.spyOn(api, 'listInvitations')
    const unread = vi.spyOn(api, 'unreadCount')

    renderApp()

    expect(await screen.findByRole('heading', { name: '107 Workspace' })).toBeVisible()
    expect(loginButtons().length).toBeGreaterThan(0)
    expect(screen.queryByText('同学，欢迎回来')).toBeNull()
    expect(screen.queryByRole('button', { name: '创建 User Group' })).toBeNull()
    expect(screen.queryByRole('button', { name: '通知' })).toBeNull()
    expect(invitations).not.toHaveBeenCalled()
    expect(unread).not.toHaveBeenCalled()
  })

  it('网络错误显示可重试错误，不进入未登录首页', async () => {
    const home = vi.spyOn(api, 'home').mockRejectedValue(new NetworkError(new TypeError('offline')))
    renderApp()

    expect(await screen.findByText('无法加载内容。')).toBeVisible()
    expect(screen.queryByText('同学，欢迎回来')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    await waitFor(() => expect(home).toHaveBeenCalledTimes(2))
  })

  it('5xx 显示可重试错误', async () => {
    vi.spyOn(api, 'home').mockRejectedValue(
      new ApiError(500, 'internal_error', '服务暂时不可用。', []),
    )
    renderApp()

    expect(await screen.findByText('服务暂时不可用。')).toBeVisible()
    expect(screen.getByRole('button', { name: '重试' })).toBeVisible()
    expect(screen.queryByText('同学，欢迎回来')).toBeNull()
  })

  it('403 保持为业务权限错误，不转为未登录', async () => {
    vi.spyOn(api, 'home').mockRejectedValue(
      new ApiError(403, 'permission_denied', '需要访问权限。', []),
    )
    renderApp()

    expect(await screen.findByText('需要访问权限。')).toBeVisible()
    expect(screen.queryByText('同学，欢迎回来')).toBeNull()
  })
})

describe('登录入口与内部路由', () => {
  it('登录按钮执行整页跳转到 /login', async () => {
    vi.spyOn(api, 'home').mockRejectedValue(
      new ApiError(401, 'authentication_required', '需要登录。', []),
    )
    const assign = vi.fn()
    vi.stubGlobal('location', { assign, href: 'http://localhost/', origin: 'http://localhost' })

    renderApp()
    await screen.findByRole('heading', { name: '107 Workspace' })
    fireEvent.click(loginButtons()[0]!)
    expect(assign).toHaveBeenCalledWith('/login')
  })

  it('未登录访问内部路由时回到公开首页', async () => {
    vi.spyOn(api, 'home').mockRejectedValue(
      new ApiError(401, 'authentication_required', '需要登录。', []),
    )
    renderApp('/projects/p-1')

    expect(await screen.findByRole('heading', { name: '107 Workspace' })).toBeVisible()
    expect(screen.queryByText('页面内容')).toBeNull()
    expect(screen.queryByRole('navigation', { name: 'Project navigation' })).toBeNull()
  })
})

describe('用户菜单与个人资料', () => {
  it('资料弹窗展示接口已有字段，缺失邮箱显示未提供', async () => {
    mockSignedInApis({
      ...homeData,
      user: { ...homeData.user, email: null },
    })
    renderApp()

    fireEvent.click(await screen.findByRole('button', { name: '当前用户 同学' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '个人资料' }))

    const dialog = await screen.findByRole('dialog', { name: '个人资料' })
    expect(within(dialog).getByLabelText('显示名')).toHaveValue('同学')
    expect(within(dialog).getByLabelText('用户名')).toHaveValue('student')
    expect(within(dialog).getByLabelText('邮箱')).toHaveValue('未提供')
    expect(within(dialog).queryByRole('textbox', { name: /编辑/ })).toBeNull()
  })

  it('设置进入现有个人执行上下文', async () => {
    mockSignedInApis()
    vi.spyOn(api, 'listEntitlements').mockResolvedValue([])
    vi.spyOn(api, 'listUserVariables').mockResolvedValue([])
    vi.spyOn(api, 'listUserSecrets').mockResolvedValue([])
    renderApp()

    fireEvent.click(await screen.findByRole('button', { name: '当前用户 同学' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '设置' }))
    expect(await screen.findByRole('heading', { name: '个人执行上下文' })).toBeVisible()
  })

  it('退出登录以同源 POST 表单提交 /logout', async () => {
    mockSignedInApis()
    const submit = vi.spyOn(HTMLFormElement.prototype, 'submit').mockImplementation(() => {})
    renderApp()

    fireEvent.click(await screen.findByRole('button', { name: '当前用户 同学' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '退出登录' }))

    expect(submit).toHaveBeenCalled()
    const form = document.querySelector('form[action="/logout"]')
    expect(form).not.toBeNull()
    expect(form).toHaveAttribute('method', 'post')
  })
})

describe('业务请求 401 与迟到响应', () => {
  it('业务 API 返回 401 时清除用户并回到公开首页，停止通知轮询', async () => {
    mockSignedInApis()
    vi.spyOn(api, 'listInvitations').mockRejectedValue(
      new ApiError(401, 'authentication_required', '需要登录。', []),
    )
    renderApp()

    expect(await screen.findByRole('heading', { name: '107 Workspace' })).toBeVisible()
    expect(screen.queryByText('同学，欢迎回来')).toBeNull()
    expect(screen.queryByRole('button', { name: '通知' })).toBeNull()
    expect(loginButtons().length).toBeGreaterThan(0)
  })

  it('迟到的 GET /me 不会在退出后恢复旧用户内容', async () => {
    let resolveLate!: (home: Home) => void
    vi.spyOn(api, 'home')
      .mockResolvedValueOnce(homeData)
      .mockImplementationOnce(
        () =>
          new Promise<Home>((resolve) => {
            resolveLate = resolve
          }),
      )
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])
    vi.spyOn(api, 'unreadCount').mockResolvedValue(0)

    renderApp()
    expect(await screen.findByRole('heading', { name: '同学，欢迎回来' })).toBeVisible()

    const persisted = new Event('pageshow')
    Object.defineProperty(persisted, 'persisted', { value: true })
    await act(async () => {
      window.dispatchEvent(persisted)
    })

    await act(async () => {
      reportUnauthorized()
    })

    await screen.findByRole('heading', { name: '107 Workspace' })
    expect(loginButtons().length).toBeGreaterThan(0)
    await act(async () => {
      resolveLate(homeData)
    })
    expect(loginButtons().length).toBeGreaterThan(0)
    expect(screen.queryByText('同学，欢迎回来')).toBeNull()
    expect(screen.queryByRole('link', { name: '计算物理课题组' })).toBeNull()
  })

  it('从历史记录恢复时重新确认用户状态', async () => {
    const home = vi.spyOn(api, 'home').mockResolvedValue(homeData)
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])
    vi.spyOn(api, 'unreadCount').mockResolvedValue(0)
    renderApp()
    expect(await screen.findByRole('heading', { name: '同学，欢迎回来' })).toBeVisible()

    home.mockRejectedValueOnce(new ApiError(401, 'authentication_required', '需要登录。', []))
    const persisted = new Event('pageshow')
    Object.defineProperty(persisted, 'persisted', { value: true })
    await act(async () => {
      window.dispatchEvent(persisted)
    })

    await screen.findByRole('heading', { name: '107 Workspace' })
    expect(loginButtons().length).toBeGreaterThan(0)
    expect(screen.queryByText('同学，欢迎回来')).toBeNull()
  })
})
