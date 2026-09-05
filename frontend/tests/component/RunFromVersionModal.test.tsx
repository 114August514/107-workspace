// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, act, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../src/api/client'
import { RunFromVersionModal } from '../../src/components/run/RunFromVersionModal'
import type { PreflightResult, Run, RunConfiguration, RunDraft } from '../../src/api/types'

/**
 * RunFromVersionModal 行为测试。
 *
 * 守的是两个可观察契约：
 * 1. 切换 Run Configuration 时立即清掉旧 Preflight，检查完成前提交按钮禁用——
 *    避免用 config A 的检查结果提交 config B 的 Run。
 * 2. 提交时 RunDraft 中显式携带 project_version_id，绑定用户选择的确定版本。
 */

const mockListRunConfigurations = vi.hoisted(() => vi.fn())
const mockPreflight = vi.hoisted(() => vi.fn())
const mockCreateRun = vi.hoisted(() => vi.fn())

vi.mock('../../src/api/client', async () => ({
  ...(await vi.importActual<typeof import('../../src/api/client')>('../../src/api/client')),
  api: {
    listRunConfigurations: mockListRunConfigurations,
    preflight: mockPreflight,
    createRun: mockCreateRun,
  },
  newIdempotencyKey: () => 'test-key',
}))

function makeConfig(id: string, name: string): RunConfiguration {
  return {
    id,
    name,
    command: 'python train.py',
    working_directory: '.',
    project_id: 'prj-1',
    compute_plan_id: 'cp-1',
    compute_request: null,
    description: '',
    environment_variables: {},
    environment_version_id: 'ev-1',
    artifact_rules: [],
    input_bindings: [],
  }
}

function makePreflight(ok: boolean): PreflightResult {
  return {
    configuration_name: '方案 A',
    command: 'python train.py',
    working_directory: '.',
    artifact_rules: [],
    input_bindings: [],
    project_version_label: 'v1',
    environment_name: 'Python',
    compute_plan_name: 'CPU',
    confirmation_token: ok ? 'confirmed' : null,
    ok,
    problems: ok ? [] : ['缺少 Secret'],
    compute_plan_id: 'cp-1',
    compute_request: null,
    environment_version: {
      id: 'ev-1',
      environment_id: 'env-1',
      version: '3.12',
      description: '',
      runtime_kind: 'modules',
      definition: { modules: ['python3.12/3.12'] },
      definition_hash: 'a'.repeat(64),
      execution_spec: { kind: 'modules', commands: [] },
      validation_summary: 'Validated',
      validation_evidence: {},
      availability: 'available',
      availability_reason: 'validated',
      availability_detail: 'Current',
      availability_checked_at: '2026-08-29T00:00:00Z',
    },
    project_version_id: 'ver-1',
    slurm_projection: null,
    resolved_environment_variables: {},
    secret_references: {},
  }
}

function makeRun(): Run {
  return {
    id: 'run-1',
    name: 'test run',
    status: 'queued',
    project_id: 'prj-1',
    capabilities: ['run.submit'],
    initiated_by_user_id: 'student',
    initiated_by_username: 'student',
    created_at: '2026-08-12T10:00:00Z',
    started_at: null,
    finished_at: null,
    submitted_at: null,
    exit_code: null,
    failure_reason: '',
    scheduler_job_id: null,
    snapshot_id: 'snap-1',
    source_run_id: null,
    source_run_configuration_id: null,
    project_version_id: 'ver-1',
    project_version_label: 'v1',
  }
}

function renderModal(overrides: Partial<Parameters<typeof RunFromVersionModal>[0]> = {}) {
  return render(
    <RunFromVersionModal
      open={true}
      versionId="ver-1"
      versionLabel="v1"
      projectId="prj-1"
      defaultRunConfigurationId="config-a"
      onClose={() => {}}
      onSubmitted={() => {}}
      {...overrides}
    />,
  )
}

