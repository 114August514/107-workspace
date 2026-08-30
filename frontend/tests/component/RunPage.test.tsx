// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

import { api, ApiError } from '../../src/api/client'
import type {
  ComputePlan,
  LogChunk,
  Project,
  RunConfiguration,
  RunDetail,
} from '../../src/api/types'
import { RunLocatorPage } from '../../src/pages/RunLocatorPage'
import { RunPage } from '../../src/pages/RunPage'

const runDetailFixture = (): RunDetail => ({
  run: {
    id: 'run-1',
    name: 'test-run',
    project_id: 'project-1',
    capabilities: ['run.submit', 'run.cancel'],
    project_version_id: 'version-1',
    project_version_label: 'v1',
    snapshot_id: 'snapshot-1',
    source_run_id: null,
    source_run_configuration_id: 'config-1',
    status: 'succeeded',
    initiated_by_user_id: 'usr_internal_student',
    initiated_by_username: 'student',
    created_at: '2026-08-15T08:00:00Z',
    submitted_at: '2026-08-15T08:01:00Z',
    started_at: '2026-08-15T08:02:00Z',
    finished_at: '2026-08-15T08:10:00Z',
    scheduler_job_id: null,
    exit_code: 0,
    failure_reason: '',
    queued_seconds: 1,
    running_seconds: 8,
  },
  events: [],
  artifacts: [],
  snapshot: {
    id: 'snapshot-1',
    command: 'python train.py',
    environment_definition_hash: 'a'.repeat(64),
    environment_execution_spec: { kind: 'modules', commands: [] },
    environment_variables: {},
    environment_version_id: 'env-1',
    compute_plan_id: 'plan-1',
    compute_request: {
      cpus: 1,
      gpus: 0,
      memory_mb: 1024,
      nodes: 1,
      time_limit_minutes: 60,
    },
    artifact_rules: [],
    input_bindings: [],
    created_at: '2026-08-15T08:00:00Z',
    initiated_by_user_id: 'student',
    project_id: 'project-1',
    project_version_id: 'version-1',
    scheduler: {
      account: '',
      cluster: '',
      cpus: 1,
      gpus: 0,
      memory_mb: 1024,
      nodes: 1,
      partition: '',
      qos: '',
      time_limit_minutes: 60,
    },
    secret_references: {},
    source_run_configuration_id: 'config-1',
    working_directory: '',
  },
})

const projectFixture: Project = {
  id: 'project-1',
  owner: { kind: 'user_group', id: 'workspace-1', display_name: 'Demo Group' },
  name: 'Demo Project',
  description: '',
  status: 'active',
  visibility: 'owner_scope',
  environment_version_id: null,
  default_run_configuration_id: 'config-1',
  created_by: 'student',
  created_at: '2026-08-15T08:00:00Z',
  updated_at: '2026-08-15T08:00:00Z',
}

const configurationFixture: RunConfiguration = {
  id: 'config-1',
  project_id: 'project-1',
  name: '默认训练方案',
  description: '',
  command: 'python train.py',
  working_directory: '.',
  environment_version_id: 'env-1',
  compute_plan_id: 'plan-1',
  compute_request: null,
  environment_variables: {},
  input_bindings: [],
  artifact_rules: [],
}

const computePlanFixture: ComputePlan = {
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
}

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}</output>
}
function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/projects/project-1/runs/run-1']}>
      <Routes>
        <Route path="/projects/:projectId/runs/:runId" element={children} />
      </Routes>
    </MemoryRouter>
  )
}

