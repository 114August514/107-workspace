// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RunFromVersionModal } from '../../src/components/run/RunFromVersionModal'
import type {
  PreflightResult,
  Run,
  RunConfiguration,
  LegacyWorkspaceContext,
} from '../../src/api/types'

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

vi.mock('../../src/api/client', () => ({
  api: {
    listRunConfigurations: mockListRunConfigurations,
    preflight: mockPreflight,
    createRun: mockCreateRun,
  },
  ApiError: class ApiError extends Error {
    problems: string[] = []
    detail = ''
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
    environment_version_id: null,
    artifact_rules: [],
    input_bindings: [],
  }
}

function makePreflight(ok: boolean): PreflightResult {
  return {
    ok,
    problems: ok ? [] : ['缺少 Secret'],
    compute_plan_id: 'cp-1',
    compute_request: null,
    environment_version_id: null,
    project_version_id: 'ver-1',
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
    workspace_id: 'ws-1',
    created_by: 'student',
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

const workspace: LegacyWorkspaceContext = {
  id: 'ws-1',
  name: 'Test Workspace',
  kind: 'collaborative',
  owner_id: 'owner',
  default_environment_version_id: null,
  capabilities: [
    'user_group.view',
    'project.view',
    'run.view',
    'run.submit',
  ] as LegacyWorkspaceContext['capabilities'],
  role: 'member',
}

function renderModal(overrides: Partial<Parameters<typeof RunFromVersionModal>[0]> = {}) {
  return render(
    <RunFromVersionModal
      open={true}
      versionId="ver-1"
      versionLabel="v1"
      projectId="prj-1"
      defaultRunConfigurationId={null}
      workspace={workspace}
      onClose={() => {}}
      onSubmitted={() => {}}
      {...overrides}
    />,
  )
}

describe('RunFromVersionModal', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  beforeEach(() => {
    vi.useRealTimers()
  })

  it('切换 Run Configuration 后清掉旧 Preflight，检查完成前提交按钮禁用', async () => {
    // 两个 configuration：A（preflight ok）和 B（preflight 尚未完成）
    mockListRunConfigurations.mockResolvedValue([
      makeConfig('config-a', '方案 A'),
      makeConfig('config-b', '方案 B'),
    ])

    // A 的 preflight 立即返回 ok=true
    // B 的 preflight 用 pending Promise 延迟，模拟检查进行中
    let resolveBPreflight!: (value: PreflightResult) => void
    const bPreflightPromise = new Promise<PreflightResult>((resolve) => {
      resolveBPreflight = resolve
    })

    mockPreflight
      .mockResolvedValueOnce(makePreflight(true)) // config A
      .mockReturnValueOnce(bPreflightPromise) // config B（pending）

    renderModal()

    // 等待 configs 加载、A 被默认选中、A 的 preflight 完成
    await waitFor(() => {
      expect(screen.getByText('提交前检查通过')).toBeInTheDocument()
    })

    // 提交按钮此时应该可用（A 的 preflight ok）
    // antd 对双字符中文标签会插入间距：「提 交」
    const submitButton = screen.getByRole('button', { name: /提\s*交/ })
    expect(submitButton).not.toBeDisabled()

    // 切换到方案 B：antd Select 用 mouseDown 打开下拉
    const configSelect = screen.getByRole('combobox', { name: '运行方案' })
    fireEvent.mouseDown(configSelect)

    // 等待下拉选项出现并点击「方案 B」
    const optionB = await waitFor(() => screen.getByText('方案 B'))
    fireEvent.click(optionB)

    // 切换后 A 的「提交前检查通过」提示应该消失
    await waitFor(() => {
      expect(screen.queryByText('提交前检查通过')).not.toBeInTheDocument()
    })

    // 提交按钮应该被禁用（B 的 preflight 还在检查中）
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /提\s*交/ })).toBeDisabled()
    })

    // B 的 preflight 完成（ok=true）
    await act(async () => {
      resolveBPreflight(makePreflight(true))
      await bPreflightPromise
    })

    // 现在提交按钮应该可用
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /提\s*交/ })).not.toBeDisabled()
    })
  })

  it('旧 Preflight 慢返回不能覆盖新 Preflight 的结果（乱序竞态）', async () => {
    // 两个 configuration：A（slow，最后才返回）和 B（fast，先返回）
    mockListRunConfigurations.mockResolvedValue([
      makeConfig('config-a', '方案 A'),
      makeConfig('config-b', '方案 B'),
    ])

    let resolveAPreflight!: (value: PreflightResult) => void
    const aPreflightPromise = new Promise<PreflightResult>((resolve) => {
      resolveAPreflight = resolve
    })

    // A 先发请求但 pending；B 随后请求并立即返回 ok
    mockPreflight
      .mockReturnValueOnce(aPreflightPromise) // config A（slow，pending）
      .mockResolvedValueOnce(makePreflight(true)) // config B（fast，ok）

    renderModal()

    // 等 configs 加载，A 被默认选中并触发 preflight（pending 中）
    await waitFor(() => {
      expect(mockPreflight).toHaveBeenCalledTimes(1)
    })
    // 提交按钮禁用（A 还在检查中）
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /提\s*交/ })).toBeDisabled()
    })

    // 切到方案 B（fast）：B 的 preflight 立即 ok，页面显示 B 的「提交前检查通过」
    const configSelect = screen.getByRole('combobox', { name: '运行方案' })
    fireEvent.mouseDown(configSelect)
    const optionB = await waitFor(() => screen.getByText('方案 B'))
    fireEvent.click(optionB)

    await waitFor(() => {
      expect(screen.getByText('提交前检查通过')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /提\s*交/ })).not.toBeDisabled()

    // 现在 A 的旧请求才 resolve（是 preflight(false)，如果覆盖 B 会引起错误提示）
    await act(async () => {
      resolveAPreflight(makePreflight(false))
      await aPreflightPromise
    })

    // 关键断言：B 的结果不能被 A 覆盖
    // 页面仍显示 B 的「提交前检查通过」，而不是 A 的失败提示
    await waitFor(() => {
      expect(screen.getByText('提交前检查通过')).toBeInTheDocument()
    })
    expect(screen.queryByText('缺少 Secret')).not.toBeInTheDocument()
    // 提交状态仍由 B 决定（可用）
    expect(screen.getByRole('button', { name: /提\s*交/ })).not.toBeDisabled()
  })

  it('提交时 RunDraft 携带 project_version_id', async () => {
    mockListRunConfigurations.mockResolvedValue([makeConfig('config-a', '方案 A')])
    mockPreflight.mockResolvedValue(makePreflight(true))
    mockCreateRun.mockResolvedValue(makeRun())

    const onSubmitted = vi.fn()
    renderModal({ onSubmitted })

    // 等待 preflight 通过
    await waitFor(() => {
      expect(screen.getByText('提交前检查通过')).toBeInTheDocument()
    })

    // 点击提交
    fireEvent.click(screen.getByRole('button', { name: /提\s*交/ }))

    // 验证 createRun 被调用时携带了 project_version_id
    await waitFor(() => {
      expect(mockCreateRun).toHaveBeenCalledWith(
        'prj-1',
        expect.objectContaining({
          run_configuration_id: 'config-a',
          project_version_id: 'ver-1',
        }),
        'test-key',
      )
    })

    expect(onSubmitted).toHaveBeenCalledTimes(1)
  })

  it('优先选中 defaultRunConfigurationId 指定的运行方案', async () => {
    // 两个 configuration，defaultRunConfigurationId 指向 config-b
    mockListRunConfigurations.mockResolvedValue([
      makeConfig('config-a', '方案 A'),
      makeConfig('config-b', '方案 B'),
    ])
    mockPreflight.mockResolvedValue(makePreflight(true))
    mockCreateRun.mockResolvedValue(makeRun())

    renderModal({ defaultRunConfigurationId: 'config-b' })

    // 等待 preflight 通过（说明 config-b 被选中并触发了 preflight）
    await waitFor(() => {
      expect(screen.getByText('提交前检查通过')).toBeInTheDocument()
    })

    // 提交后验证用的是 config-b 而非列表第一个 config-a
    fireEvent.click(screen.getByRole('button', { name: /提\s*交/ }))

    await waitFor(() => {
      expect(mockCreateRun).toHaveBeenCalledWith(
        'prj-1',
        expect.objectContaining({
          run_configuration_id: 'config-b',
        }),
        'test-key',
      )
    })
  })
})
