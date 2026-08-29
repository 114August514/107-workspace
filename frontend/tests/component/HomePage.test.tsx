// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from '../../src/api/client'
import type { Home, Invitation } from '../../src/api/types'
import { useAsync } from '../../src/api/useAsync'
import { HomePage } from '../../src/pages/HomePage'
import { PrimerRoot } from '../../src/primer/setup'

const invitation: Invitation = {
  user_group_id: 'grp-inv',
  user_group_name: 'test_invite',
  user_group_description: '',
  role: 'member',
  invited_at: '2026-08-15T10:00:00Z',
}

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
  personal_execution_context: {
    owner: { kind: 'user', id: 'u-1', display_name: '同学' },
    entitlements: [],
  },
  recent_projects: [
    {
      id: 'p-1',
      name: 'LJ 流体模拟',
      description: '',
      owner: { kind: 'user', id: 'u-1', display_name: 'student' },
      visibility: 'owner_scope',
      status: 'active',
      created_by: 'u-1',
      created_at: '2026-08-15T10:00:00Z',
      updated_at: '2026-08-16T10:00:00Z',
      default_run_configuration_id: null,
      environment_version_id: null,
    },
  ],
  recent_runs: [
    {
      id: 'r-1',
      name: '首次基线运行',
      project_id: 'p-1',
      project_version_id: 'v-1',
      project_version_label: 'v1',
      snapshot_id: 's-1',
      status: 'succeeded',
      initiated_by_user_id: 'u-1',
      initiated_by_username: 'student',
      created_at: '2026-08-15T10:00:00Z',
      submitted_at: null,
      started_at: null,
      finished_at: null,
      exit_code: null,
      failure_reason: '',
      scheduler_job_id: null,
      source_run_id: null,
      source_run_configuration_id: null,
    },
  ],
}

function HomeHarness() {
  const home = useAsync<Home>(() => api.home(), ['student'])
  return <HomePage username="student" home={home} />
}

function renderHome() {
  return render(
    <PrimerRoot>
      <MemoryRouter>
        <HomeHarness />
      </MemoryRouter>
    </PrimerRoot>,
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('HomePage 各栏目渲染内容而不只是标题', () => {
  /**
   * 这条测试来自一个真实事故：@primer/react 38 的 experimental Card
   * 只要出现 Card.Heading 这类 slot，其余子元素会被整个丢弃，
   * 首页三个卡片一度只剩标题。守的是「栏目里看得到数据」这个行为。
   */
  it('数据返回后最近 Run 和算力目录都渲染条目', async () => {
    vi.spyOn(api, 'home').mockResolvedValue(homeData)
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([
      {
        id: 'plan-1',
        code: 'cpu-basic',
        name: 'CPU 基础',
        description: '单节点 CPU',
        max_nodes: 1,
        max_cpus: 8,
        max_gpus: 0,
        max_memory_mb: 8192,
        max_time_limit_minutes: 60,
        default_nodes: 1,
        default_cpus: 2,
        default_gpus: 0,
        default_memory_mb: 2048,
        default_time_limit_minutes: 30,
      },
    ])

    renderHome()

    expect(await screen.findByText('首次基线运行')).toBeInTheDocument()
    expect(await screen.findByText('cpu-basic')).toBeInTheDocument()
  })

  it('HomePage 正文不自行渲染导航或重复的 User Group、Project 卡片', async () => {
    vi.spyOn(api, 'home').mockResolvedValue(homeData)
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    renderHome()

    expect(await screen.findByRole('region', { name: '最近提交的 Run' })).toBeVisible()
    expect(screen.queryByRole('complementary', { name: '首页工作入口' })).toBeNull()
    expect(screen.queryByRole('navigation', { name: '工作入口' })).toBeNull()
    expect(screen.queryByRole('region', { name: '我的 User Group' })).toBeNull()
    expect(screen.queryByRole('region', { name: '最近使用的 Project' })).toBeNull()
  })

  it('没有数据时栏目显示空态说明，而不是只剩标题', async () => {
    vi.spyOn(api, 'home').mockResolvedValue({
      ...homeData,
      user_groups: [],
      recent_projects: [],
      recent_runs: [],
    })
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    renderHome()

    expect(await screen.findByText('还没有提交过 Run')).toBeInTheDocument()
    expect(await screen.findByText('暂无算力方案')).toBeInTheDocument()
  })
})

describe('HomePage 首页请求统一异步状态', () => {
  it('首页请求 pending 时只显示一次统一 loading 文案', async () => {
    let resolveHome!: (value: Home) => void
    vi.spyOn(api, 'home').mockImplementation(
      () =>
        new Promise<Home>((resolve) => {
          resolveHome = resolve
        }),
    )
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    renderHome()

    expect(screen.getAllByText('正在加载首页内容…')).toHaveLength(1)
    expect(screen.queryByText('正在加载工作区…')).toBeNull()
    expect(screen.queryByText('正在加载项目…')).toBeNull()
    expect(screen.queryByText('正在加载 Run…')).toBeNull()
    resolveHome(homeData)
  })

  it('首页首次失败只显示一份错误和重试，成功后恢复首页内容', async () => {
    const home = vi
      .spyOn(api, 'home')
      .mockRejectedValueOnce(new ApiError(500, 'internal_error', '首页加载失败。', []))
      .mockResolvedValueOnce(homeData)
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    renderHome()

    expect(await screen.findAllByText('首页加载失败。')).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: '重试' })).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    await waitFor(() => expect(home).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('首次基线运行')).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: '工作入口' })).toBeNull()
  })
})

