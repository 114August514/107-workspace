// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { Home } from '../../src/api/types'
import { HomePage } from '../../src/pages/HomePage'
import { PrimerRoot } from '../../src/primer/setup'

const homeData: Home = {
  user: { id: 'u-1', username: 'student', display_name: '同学' },
  workspaces: [
    {
      id: 'ws-1',
      name: '计算物理课题组',
      description: '',
      kind: 'collaborative',
      owner_id: 'u-1',
      created_at: '2026-08-15T10:00:00Z',
      default_environment_version_id: null,
      role: null,
    },
  ],
  recent_projects: [
    {
      id: 'p-1',
      name: 'LJ 流体模拟',
      description: '',
      workspace_id: 'ws-1',
      status: 'active',
      created_by: 'u-1',
      created_at: '2026-08-15T10:00:00Z',
      updated_at: null,
      default_run_configuration_id: null,
      environment_version_id: null,
    },
  ],
  recent_runs: [
    {
      id: 'r-1',
      name: '首次基线运行',
      workspace_id: 'ws-1',
      project_id: 'p-1',
      project_version_id: 'v-1',
      project_version_label: 'v1',
      snapshot_id: 's-1',
      status: 'succeeded',
      created_by: 'u-1',
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

function renderHome() {
  return render(
    <PrimerRoot>
      <MemoryRouter>
        <HomePage username="student" />
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
  it('数据返回后三个栏目和算力目录都渲染条目', async () => {
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

    await waitFor(() => {
      expect(screen.getByText('计算物理课题组')).toBeInTheDocument()
    })
    expect(screen.getByText('LJ 流体模拟')).toBeInTheDocument()
    expect(screen.getByText('首次基线运行')).toBeInTheDocument()
    expect(screen.getByText('cpu-basic')).toBeInTheDocument()
  })

  it('没有数据时栏目显示空态说明，而不是只剩标题', async () => {
    vi.spyOn(api, 'home').mockResolvedValue({
      ...homeData,
      workspaces: [],
      recent_projects: [],
      recent_runs: [],
    })
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    renderHome()

    await waitFor(() => {
      expect(screen.getByText('还没有 Workspace')).toBeInTheDocument()
    })
    expect(screen.getByText('还没有 Project')).toBeInTheDocument()
    expect(screen.getByText('还没有提交过 Run')).toBeInTheDocument()
    expect(screen.getByText('暂无算力方案')).toBeInTheDocument()
  })
})
