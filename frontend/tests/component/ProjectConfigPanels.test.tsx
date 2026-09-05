// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Project, RunConfiguration } from '../../src/api/types'
import { ProjectSecretsPanel } from '../../src/components/project/ProjectSecretsPanel'
import { ProjectSettingsPanel } from '../../src/components/project/ProjectSettingsPanel'
import { ProjectVariablesPanel } from '../../src/components/project/ProjectVariablesPanel'
import { RunConfigurationPanel } from '../../src/components/runconfig/RunConfigurationPanel'

/**
 * Issue #54：Project Variable / Secret 管理表面与运行配置引用。
 *
 * 守的是用户可观察行为：
 * - Variable 列表可读，编辑入口由 config.manage 决定；
 * - Secret 只展示名字，写入/轮换走密码框，不回读明文；
 * - 删除走确认弹窗；「设为默认运行方案」由 project.update 决定。
 *
 * 断言用角色和可见文案，不绑定 Primer 私有 DOM；
 * <relative-time> 在 jsdom 不产出文本，只断言 datetime 属性。
 */

const mockListProjectVariables = vi.hoisted(() => vi.fn())
const mockPutProjectVariable = vi.hoisted(() => vi.fn())
const mockDeleteProjectVariable = vi.hoisted(() => vi.fn())
const mockListProjectSecrets = vi.hoisted(() => vi.fn())
const mockPutProjectSecret = vi.hoisted(() => vi.fn())
const mockDeleteProjectSecret = vi.hoisted(() => vi.fn())
const mockListRunConfigurations = vi.hoisted(() => vi.fn())
const mockComputePlans = vi.hoisted(() => vi.fn())
const mockEnvironmentsForProject = vi.hoisted(() => vi.fn())
const mockUpdateProject = vi.hoisted(() => vi.fn())

vi.mock('../../src/api/client', async () => ({
  ...(await vi.importActual<typeof import('../../src/api/client')>('../../src/api/client')),
  api: {
    listEntitlements: vi.fn().mockResolvedValue([]),
    listProjectVariables: mockListProjectVariables,
    putProjectVariable: mockPutProjectVariable,
    deleteProjectVariable: mockDeleteProjectVariable,
    listProjectSecrets: mockListProjectSecrets,
    putProjectSecret: mockPutProjectSecret,
    deleteProjectSecret: mockDeleteProjectSecret,
    listRunConfigurations: mockListRunConfigurations,
    computePlans: mockComputePlans,
    environmentsForProject: mockEnvironmentsForProject,
    updateProject: mockUpdateProject,
  },
}))

function makeProject(capabilities: string[]): Project {
  return {
    id: 'proj-1',
    name: '测试项目',
    description: '',
    owner: { kind: 'user', id: 'user-1', display_name: 'Alice' },
    status: 'active',
    visibility: 'owner_scope',
    environment_version_id: null,
    default_run_configuration_id: null,
    created_by: 'user-1',
    created_at: '2026-09-01T10:00:00Z',
    updated_at: '2026-09-01T10:00:00Z',
    capabilities: capabilities as Project['capabilities'],
  }
}

const manager = makeProject(['project.view', 'config.view', 'config.manage'])
const viewer = makeProject(['project.view', 'config.view'])

