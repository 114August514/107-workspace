// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { defaultPaneWidth } from '@primer/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StrictMode } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'

import { api, setCurrentUser } from '../../src/api/client'
import type { Home } from '../../src/api/types'
import type { AsyncState } from '../../src/api/useAsync'
import { App } from '../../src/App'
import { AppShell } from '../../src/components/layout/AppShell'
import { PrimerRoot } from '../../src/primer/setup'

const homeData: Home = {
  user: { id: 'u-1', username: 'student', display_name: '同学' },
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
  personal_resource_context_id: null,
  recent_projects: [
    {
      id: 'p-1',
      name: 'LJ 流体模拟',
      description: '',
      workspace_id: 'grp-1',
      status: 'active',
      created_by: 'u-1',
      created_at: '2026-08-15T10:00:00Z',
      updated_at: '2026-08-16T10:00:00Z',
      default_run_configuration_id: null,
      environment_version_id: null,
    },
  ],
  recent_runs: [],
}

function readyHome(data = homeData): AsyncState<Home> {
  return { data, loading: false, error: undefined, reload: vi.fn() }
}

const contextGuideCases = [
  ['/', '从最近的 Project 或 User Group 开始；进入 Project 后可选择版本发起 Run。'],
  ['/user-groups/grp-1', '在这里管理成员，并进入关联的 Project 与配置；协作内容保留在各自对象中。'],
  ['/workspaces/ws-1', '这里保留已有个人资源；进入 Project 后可继续查看文件、版本和 Run。'],
  [
    '/projects/p-1',
    '当前工作区文件是 Working State；创建 Project 版本后形成不可变快照，并可据此发起 Run。',
  ],
  ['/versions/v-1', '这是不可变的 Project 版本；可以比较、派生 Project，或基于它发起 Run。'],
  ['/runs/r-1', '这里展示当前 Run 的状态、日志和产物；后续修改不会回写其运行快照。'],
] as const

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}</output>
}

function renderShell(username: string, home = readyHome(), initialEntry = '/') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <PrimerRoot>
        <AppShell username={username} onUsernameChange={() => {}} home={home}>
          <p>页面内容</p>
          <LocationProbe />
        </AppShell>
      </PrimerRoot>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  window.localStorage.removeItem('workspace107.devUser')
  setCurrentUser('student')
  vi.restoreAllMocks()
})