describe('Simple Run submission', () => {
  beforeEach(() => {
    mockListRunConfigurations.mockResolvedValue([
      makeConfig('config-a', '方案 A'),
      makeConfig('config-b', '方案 B'),
    ])
    mockPreflight.mockResolvedValue(makePreflight(true))
    mockCreateRun.mockResolvedValue(makeRun())
  })
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })
  const ready = () =>
    waitFor(() => expect(screen.getByRole('button', { name: '提交 Run' })).toBeEnabled())
  const chooseB = () => {
    fireEvent.click(screen.getByRole('button', { name: '更换' }))
    fireEvent.change(screen.getByRole('combobox', { name: '运行方案' }), {
      target: { value: 'config-b' },
    })
  }

  it('pins the exact project version and backend confirmation when creating a Run', async () => {
    const onSubmitted = vi.fn()
    renderModal({ onSubmitted })
    await ready()
    fireEvent.click(screen.getByRole('button', { name: '提交 Run' }))
    await waitFor(() =>
      expect(mockCreateRun).toHaveBeenCalledWith(
        'prj-1',
        expect.objectContaining({
          run_configuration_id: 'config-a',
          project_version_id: 'ver-1',
          confirmation_token: 'confirmed',
        }),
        'test-key',
      ),
    )
    expect(onSubmitted).toHaveBeenCalledOnce()
  })
  it('clears the old preview while a different configuration is being checked', async () => {
    let finish!: (p: PreflightResult) => void
    const pending = new Promise<PreflightResult>((resolve) => {
      finish = resolve
    })
    mockPreflight.mockImplementation((_id: string, draft: RunDraft) =>
      draft.run_configuration_id === 'config-b' ? pending : Promise.resolve(makePreflight(true)),
    )
    renderModal()
    await ready()
    chooseB()
    expect(screen.getByRole('button', { name: '提交 Run' })).toBeDisabled()
    await act(async () => {
      finish(makePreflight(true))
      await pending
    })
    await ready()
  })
  it('ignores an old response arriving after the current preview', async () => {
    let finish!: (p: PreflightResult) => void
    const pending = new Promise<PreflightResult>((resolve) => {
      finish = resolve
    })
    mockPreflight.mockImplementation((_id: string, draft: RunDraft) =>
      draft.run_configuration_id === 'config-a' ? pending : Promise.resolve(makePreflight(true)),
    )
    renderModal()
    await screen.findByRole('button', { name: '更换' })
    chooseB()
    await ready()
    await act(async () => {
      finish(makePreflight(false))
      await pending
    })
    expect(screen.queryByText('缺少 Secret')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '提交 Run' })).toBeEnabled()
  })
  it('uses the project default configuration', async () => {
    renderModal({ defaultRunConfigurationId: 'config-b' })
    await ready()
    fireEvent.click(screen.getByRole('button', { name: '提交 Run' }))
    await waitFor(() =>
      expect(mockCreateRun).toHaveBeenCalledWith(
        'prj-1',
        expect.objectContaining({ run_configuration_id: 'config-b' }),
        'test-key',
      ),
    )
  })
  it('shows exact inputs returned by the backend inside configuration details', async () => {
    const preview = makePreflight(true)
    preview.input_bindings = [
      {
        source_type: 'shared_resource_version',
        source_id: 'shrv-2',
        source_subpath: 'train',
        access_path: '/inputs/train',
      },
    ]
    mockPreflight.mockResolvedValue(preview)
    renderModal()
    await ready()
    const summary = screen.getByText('配置详情')
    fireEvent.click(summary)
    const details = summary.parentElement! as HTMLDetailsElement
    details.open = true
    expect(within(details).getByText('shrv-2/train')).toBeVisible()
    expect(within(details).getByText('/inputs/train')).toBeVisible()
  })
  it('does not allow repeated clicks during creation', async () => {
    mockCreateRun.mockReturnValue(new Promise(() => {}))
    renderModal()
    await ready()
    const button = screen.getByRole('button', { name: '提交 Run' })
    fireEvent.click(button)
    fireEvent.click(button)
    expect(mockCreateRun).toHaveBeenCalledOnce()
  })
  it('requires a refreshed preview after the backend detects changed execution facts', async () => {
    mockCreateRun.mockRejectedValueOnce(
      new ApiError(409, 'run_confirmation_changed', 'changed', [], 'req-81'),
    )
    renderModal()
    await ready()
    fireEvent.click(screen.getByRole('button', { name: '提交 Run' }))
    expect(await screen.findByText('运行配置已变化')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '提交 Run' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '刷新摘要' }))
    await ready()
  })

  it('reuses the same confirmed intent after a network failure', async () => {
    mockCreateRun.mockRejectedValueOnce(new Error('network'))
    renderModal()
    await ready()
    fireEvent.click(screen.getByRole('button', { name: '提交 Run' }))
    expect(await screen.findByText('无法提交 Run')).toBeInTheDocument()
    await ready()
    fireEvent.click(screen.getByRole('button', { name: '提交 Run' }))
    await waitFor(() => expect(mockCreateRun).toHaveBeenCalledTimes(2))
    expect(mockCreateRun.mock.calls[0]).toEqual(mockCreateRun.mock.calls[1])
  })
})
