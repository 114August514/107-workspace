// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

import { api, ApiError } from '../../src/api/client'
import type {
  ComputePlan,
  Environment,
  EnvironmentVersion,
  LogChunk,
  Project,
  RunConfiguration,
  RunDetail,
} from '../../src/api/types'
import { ArtifactFilePreviewPage } from '../../src/pages/ArtifactFilePreviewPage'
import { RunLocatorPage } from '../../src/pages/RunLocatorPage'
import { AdjustedRerunModal } from '../../src/components/run/AdjustedRerunModal'
import { RunLogPanel } from '../../src/components/run/RunLogPanel'
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

const environmentVersionFixture: EnvironmentVersion = {
  id: 'env-1',
  environment_id: 'environment-1',
  version: '3.12',
  description: '',
  runtime_kind: 'modules',
  definition: {},
  definition_hash: 'a'.repeat(64),
  execution_spec: { kind: 'modules', commands: [] },
  availability: 'available',
  availability_checked_at: '2026-08-15T08:00:00Z',
  availability_detail: '',
  availability_reason: '',
  validation_evidence: {},
  validation_summary: '',
}

const environmentFixture: Environment = {
  id: 'environment-1',
  name: 'Python',
  description: '',
  owner: { kind: 'user_group', id: 'workspace-1', display_name: 'Demo Group' },
  versions: [environmentVersionFixture],
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

function ArtifactPreviewWrapper({ path }: { path: string }) {
  return (
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/projects/:projectId/runs/:runId/artifacts/:artifactId/file"
          element={<ArtifactFilePreviewPage />}
        />
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
    vi.spyOn(api, 'environmentVersion').mockResolvedValue(environmentVersionFixture)
    vi.spyOn(api, 'environment').mockResolvedValue(environmentFixture)
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
    expect(within(runHeader).queryByText('student')).not.toBeInTheDocument()
    expect(within(runHeader).queryByText('usr_internal_student')).not.toBeInTheDocument()
    expect(within(screen.getByLabelText('Run Summary')).getByText('student')).toBeVisible()
    expect(within(runHeader).getByText('#run-1')).toBeVisible()
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
    expect(within(runHeader).queryByText('未知用户')).not.toBeInTheDocument()
    expect(within(runHeader).queryByText('usr_missing')).not.toBeInTheDocument()
    expect(within(screen.getByLabelText('Run Summary')).getByText('未知用户')).toBeVisible()
  })

  it('keeps Run semantics without duplicating Project navigation', async () => {
    vi.spyOn(api, 'getRun').mockResolvedValue(runDetailFixture())
    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    await screen.findByRole('link', { name: 'Demo Project · v1' })
    expect(screen.queryByRole('link', { name: '项目文件' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '运行方案' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '版本' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Runs' })).toHaveAttribute(
      'href',
      '/projects/project-1/runs',
    )

    const runHeader = screen.getByRole('banner', { name: 'Run header' })
    expect(within(runHeader).queryByText('student')).not.toBeInTheDocument()
    expect(within(runHeader).queryByText('8 秒')).not.toBeInTheDocument()
    expect(within(runHeader).queryByText('默认训练方案')).not.toBeInTheDocument()
    expect(within(runHeader).getByText('#run-1')).toBeVisible()
    expect(within(runHeader).getByLabelText('成功')).toBeVisible()
    expect(runHeader.querySelector('[data-component="Label"]')).toBeNull()

    const summary = screen.getByLabelText('Run Summary')
    expect(within(summary).getByRole('heading', { name: '执行过程' })).toBeVisible()
    expect(within(summary).getByText('这个 Run 还没有执行事件。')).toBeVisible()

    const snapshotSummary = within(summary)
      .getByRole('heading', { name: '运行快照' })
      .closest('section')!
    expect(within(snapshotSummary).getByText('本次 Run 的不可变执行配置')).toBeVisible()
    const basicTab = within(snapshotSummary).getByRole('button', { name: '基本信息' })
    const environmentTab = within(snapshotSummary).getByRole('button', { name: '环境与算力' })
    const executionTab = within(snapshotSummary).getByRole('button', { name: '执行配置' })
    expect(basicTab).toHaveAttribute('aria-pressed', 'true')
    expect(within(snapshotSummary).getByRole('link', { name: 'Demo Project · v1' })).toBeVisible()
    expect(within(snapshotSummary).getByText('默认训练方案')).toBeVisible()
    expect(within(snapshotSummary).getByText('student')).toBeVisible()
    expect(within(snapshotSummary).getByText('8 秒')).toBeVisible()
    expect(within(snapshotSummary).queryByRole('link', { name: 'Python · 3.12' })).toBeNull()

    fireEvent.click(environmentTab)
    expect(environmentTab).toHaveAttribute('aria-pressed', 'true')
    expect(within(snapshotSummary).getByRole('link', { name: 'Python · 3.12' })).toBeVisible()
    expect(within(snapshotSummary).getByText('CPU 基础')).toBeVisible()
    expect(within(snapshotSummary).getByText('1 节点 · 1 核 · 1 GB')).toBeVisible()
    expect(within(snapshotSummary).getByText('最长运行 1 小时')).toBeVisible()
    expect(within(snapshotSummary).getByText('cpu-basic')).toBeVisible()

    fireEvent.click(executionTab)
    expect(executionTab).toHaveAttribute('aria-pressed', 'true')
    expect(within(snapshotSummary).getByText('python train.py')).toBeVisible()
    expect(within(snapshotSummary).queryByRole('link', { name: 'Python · 3.12' })).toBeNull()
    expect(within(summary).queryByText('完整运行快照')).toBeNull()

    const diagnosticSummary = screen.getByText('诊断信息').closest('summary')!
    expect(screen.getByText('调度任务')).not.toBeVisible()
    fireEvent.click(diagnosticSummary)
    expect(screen.getByText('环境执行规格')).toBeVisible()
    expect(screen.getByText('env-1')).toBeVisible()
    expect(screen.queryByRole('link', { name: '执行' })).toBeNull()
    expect(screen.queryByRole('link', { name: '运行快照' })).toBeNull()
  })

  it('keeps the Snapshot readable when its environment label is unavailable', async () => {
    vi.spyOn(api, 'getRun').mockResolvedValue(runDetailFixture())
    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])
    vi.spyOn(api, 'environmentVersion').mockRejectedValue(new Error('unavailable'))

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    const snapshotSummary = (await screen.findByRole('heading', { name: '运行快照' })).closest(
      'section',
    )!
    fireEvent.click(within(snapshotSummary).getByRole('button', { name: '环境与算力' }))
    expect(await within(snapshotSummary).findByText('运行环境信息暂不可用')).toBeVisible()
    expect(screen.getByRole('heading', { name: '运行快照' })).toBeVisible()
    expect(screen.getByText('env-1')).not.toBeVisible()
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
    const eventTime = screen.getByText(/^\d{2}:\d{2}:\d{2}$/)
    expect(eventTime.getAttribute('title')).toMatch(/^2026-08-15 \d{2}:00:00$/)
    expect(screen.getByRole('img', { name: '已完成' })).toBeVisible()
    const logsSummary = screen.getByText('日志')
    const logsDisclosure = logsSummary.closest('details')
    expect(logsDisclosure).not.toHaveAttribute('open')
    fireEvent.click(logsSummary)
    expect(logsDisclosure).toHaveAttribute('open')
    expect(screen.getByRole('button', { name: '标准输出' })).toBeVisible()
    expect(screen.getByRole('button', { name: '标准错误' })).toBeVisible()
    expect(screen.getByLabelText('stdout 日志')).toHaveTextContent('done')
    expect(screen.queryByRole('button', { name: '自动换行' })).toBeNull()
  })

  it('shows relative artifact trees inside independently collapsible groups', async () => {
    const detail = runDetailFixture()
    detail.artifacts = [
      {
        id: 'artifact-1',
        run_id: detail.run.id,
        name: '训练指标',
        description: '',
        source_path: 'outputs',
        status: 'available',
        file_count: 3,
        size: 4096,
        created_at: '2026-08-15T08:10:00Z',
      },
    ]
    vi.spyOn(api, 'getRun').mockResolvedValue(detail)
    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])
    vi.spyOn(api, 'listArtifactFiles').mockResolvedValue([
      { path: 'metrics.json', size: 515 },
      { path: 'plots/loss.png', size: 1024 },
      { path: 'plots/nested/chart.png', size: 2557 },
    ])

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    await screen.findByRole('heading', { name: 'test-run' })
    const artifactSummary = screen.getByText('运行产物')
    const artifactDisclosure = artifactSummary.closest('details')
    expect(artifactDisclosure).not.toHaveAttribute('open')
    expect(screen.queryByText('训练指标')).toBeNull()
    fireEvent.click(artifactSummary)
    expect(artifactDisclosure).toHaveAttribute('open')
    const groupSummary = await screen.findByText('训练指标')
    const group = groupSummary.closest('details')
    expect(group).toHaveAttribute('open')
    expect(within(group!).getByText('outputs')).toBeVisible()
    expect(screen.queryByText('outputs/')).toBeNull()
    expect(await screen.findByRole('list', { name: '训练指标 文件' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'metrics.json' })).toHaveAttribute(
      'href',
      '/projects/project-1/runs/run-1/artifacts/artifact-1/file?path=metrics.json',
    )
    expect(screen.getByRole('button', { name: '下载 metrics.json' })).toBeVisible()

    const directory = screen.getByText('plots/').closest('details')
    expect(directory).not.toHaveAttribute('open')
    expect(screen.getByText('loss.png')).not.toBeVisible()
    fireEvent.click(screen.getByText('plots/'))
    expect(directory).toHaveAttribute('open')
    expect(screen.getByText('loss.png')).toBeVisible()
    expect(screen.getByText('nested/').closest('details')).not.toHaveAttribute('open')
    expect(screen.getByText('chart.png')).not.toBeVisible()

    fireEvent.click(groupSummary)
    expect(group).not.toHaveAttribute('open')
  })

  it('keeps execution identifiers out of the user-facing Timeline', async () => {
    const detail = runDetailFixture()
    detail.run.source_run_id = 'run_89086a75'
    detail.run.scheduler_job_id = 'mock-37485c97fc49'
    detail.snapshot.scheduler.cluster = '107'
    detail.snapshot.scheduler.partition = 'debug'
    detail.events = [
      {
        id: 'event-created',
        type: 'created',
        message: '基于 Run run_89086a75 重新运行',
        created_at: '2026-08-15T08:00:00Z',
      },
      {
        id: 'event-submitted',
        type: 'submitted',
        message: '已提交到 107/debug，调度任务 mock-37485c97fc49',
        created_at: '2026-08-15T08:01:00Z',
      },
      {
        id: 'event-finished',
        type: 'finished',
        message: '任务结束，状态 succeeded，退出码 0',
        created_at: '2026-08-15T08:10:00Z',
      },
    ]
    vi.spyOn(api, 'getRun').mockResolvedValue(detail)
    vi.spyOn(api, 'readLogs').mockResolvedValue([] as LogChunk[])

    render(
      <Wrapper>
        <RunPage />
      </Wrapper>,
    )

    const runHeader = await screen.findByRole('banner', { name: 'Run header' })
    expect(within(runHeader).getByText('#run-1')).toBeVisible()
    expect(within(runHeader).queryByRole('link', { name: 'Run #89086a75' })).not.toBeInTheDocument()
    const timeline = screen.getByRole('list', { name: 'Run 执行事件' })
    expect(within(timeline).getByText('已固定本次运行快照')).toBeVisible()
    expect(within(timeline).getByText('已提交到 107/debug')).toBeVisible()
    const snapshotSummary = screen.getByLabelText('基本信息运行快照')
    expect(within(snapshotSummary).getByRole('link', { name: 'Run #89086a75' })).toBeVisible()
    expect(within(timeline).getByText('运行成功')).toBeVisible()
    expect(within(timeline).queryByText(/基于 Run|mock-|succeeded|退出码/)).toBeNull()
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
    const logsLink = screen.getByRole('link', { name: '查看日志' })
    expect(logsLink).toHaveAttribute('href', '#run-logs')
    fireEvent.click(logsLink)
    expect(screen.getByText('日志').closest('details')).toHaveAttribute('open')
    expect(screen.getByLabelText('stderr 日志')).toHaveTextContent('boom')
  })
  it('switches to stderr when a running Run becomes failed', async () => {
    const chunks: LogChunk[] = [
      { stream: 'stdout', content: 'progress', truncated: false },
      { stream: 'stderr', content: 'failure details', truncated: false },
    ]
    const view = render(<RunLogPanel chunks={chunks} failed={false} />)

    expect(screen.getByRole('button', { name: '标准输出' })).toHaveAttribute('aria-pressed', 'true')
    view.rerender(<RunLogPanel chunks={chunks} failed />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: '标准错误' })).toHaveAttribute(
        'aria-pressed',
        'true',
      ),
    )
    expect(screen.getByLabelText('stderr 日志')).toHaveTextContent('failure details')
  })
  it('offers complete log downloads separately from the truncated preview', async () => {
    const downloadLogs = vi.spyOn(api, 'downloadLogs').mockResolvedValue()
    const chunks: LogChunk[] = [
      { stream: 'stdout', content: 'preview', truncated: true },
      { stream: 'stderr', content: '', truncated: false },
    ]
    render(<RunLogPanel runId="run-1" chunks={chunks} />)

    fireEvent.click(screen.getByRole('button', { name: '下载完整日志' }))
    await waitFor(() => expect(downloadLogs).toHaveBeenCalledWith('run-1', 'combined'))
  })

  it('submits adjusted rerun directly and does not preflight the mutable configuration', async () => {
    const detail = runDetailFixture()
    const adjustedRerun = vi.spyOn(api, 'adjustedRerun').mockResolvedValue(detail.run)
    const preflight = vi.spyOn(api, 'preflight')
    const onSubmitted = vi.fn()

    render(<AdjustedRerunModal open detail={detail} onClose={() => {}} onSubmitted={onSubmitted} />)

    fireEvent.click(await screen.findByRole('button', { name: '创建新 Run' }))
    await waitFor(() => expect(adjustedRerun).toHaveBeenCalled())
    expect(preflight).not.toHaveBeenCalled()
    expect(adjustedRerun).toHaveBeenCalledWith(
      'run-1',
      expect.objectContaining({
        project_version_id: 'version-1',
        environment_version_id: 'env-1',
        command: 'python train.py',
        working_directory: '.',
      }),
      expect.any(String),
    )
    expect(onSubmitted).toHaveBeenCalledWith(detail.run)
  })

  it('shows adjusted endpoint validation errors without a second mutable-config preflight', async () => {
    vi.spyOn(api, 'adjustedRerun').mockRejectedValue(
      new ApiError(422, 'preflight_rejected', '无法创建 Run', ['Secret 已失效'], 'req-48'),
    )
    const preflight = vi.spyOn(api, 'preflight')
    const onSubmitted = vi.fn()
    render(
      <AdjustedRerunModal
        open
        detail={runDetailFixture()}
        onClose={() => {}}
        onSubmitted={onSubmitted}
      />,
    )

    fireEvent.click(await screen.findByRole('button', { name: '创建新 Run' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Secret 已失效')
    expect(preflight).not.toHaveBeenCalled()
    expect(onSubmitted).not.toHaveBeenCalled()
  })

  it('collapses logs when rerun navigation changes the Run ID', async () => {
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
    fireEvent.click(screen.getByText('日志'))
    expect(screen.getByText('日志').closest('details')).toHaveAttribute('open')
    fireEvent.click(screen.getByRole('button', { name: '重新运行' }))
    await waitFor(() =>
      expect(screen.getByRole('banner', { name: 'Run header' })).toHaveTextContent('#run-2'),
    )
    expect(within(screen.getByLabelText('基本信息运行快照')).getByText('来源 Run')).toBeVisible()
    expect(screen.getByText('日志').closest('details')).not.toHaveAttribute('open')
    expect(screen.getByRole('heading', { name: '执行过程' })).toBeVisible()
    expect(screen.getByLabelText('Run Summary')).toBeVisible()
    const snapshotSummary = screen.getByLabelText('基本信息运行快照')
    expect(within(snapshotSummary).getByRole('link', { name: 'Run #run-1' })).toHaveAttribute(
      'href',
      '/projects/project-1/runs/run-1',
    )
  })

  it('previews text Artifact files on a dedicated route', async () => {
    const detail = runDetailFixture()
    detail.artifacts = [
      {
        id: 'artifact-1',
        run_id: detail.run.id,
        name: '训练指标',
        description: '',
        source_path: 'outputs',
        status: 'available',
        file_count: 1,
        size: 515,
        created_at: '2026-08-15T08:10:00Z',
      },
    ]
    vi.spyOn(api, 'getRun').mockResolvedValue(detail)
    vi.spyOn(api, 'listArtifactFiles').mockResolvedValue([{ path: 'metrics.json', size: 515 }])
    const content = new TextEncoder().encode('{"loss": 0.2489, "accuracy": 0.917}')
    vi.spyOn(api, 'readArtifactFile').mockResolvedValue({
      arrayBuffer: async () => content.buffer,
    } as Blob)

    render(
      <ArtifactPreviewWrapper path="/projects/project-1/runs/run-1/artifacts/artifact-1/file?path=metrics.json" />,
    )

    expect(await screen.findByRole('heading', { name: 'metrics.json' })).toBeVisible()
    expect(screen.getByRole('link', { name: '返回运行产物' })).toHaveAttribute(
      'href',
      '/projects/project-1/runs/run-1#run-artifacts',
    )
    expect(await screen.findByLabelText('metrics.json 内容')).toHaveTextContent('"loss"')
    expect(api.readArtifactFile).toHaveBeenCalledWith('artifact-1', 'metrics.json')
  })

  it('keeps known binary Artifact files downloadable without reading them into the preview', async () => {
    const detail = runDetailFixture()
    detail.artifacts = [
      {
        id: 'artifact-2',
        run_id: detail.run.id,
        name: '模型检查点',
        description: '',
        source_path: 'checkpoints',
        status: 'available',
        file_count: 1,
        size: 4096,
        created_at: '2026-08-15T08:10:00Z',
      },
    ]
    vi.spyOn(api, 'getRun').mockResolvedValue(detail)
    vi.spyOn(api, 'listArtifactFiles').mockResolvedValue([{ path: 'final.pt', size: 4096 }])
    const readArtifactFile = vi.spyOn(api, 'readArtifactFile')

    render(
      <ArtifactPreviewWrapper path="/projects/project-1/runs/run-1/artifacts/artifact-2/file?path=final.pt" />,
    )

    expect(await screen.findByRole('heading', { name: '无法在浏览器中预览这个文件' })).toBeVisible()
    expect(screen.getByRole('button', { name: '下载' })).toBeVisible()
    expect(readArtifactFile).not.toHaveBeenCalled()
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