describe('AppShell 壳层', () => {
  it.each(contextGuideCases)('路由 %s 显示对应的页面引导', (pathname, message) => {
    renderShell('student', readyHome(), pathname)

    const guide = screen.getByRole('complementary', { name: '页面引导' })
    expect(guide).toHaveTextContent(message)
    expect(guide.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByText('GPU 型号、分区、QoS 和配额等信息以平台页面为准。')).toBeNull()
  })

  it('不为未匹配的嵌套路径显示页面引导', () => {
    renderShell('student', readyHome(), '/projects/p-1/extra')

    expect(screen.queryByRole('complementary', { name: '页面引导' })).toBeNull()
  })

  it('非首页 Body 仅直接包含 main，Primer Content 在 main 内负责正文居中', () => {
    renderShell('student', readyHome(), '/projects/p-1')
    const body = screen.getByRole('banner').nextElementSibling
    const main = screen.getByRole('main')
    const layout = main.querySelector('[data-component="PageLayout"]')
    const centeredContent = main.querySelector<HTMLElement>('[data-component="PageLayout.Content"]')

    expect(body?.firstElementChild).toBe(main)
    expect(main.parentElement).toBe(body)
    expect(screen.queryByRole('complementary', { name: '首页工作入口' })).toBeNull()
    expect(layout?.querySelector('[data-component="PageLayout.Sidebar"]')).toBeNull()
    expect(centeredContent).toHaveProperty('tagName', 'DIV')
    expect(centeredContent?.firstElementChild).toHaveAttribute('data-width', 'xlarge')
    expect(main).toContainElement(screen.getByText('页面内容'))
  })

  it('首页 Body 直接 stretch persistent sidebar 与 main，Primer 只负责正文居中', () => {
    renderShell('student')
    const body = screen.getByRole('banner').nextElementSibling
    const sidebar = screen.getByRole('complementary', { name: '首页工作入口' })
    const main = screen.getByRole('main')
    const centeredContent = main.querySelector<HTMLElement>('[data-component="PageLayout.Content"]')

    const shell = body?.parentElement
    expect(sidebar.parentElement).toBe(body)
    expect(sidebar.nextElementSibling).toBe(main)
    expect(main.parentElement).toBe(body)
    expect(shell?.style.getPropertyValue('--app-shell-sidebar-width')).toBe(
      `${defaultPaneWidth.medium}px`,
    )
    expect(within(sidebar).getByRole('navigation', { name: '工作入口' })).toBeVisible()
    expect(centeredContent).toHaveProperty('tagName', 'DIV')
    expect(centeredContent?.firstElementChild).toHaveAttribute('data-width', 'xlarge')
    expect(main).toContainElement(screen.getByText('页面内容'))
    expect(screen.getAllByRole('main')).toHaveLength(1)
  })

  it('header 菜单打开 overlay 工作导航，并通过真实链接导航后关闭', async () => {
    renderShell('student')

    const trigger = screen.getByRole('button', { name: '打开导航' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(trigger)

    const dialog = await screen.findByRole('dialog', { name: '107 Workspace' })
    expect(dialog).toBeVisible()
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    const homeLink = within(dialog).getByRole('link', { name: '首页' })
    expect(homeLink).toHaveAttribute('aria-current', 'page')
    expect(within(homeLink).getByText('首页', { selector: 'span' })).toBeVisible()
    expect(within(dialog).getByRole('link', { name: '计算物理课题组' })).toHaveAttribute(
      'href',
      '/user-groups/grp-1',
    )
    fireEvent.click(within(dialog).getByRole('link', { name: /LJ 流体模拟/ }))

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '107 Workspace' })).toBeNull())
    expect(screen.getByTestId('location')).toHaveTextContent('/projects/p-1')
  })

  it('Escape 关闭导航并把焦点返回 header 菜单按钮', async () => {
    renderShell('student')

    const trigger = screen.getByRole('button', { name: '打开导航' })
    fireEvent.click(trigger)
    const dialog = await screen.findByRole('dialog', { name: '107 Workspace' })
    fireEvent.keyDown(dialog, { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('dialog', { name: '107 Workspace' })).toBeNull())
    expect(trigger).toHaveFocus()
  })

  it('导航加载失败只影响抽屉，不阻断当前页面内容', async () => {
    renderShell('student', {
      data: undefined,
      loading: false,
      error: new Error('offline'),
      reload: vi.fn(),
    })

    expect(screen.getByText('页面内容')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '打开导航' }))
    expect(await screen.findByText('工作入口加载失败。')).toBeVisible()
    expect(screen.getByText('页面内容')).toBeVisible()
  })

  it('header 创建按钮打开创建 User Group 弹窗', async () => {
    renderShell('student')
    fireEvent.click(screen.getByRole('button', { name: '创建 User Group' }))
    expect(await screen.findByRole('dialog')).toBeVisible()
    expect(screen.getByText('创建 User Group', { selector: 'h1' })).toBeTruthy()
  })

  it('身份切换器展示当前身份并展开可选身份', async () => {
    renderShell('student')
    fireEvent.click(screen.getByRole('button', { name: '切换身份，当前 student' }))
    expect(await screen.findByRole('menuitem', { name: 'teacher' })).toBeVisible()
  })

  it('首页与抽屉共享一次 /me 请求', async () => {
    const home = vi.spyOn(api, 'home').mockResolvedValue(homeData)
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])
    vi.spyOn(api, 'unreadCount').mockResolvedValue(0)

    render(
      <StrictMode>
        <MemoryRouter>
          <App />
        </MemoryRouter>
      </StrictMode>,
    )
    const sidebar = await screen.findByRole('complementary', { name: '首页工作入口' })
    expect(within(sidebar).getByRole('link', { name: '计算物理课题组' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '打开导航' }))
    const dialog = await screen.findByRole('dialog', { name: '107 Workspace' })
    expect(within(dialog).getByRole('link', { name: '计算物理课题组' })).toBeVisible()
    expect(home).toHaveBeenCalledTimes(1)
  })

  it('切换身份时不短暂显示旧用户的工作入口', async () => {
    let resolveStudent!: (home: Home) => void
    const teacherHome: Home = {
      ...homeData,
      user: { id: 'u-2', username: 'teacher', display_name: '老师' },
      user_groups: [
        {
          id: 'grp-teacher',
          name: '教师用户组',
          description: '',
          created_by_id: 'u-2',
          created_at: '2026-08-15T10:00:00Z',
          role: 'owner',
          capabilities: [],
        },
      ],
      recent_projects: [],
    }
    const home = vi
      .spyOn(api, 'home')
      .mockImplementationOnce(
        () =>
          new Promise<Home>((resolve) => {
            resolveStudent = resolve
          }),
      )
      .mockResolvedValueOnce(teacherHome)
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])
    vi.spyOn(api, 'unreadCount').mockResolvedValue(0)
    window.localStorage.setItem('workspace107.devUser', 'student')
    setCurrentUser('student')

    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByRole('button', { name: '切换身份，当前 student' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: 'teacher' }))

    fireEvent.click(screen.getByRole('button', { name: '打开导航' }))
    const dialog = await screen.findByRole('dialog', { name: '107 Workspace' })
    expect(within(dialog).getByRole('link', { name: '教师用户组' })).toBeVisible()
    await act(async () => resolveStudent(homeData))
    expect(within(dialog).queryByRole('link', { name: '计算物理课题组' })).toBeNull()
    expect(home).toHaveBeenCalledTimes(2)
  })
})

describe('AppShell 身份切换的乱序防护', () => {
  it('旧身份迟到的未读数不能盖掉新身份刚拉到的数字', async () => {
    let calls = 0
    let resolveFirst!: (n: number) => void
    vi.spyOn(api, 'unreadCount').mockImplementation(() => {
      calls += 1
      if (calls === 1) {
        // student 的请求在网络上悬着，等身份已切换到 teacher 后才返回
        return new Promise<number>((resolve) => {
          resolveFirst = resolve
        })
      }
      return Promise.resolve(7)
    })

    const { rerender } = renderShell('student')
    rerender(
      <MemoryRouter>
        <PrimerRoot>
          <AppShell username="teacher" onUsernameChange={() => {}} home={readyHome()}>
            <p>页面内容</p>
          </AppShell>
        </PrimerRoot>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '通知，7 条未读' })).toBeTruthy()
    })

    // student 的响应这时才落地：key 重挂载已丢弃旧实例，这声 setState 不该生效
    await act(async () => {
      resolveFirst(3)
    })
    expect(screen.getByRole('button', { name: '通知，7 条未读' })).toBeTruthy()
  })
})