describe('HomePage 邀请区块', () => {
  it('以紧凑行呈现：User Group 名称 + 身份说明 + 并排的接受/拒绝，而不是通知式 Banner', async () => {
    vi.spyOn(api, 'home').mockResolvedValue(homeData)
    vi.spyOn(api, 'listInvitations').mockResolvedValue([invitation])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    renderHome()

    expect(await screen.findByText('待处理邀请')).toBeInTheDocument()
    expect(await screen.findByText('test_invite')).toBeInTheDocument()
    expect(screen.getByText('User Group · 成员')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '接受邀请' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '拒绝' })).toBeInTheDocument()
    expect(screen.queryByText(/邀请你以/)).not.toBeInTheDocument()
  })

  it('接受邀请调用 API 并在重载后从列表消失', async () => {
    vi.spyOn(api, 'home').mockResolvedValue(homeData)
    vi.spyOn(api, 'listInvitations').mockResolvedValueOnce([invitation]).mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])
    const respond = vi.spyOn(api, 'respondToInvitation').mockResolvedValue(undefined)

    renderHome()

    fireEvent.click(await screen.findByRole('button', { name: '接受邀请' }))
    await waitFor(() => expect(respond).toHaveBeenCalledWith('grp-inv', true))
    await waitFor(() => expect(screen.queryByText('test_invite')).not.toBeInTheDocument())
  })

  it('加载邀请时提供可访问的可见反馈', async () => {
    vi.spyOn(api, 'home').mockResolvedValue(homeData)
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    renderHome()

    const invitations = await screen.findByRole('region', { name: '待处理邀请' })
    expect(within(invitations).getByRole('status')).toHaveTextContent('正在加载邀请…')
  })

  it('首次加载邀请失败时就地显示错误并可重试，成功空数据后隐藏区块', async () => {
    vi.spyOn(api, 'home').mockResolvedValue(homeData)
    const invitations = vi
      .spyOn(api, 'listInvitations')
      .mockRejectedValueOnce(
        new ApiError(503, 'service_unavailable', '邀请加载失败。', [], 'req-invitations'),
      )
      .mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    renderHome()

    expect(await screen.findByText('邀请加载失败。')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '重试' }))

    await waitFor(() => expect(invitations).toHaveBeenCalledTimes(2))
    await waitFor(() => expect(screen.queryByRole('region', { name: '待处理邀请' })).toBeNull())
  })
})
