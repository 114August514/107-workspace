// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { api, ApiError } from '../../src/api/client'
import type { LogChunk, Project, RunConfiguration, RunDetail } from '../../src/api/types'
import { RunPage } from '../../src/pages/RunPage'

const runDetailFixture = (): RunDetail => ({
  run: {
    id: 'run-1',
    name: 'test-run',
    project_id: 'project-1',
    workspace_id: 'workspace-1',
    project_version_id: 'version-1',
    project_version_label: 'v1',
    snapshot_id: 'snapshot-1',
    source_run_id: null,
    source_run_configuration_id: 'config-1',
    status: 'succeeded',
    initiated_by_user_id: 'student',
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
  capabilities: ['run.submit', 'run.cancel'],
  snapshot: {
    id: 'snapshot-1',
    command: 'python train.py',
    environment_image: 'python:3.11',
    environment_setup_command: '',
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
  workspace_id: 'workspace-1',
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

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <MemoryRouter initialEntries={['/runs/run-1']}>
      <Routes>
        <Route path="/runs/:runId" element={children} />
      </Routes>
    </MemoryRouter>
  )
}

describe('RunPage backend unavailable', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.spyOn(api, 'getProject').mockResolvedValue(projectFixture)
    vi.spyOn(api, 'listRunConfigurations').mockResolvedValue([configurationFixture])
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
    expect(screen.getByRole('heading', { name: 'test-run' })).toBeInTheDocument()
  })

  it('keeps actions fail-closed and restores them from refreshed Run capabilities', async () => {
    const denied = runDetailFixture()
    denied.capabilities = []
    const restored = runDetailFixture()
    restored.capabilities = ['run.submit']

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

    fireEvent.click(screen.getByRole('button', { name: '刷新' }))

    expect(await screen.findByRole('button', { name: '重新运行' })).toBeInTheDocument()
    expect(getRun).toHaveBeenCalledTimes(2)
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

    const summary = screen.getByLabelText('Run Summary')
    expect(
      within(summary)
        .getAllByRole('term')
        .map((term) => term.textContent),
    ).toEqual([
      '状态',
      '发起用户',
      'Project 版本',
      '运行方案',
      '运行时长',
      '排队时长',
      'Compute Plan',
      '执行来源',
    ])
    expect(within(summary).getByText('默认训练方案')).toBeVisible()
    expect(screen.getByText('诊断信息')).toBeVisible()
    expect(screen.getByText('调度任务')).not.toBeVisible()
  })

  it('nests stdout and stderr under Execution instead of page-level navigation', async () => {
    vi.spyOn(api, 'getRun').mockResolvedValue(runDetailFixture())
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
    expect(screen.queryByRole('link', { name: '日志' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('link', { name: '执行' }))
    expect(await screen.findByRole('heading', { name: '执行过程' })).toBeVisible()
    expect(screen.getByRole('heading', { name: '日志' })).toBeVisible()
    expect(screen.getByRole('link', { name: '标准输出' })).toBeVisible()
    expect(screen.getByRole('link', { name: '标准错误' })).toBeVisible()
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
    fireEvent.click(screen.getByRole('link', { name: '执行' }))
    expect(await screen.findByRole('heading', { name: '执行过程' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '重新运行' }))

    await waitFor(() =>
      expect(screen.getByRole('link', { name: '概览' })).toHaveAttribute('aria-current', 'page'),
    )
    expect(screen.queryByRole('heading', { name: '执行过程' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Run Summary')).toBeVisible()
  })
})