beforeEach(() => {
  mockListProjectVariables.mockResolvedValue([
    { name: 'EPOCHS', value: '5', updated_at: '2026-09-01T10:00:00Z' },
  ])
  mockListProjectSecrets.mockResolvedValue([
    { name: 'HF_TOKEN', updated_at: '2026-09-01T10:00:00Z' },
    { name: 'AWS_KEY', updated_at: '2026-08-20T10:00:00Z' },
  ])
  mockListRunConfigurations.mockResolvedValue([])
  mockComputePlans.mockResolvedValue([])
  mockEnvironmentsForProject.mockResolvedValue([])
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('ProjectVariablesPanel', () => {
  it('列出 Variable 与值，config.manage 用户可以新建', async () => {
    const { container } = render(
      <MemoryRouter>
        <ProjectVariablesPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('EPOCHS')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /新建 Variable/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '复制 EPOCHS 的值' })).toBeInTheDocument()
    const time = container.querySelector('relative-time')
    expect(time).not.toBeNull()
    expect(time!.getAttribute('datetime')).toMatch(/^2026-09-01T10:00:00/)
  })

  it('新建 Variable 提交 PUT 并刷新列表', async () => {
    mockPutProjectVariable.mockResolvedValue({
      name: 'DATASET_URL',
      value: 'http://x',
      updated_at: '2026-09-02T10:00:00Z',
    })
    render(
      <MemoryRouter>
        <ProjectVariablesPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: /新建 Variable/ }))
    fireEvent.change(await screen.findByLabelText(/^名称/), { target: { value: 'DATASET_URL' } })
    fireEvent.change(screen.getByLabelText(/^值/), { target: { value: 'http://x' } })
    fireEvent.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => {
      expect(mockPutProjectVariable).toHaveBeenCalledWith('proj-1', {
        name: 'DATASET_URL',
        value: 'http://x',
      })
    })
    await waitFor(() => {
      expect(mockListProjectVariables).toHaveBeenCalledTimes(2)
    })
  })

  it('名称不合法时提交前拦截', async () => {
    render(
      <MemoryRouter>
        <ProjectVariablesPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: /新建 Variable/ }))
    fireEvent.change(await screen.findByLabelText(/^名称/), { target: { value: '1ABC' } })
    fireEvent.change(screen.getByLabelText(/^值/), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: '保存' }))

    expect(
      await screen.findByText('只能包含字母、数字和下划线，且不能以数字开头'),
    ).toBeInTheDocument()
    expect(mockPutProjectVariable).not.toHaveBeenCalled()
  })

  it('删除 Variable 先确认再调 DELETE', async () => {
    mockDeleteProjectVariable.mockResolvedValue(undefined)
    render(
      <MemoryRouter>
        <ProjectVariablesPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: '删除 EPOCHS' }))
    expect(await screen.findByText('删除 Variable「EPOCHS」？')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '删除' }))

    await waitFor(() => {
      expect(mockDeleteProjectVariable).toHaveBeenCalledWith('proj-1', 'EPOCHS')
    })
  })

  it('列表为空时展示引导文案', async () => {
    mockListProjectVariables.mockResolvedValue([])
    render(
      <MemoryRouter>
        <ProjectVariablesPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    expect(
      await screen.findByText('还没有 Project Variable。创建后可以在运行方案环境变量中引用。'),
    ).toBeInTheDocument()
  })

  it('没有 config.manage 时只读，不出现编辑入口', async () => {
    // 断言收敛到容器内：前一个用例的 ConfirmationDialog portal 可能还挂在 body 上。
    const { container } = render(
      <MemoryRouter>
        <ProjectVariablesPanel projectId="proj-1" access={viewer} />
      </MemoryRouter>,
    )

    expect(await within(container).findByText('EPOCHS')).toBeInTheDocument()
    expect(
      within(container).queryByRole('button', { name: /新建 Variable/ }),
    ).not.toBeInTheDocument()
    expect(within(container).queryByRole('button', { name: /编辑/ })).not.toBeInTheDocument()
    expect(within(container).queryByRole('button', { name: /删除/ })).not.toBeInTheDocument()
  })
})

