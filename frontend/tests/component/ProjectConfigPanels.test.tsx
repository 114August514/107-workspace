// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Project, RunConfiguration } from '../../src/api/types'
import { ProjectSecretsPanel } from '../../src/components/project/ProjectSecretsPanel'
import { ProjectVariablesPanel } from '../../src/components/project/ProjectVariablesPanel'
import { RunConfigurationPanel } from '../../src/components/runconfig/RunConfigurationPanel'

/**
 * Issue #54：Project Variable / Secret 管理表面与运行配置引用。
 *
 * 守的是用户可观察行为：
 * - Variable 列表可读，编辑入口由 config.manage 决定；
 * - Secret 只展示名字，写入/轮换走密码框，不回读明文；
 * - 「设为默认运行方案」由 project.update 决定，PATCH 后刷新 Project。
 *
 * 断言用角色和可见文案，不绑定 antd/Primer 私有 DOM。
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

vi.mock('../../src/api/client', () => ({
  api: {
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
  mockListProjectVariables.mockResolvedValue([{ name: 'EPOCHS', value: '5' }])
  mockListProjectSecrets.mockResolvedValue(['HF_TOKEN', 'AWS_KEY'])
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
    render(
      <MemoryRouter>
        <ProjectVariablesPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('EPOCHS')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    // PlusOutlined 的 aria-label 会进 accessible name，所以用正则匹配。
    expect(screen.getByRole('button', { name: /新建 Variable/ })).toBeInTheDocument()
  })

  it('新建 Variable 提交 PUT 并刷新列表', async () => {
    mockPutProjectVariable.mockResolvedValue({ name: 'DATASET_URL', value: 'http://x' })
    render(
      <MemoryRouter>
        <ProjectVariablesPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: /新建 Variable/ }))
    fireEvent.change(await screen.findByLabelText('名称'), { target: { value: 'DATASET_URL' } })
    fireEvent.change(screen.getByLabelText('值'), { target: { value: 'http://x' } })
    fireEvent.click(screen.getByRole('button', { name: '保 存' }))

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

  it('没有 config.manage 时只读，不出现编辑入口', async () => {
    render(
      <MemoryRouter>
        <ProjectVariablesPanel projectId="proj-1" access={viewer} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('EPOCHS')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /新建 Variable/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '编辑' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '删除' })).not.toBeInTheDocument()
  })
})

describe('ProjectSecretsPanel', () => {
  it('列表只展示 Secret 名字，不展示值', async () => {
    render(
      <MemoryRouter>
        <ProjectSecretsPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    expect(await screen.findByText('HF_TOKEN')).toBeInTheDocument()
    expect(screen.getByText('AWS_KEY')).toBeInTheDocument()
  })

  it('新建 Secret 的值输入框是密码框，提交后不回显', async () => {
    mockPutProjectSecret.mockResolvedValue(undefined)
    render(
      <MemoryRouter>
        <ProjectSecretsPanel projectId="proj-1" access={manager} />
      </MemoryRouter>,
    )

    fireEvent.click(await screen.findByRole('button', { name: /新建 Secret/ }))
    const valueInput = screen.getByLabelText('值')
    expect(valueInput).toHaveAttribute('type', 'password')
    fireEvent.change(screen.getByLabelText('名称'), { target: { value: 'HF_TOKEN' } })
    fireEvent.change(valueInput, { target: { value: 'hf_super_secret' } })
    fireEvent.click(screen.getByRole('button', { name: '保 存' }))

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

    const replaceButtons = await screen.findAllByRole('button', { name: /替换值/ })
    fireEvent.click(replaceButtons[0]!)
    const nameInput = await screen.findByLabelText('名称')
    expect(nameInput).toBeDisabled()
    expect(nameInput).toHaveValue('HF_TOKEN')
    expect(screen.getByText('替换 Secret「HF_TOKEN」的值')).toBeInTheDocument()
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
    expect(screen.getByText('CPU 基础')).toBeInTheDocument()
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