describe('RunPage backend unavailable', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.spyOn(api, 'getProject').mockResolvedValue(projectFixture)
    vi.spyOn(api, 'listRunConfigurations').mockResolvedValue([configurationFixture])
    vi.spyOn(api, 'computePlans').mockResolvedValue([computePlanFixture])
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('converges from loading to stable error copy with retry, then recovers when API returns', async () => {
    let getRunCalls = 0
    vi.spyOn(api, 'getRun').mockImplementation(async () => {
      getRunCalls++
      if (getRunCalls === 1) {
        // 模拟 Vite proxy 把后端 ECONNREFUSED 转成非结构化 HTTP 500 的路径。
        throw new ApiError(500, 'http_error', '请求失败（HTTP 500）', [], '')
      }
      return runDetailFixture()
    })

    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    // Loading ends and context-specific error copy appears.
    await waitFor(() => {
      expect(screen.getByText('无法加载这个 Run。')).toBeInTheDocument()
    })
    expect(screen.getByText('请重试。')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /重\s*试/ })).toBeInTheDocument()

    // Unstructured HTTP 500/proxy wording must not be exposed to users.
    expect(screen.queryByText(/HTTP 500/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/请求失败（HTTP 500）/i)).not.toBeInTheDocument()

    // Retry re-fetches the run.
    fireEvent.click(screen.getByRole('button', { name: /重\s*试/ }))
    await waitFor(() => {
      expect(getRunCalls).toBe(2)
    })

    // After recovery the page content appears.
    await waitFor(() => {
      expect(screen.queryByText('无法加载这个 Run。')).not.toBeInTheDocument()
    })
    expect(await screen.findByRole('heading', { name: 'test-run' })).toBeInTheDocument()
    const runHeader = screen.getByRole('banner', { name: 'Run header' })
    expect(within(runHeader).getByText('student')).toBeInTheDocument()
    expect(within(runHeader).queryByText('usr_internal_student')).not.toBeInTheDocument()
  })

  it('keeps actions fail-closed and restores them from refreshed Run capabilities', async () => {
    const denied = runDetailFixture()
    denied.run.capabilities = []
    const restored = runDetailFixture()
    restored.run.capabilities = ['run.submit']

    const getRun = vi
      .spyOn(api, 'getRun')
      .mockResolvedValueOnce(denied)
      .mockResolvedValueOnce(restored)
    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])
    vi.spyOn(api, 'syncRuns').mockResolvedValue({ changed: 0 })

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    await screen.findByRole('heading', { name: 'test-run' })
    expect(screen.queryByRole('button', { name: '重新运行' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '刷新' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '更多 Run 操作' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '刷新' }))

    expect(await screen.findByRole('button', { name: '重新运行' })).toBeInTheDocument()
    expect(getRun).toHaveBeenCalledTimes(2)
  })

  it('keeps refresh and cancel directly available for an active Run', async () => {
    const active = runDetailFixture()
    active.run.status = 'running'
    vi.spyOn(api, 'getRun').mockResolvedValue(active)
    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    await screen.findByRole('heading', { name: 'test-run' })
    expect(screen.getByRole('button', { name: '刷新' })).toBeVisible()
    expect(screen.getByRole('button', { name: '取消 Run' })).toBeVisible()
    expect(screen.queryByRole('button', { name: '更多 Run 操作' })).toBeNull()
  })

  it('shows an explicit fallback instead of a missing User ID', async () => {
    const missingUserDetail = runDetailFixture()
    missingUserDetail.run = {
      ...missingUserDetail.run,
      initiated_by_user_id: 'usr_missing',
      initiated_by_username: null,
    }
    vi.spyOn(api, 'getRun').mockResolvedValue(missingUserDetail)
    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    const runHeader = await screen.findByRole('banner', { name: 'Run header' })
    expect(within(runHeader).getByText('未知用户')).toBeInTheDocument()
    expect(within(runHeader).queryByText('usr_missing')).not.toBeInTheDocument()
  })

  it('keeps Project context and prioritizes user semantics in the default summary', async () => {
    vi.spyOn(api, 'getRun').mockResolvedValue(runDetailFixture())
    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    await screen.findByRole('heading', { name: 'test-run' })
    const projectLinks = await screen.findAllByRole('link', { name: 'Demo Project' })
    expect(
      projectLinks.some((link) => link.getAttribute('href')?.endsWith('/projects/project-1')),
    ).toBe(true)
    expect((await screen.findAllByRole('link', { name: 'Runs' }))[0]).toHaveAttribute(
      'href',
      '/projects/project-1?tab=runs',
    )

    const runHeader = screen.getByRole('banner', { name: 'Run header' })
    expect(within(runHeader).getByText('student')).toBeVisible()
    expect(within(runHeader).getByText('运行 8 秒')).toBeVisible()
    expect(within(runHeader).getByText('排队 1 秒')).toBeVisible()
    expect(within(runHeader).getByRole('link', { name: 'v1' })).toBeVisible()
    expect(within(runHeader).getByText('默认训练方案')).toBeVisible()

    const summary = screen.getByLabelText('Run Summary')
    expect(within(summary).queryByRole('heading', { name: '执行信息' })).toBeNull()
    expect(within(summary).queryByRole('heading', { name: '来源' })).toBeNull()
    expect(within(summary).queryByRole('heading', { name: '来源关系' })).toBeNull()
    expect(within(summary).queryByText('首次运行')).toBeNull()
    const compute = within(summary).getByRole('heading', { name: '算力' }).parentElement!
    expect(within(compute).getByText('CPU 基础')).toBeVisible()
    expect(within(compute).getByText('cpu-basic')).toBeVisible()
    expect(within(compute).getByText('1 节点 · 1 核 · 1 GB')).toBeVisible()
    expect(within(compute).getByText('最长运行 1 小时')).toBeVisible()
    expect(within(summary).getByRole('heading', { name: '执行过程' })).toBeVisible()
    expect(within(summary).getByText('这个 Run 还没有执行事件。')).toBeVisible()
    expect(within(summary).getByText('完整运行快照')).toBeVisible()
    expect(within(summary).getByText('执行命令')).not.toBeVisible()
    expect(screen.getByText('诊断信息')).toBeVisible()
    expect(screen.getByText('调度任务')).not.toBeVisible()
    expect(screen.queryByRole('link', { name: '执行' })).toBeNull()
    expect(screen.queryByRole('link', { name: '运行快照' })).toBeNull()
  })

  it('uses Logs as a primary intent and keeps the timeline in Summary', async () => {
    const detail = runDetailFixture()
    detail.events = [
      {
        id: 'event-1',
        type: 'created',
        message: '已固定 Run Snapshot',
        created_at: '2026-08-15T08:00:00Z',
      },
    ]
    vi.spyOn(api, 'getRun').mockResolvedValue(detail)
    vi.spyOn(api, 'readLogs').mockResolvedValue([
      { stream: 'stdout', content: 'done', truncated: false },
      { stream: 'stderr', content: '', truncated: false },
    ])

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    await screen.findByRole('heading', { name: 'test-run' })
    expect(screen.getByRole('heading', { name: '执行过程' })).toBeVisible()
    const eventTime = screen.getByText(/^\d{2}:\d{2}$/)
    expect(eventTime.getAttribute('title')).toMatch(/^2026-08-15 \d{2}:00:00$/)
    fireEvent.click(screen.getByRole('link', { name: '日志' }))
    expect(screen.queryByRole('heading', { name: '执行过程' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '日志' })).toBeVisible()
    expect(screen.getByRole('link', { name: '标准输出' })).toBeVisible()
    expect(screen.getByRole('link', { name: '标准错误' })).toBeVisible()
  })

  it('offers a direct Logs action when the Run fails', async () => {
    const failed = runDetailFixture()
    failed.run.status = 'failed'
    failed.run.failure_reason = 'Process exited with code 1.'
    vi.spyOn(api, 'getRun').mockResolvedValue(failed)
    vi.spyOn(api, 'readLogs').mockResolvedValue([
      { stream: 'stdout', content: '', truncated: false },
      { stream: 'stderr', content: 'boom', truncated: false },
    ])

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    expect(await screen.findByText('Process exited with code 1.')).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '查看日志' }))
    expect(screen.getByRole('link', { name: '日志' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('heading', { name: '日志' })).toBeVisible()
  })

  it('returns to Summary when rerun navigation changes the Run ID', async () => {
    vi.spyOn(api, 'getRun').mockImplementation(async (id) => {
      const detail = runDetailFixture()
      detail.run.id = id
      detail.run.source_run_id = id === 'run-2' ? 'run-1' : null
      return detail
    })
    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])
    const rerun = runDetailFixture().run
    rerun.id = 'run-2'
    rerun.source_run_id = 'run-1'
    vi.spyOn(api, 'rerun').mockResolvedValue(rerun)

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    await screen.findByRole('heading', { name: 'test-run' })
    fireEvent.click(screen.getByRole('link', { name: '日志' }))
    expect(await screen.findByRole('heading', { name: '日志' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '重新运行' }))

    await waitFor(() =>
      expect(screen.getByRole('link', { name: '概览' })).toHaveAttribute('aria-current', 'page'),
    )
    expect(screen.getByRole('heading', { name: '执行过程' })).toBeVisible()
    expect(screen.getByLabelText('Run Summary')).toBeVisible()
    const runHeader = screen.getByRole('banner', { name: 'Run header' })
    expect(within(runHeader).getByRole('link', { name: 'Run #run-1' })).toHaveAttribute(
      'href',
      '/projects/project-1/runs/run-1',
    )
  })

  it('resolves an ID-only Run link into the canonical Project route', async () => {
    vi.spyOn(api, 'getRun').mockResolvedValue(runDetailFixture())

    render(
      <MemoryRouter initialEntries={['/runs/run-1']}>
        <Routes>
          <Route path="/runs/:runId" element={<RunLocatorPage />} />
          <Route path="/projects/:projectId/runs/:runId" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    )

    await waitFor(() =>
      expect(screen.getByTestId('location')).toHaveTextContent('/projects/project-1/runs/run-1'),
    )
  })
})