describe('ProjectSecretsPanel', () => {
  it('列表只展示 Secret 名字与更新时间，不展示值', async () => {
    const { container } = render(
      <MemoryRouter>
        <ProjectSecretsPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('HF_TOKEN')).toBeInTheDocument()
    expect(screen.getByText('AWS_KEY')).toBeInTheDocument()
    const time = container.querySelector('relative-time')
    expect(time).not.toBeNull()
    expect(time!.getAttribute('datetime')).toMatch(/^2026-09-01T10:00:00/)
  })

  it('新建 Secret 的值输入框是密码框，提交后不回显', async () => {
    mockPutProjectSecret.mockResolvedValue(undefined)
    render(
      <MemoryRouter>
        <ProjectSecretsPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: /新建 Secret/ }))
    const valueInput = screen.getByLabelText(/^值/)
    expect(valueInput).toHaveAttribute('type', 'password')
    fireEvent.change(screen.getByLabelText(/^名称/), { target: { value: 'HF_TOKEN' } })
    fireEvent.change(valueInput, { target: { value: 'hf_super_secret' } })
    fireEvent.click(screen.getByRole('button', { name: '保存' }))

    await waitFor(() => {
      expect(mockPutProjectSecret).toHaveBeenCalledWith('proj-1', {
        name: 'HF_TOKEN',
        value: 'hf_super_secret',
      })
    })
  })

  it('替换值只允许改值，名字锁定', async () => {
    mockPutProjectSecret.mockResolvedValue(undefined)
    render(
      <MemoryRouter>
        <ProjectSecretsPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: '替换 HF_TOKEN 的值' }))
    const nameInput = await screen.findByLabelText(/^名称/)
    expect(nameInput).toBeDisabled()
    expect(nameInput).toHaveValue('HF_TOKEN')
    expect(screen.getByText('替换 Secret「HF_TOKEN」的值')).toBeInTheDocument()
    expect(screen.getByLabelText(/^新值/)).toHaveAttribute('type', 'password')
  })

  it('删除 Secret 先确认再调 DELETE', async () => {
    mockDeleteProjectSecret.mockResolvedValue(undefined)
    render(
      <MemoryRouter>
        <ProjectSecretsPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: '删除 HF_TOKEN' }))
    expect(await screen.findByText('删除 Secret「HF_TOKEN」？')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '删除' }))

    await waitFor(() => {
      expect(mockDeleteProjectSecret).toHaveBeenCalledWith('proj-1', 'HF_TOKEN')
    })
  })
})

describe('ProjectSettingsPanel', () => {
  it('SegmentedControl 在 Variables 和 Secrets 分区之间切换', async () => {
    render(
      <MemoryRouter>
        <ProjectSettingsPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('EPOCHS')).toBeInTheDocument()
    expect(screen.queryByText('HF_TOKEN')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Secrets' }))
    expect(await screen.findByText('HF_TOKEN')).toBeInTheDocument()
    expect(screen.queryByText('EPOCHS')).not.toBeInTheDocument()
  })
})

describe('RunConfigurationPanel 默认运行方案', () => {
  const configuration: RunConfiguration = {
    id: 'cfg-1',
    project_id: 'proj-1',
    name: '训练方案',
    description: '',
    working_directory: '.',
    command: 'python train.py',
    environment_version_id: 'envv-1',
    environment_variables: { EPOCHS: '${{ vars.EPOCHS }}' },
    input_bindings: [],
    compute_plan_id: 'plan-1',
    compute_request: null,
    artifact_rules: [],
  }

  it('project.update 用户可以设为默认并触发刷新', async () => {
    mockComputePlans.mockResolvedValue([
      {
        id: 'plan-1',
        code: 'cpu-basic',
        name: 'CPU 基础',
        description: '',
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
    mockListRunConfigurations.mockResolvedValue([configuration])
    mockUpdateProject.mockResolvedValue({ ...manager, default_run_configuration_id: 'cfg-1' })
    const onChanged = vi.fn()

    render(
      <MemoryRouter>
        <RunConfigurationPanel
          projectId="proj-1"
          access={makeProject(['project.view', 'project.update'])}
          defaultConfigurationId={null}
          onSubmitRun={vi.fn()}
          onChanged={onChanged}
        />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: '设为默认' }))
    await waitFor(() => {
      expect(mockUpdateProject).toHaveBeenCalledWith('proj-1', {
        default_run_configuration_id: 'cfg-1',
      })
    })
    expect(onChanged).toHaveBeenCalled()
    // 算力方案列展示计划名而不是裸 id。
    expect(screen.getByText(/CPU 基础/)).toBeInTheDocument()
  })

  it('没有 project.update 时不出现默认方案操作', async () => {
    mockListRunConfigurations.mockResolvedValue([configuration])
    render(
      <MemoryRouter>
        <RunConfigurationPanel
          projectId="proj-1"
          access={makeProject(['project.view'])}
          defaultConfigurationId={null}
          onSubmitRun={vi.fn()}
          onChanged={vi.fn()}
        />
      </MemoryRouter>,
    )

    expect(await screen.findByText('训练方案')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '设为默认' })).not.toBeInTheDocument()
  })
})
