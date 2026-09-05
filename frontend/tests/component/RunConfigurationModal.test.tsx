// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api } from '../../src/api/client'
import type {
  ComputePlan,
  Environment,
  RunConfiguration,
  SharedResource,
  SharedResourceDetail,
} from '../../src/api/types'
import { RunConfigurationModal } from '../../src/components/runconfig/RunConfigurationModal'

const plan: ComputePlan = {
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

const environment: Environment = {
  id: 'env-1',
  name: 'Python',
  description: '',
  owner: { kind: 'user_group', id: 'grp-project', display_name: 'Project 组' },
  versions: [
    {
      id: 'envv-1',
      environment_id: 'env-1',
      version: '3.12',
      description: '',
      runtime_kind: 'modules',
      definition: { modules: ['python/3.12'] },
      definition_hash: 'd'.repeat(64),
      execution_spec: { modules: ['python/3.12'] },
      validation_evidence: { source: 'test' },
      validation_summary: '已验证测试运行环境',
      availability: 'available',
      availability_reason: 'validated',
      availability_detail: '测试环境当前可用',
      availability_checked_at: '2026-08-20T10:00:00Z',
    },
  ],
}

const resource: SharedResource = {
  id: 'shr-1',
  name: '训练数据',
  description: '',
  owner: { kind: 'user_group', id: 'grp-data', display_name: '数据组' },
  created_at: '2026-08-20T10:00:00Z',
  capabilities: ['shared_resource.view'],
  use_qualifications: [
    {
      scope: 'user_grant',
      grantee: { kind: 'user', id: 'usr-student', display_name: 'student' },
      grants: [
        {
          id: 'grant-user-resource',
          target_all: false,
          created_at: '2026-08-20T09:00:00Z',
        },
      ],
    },
  ],
}

const resourceDetail: SharedResourceDetail = {
  ...resource,
  versions: [
    {
      id: 'shrv-2',
      shared_resource_id: resource.id,
      sequence: 2,
      label: 'v2',
      description: '',
      file_count: 2,
      total_size: 20,
      manifest_hash: '2'.repeat(64),
      validation_summary: '已验证 2 个文件',
      created_by: 'alice',
      created_at: '2026-08-20T11:00:00Z',
    },
    {
      id: 'shrv-1',
      shared_resource_id: resource.id,
      sequence: 1,
      label: 'v1',
      description: '',
      file_count: 1,
      total_size: 10,
      manifest_hash: '1'.repeat(64),
      validation_summary: '已验证 1 个文件',
      created_by: 'alice',
      created_at: '2026-08-20T10:00:00Z',
    },
  ],
}

function makeConfiguration(
  inputBindings: RunConfiguration['input_bindings'] = [],
): RunConfiguration {
  return {
    id: 'rc-1',
    project_id: 'prj-1',
    name: '训练方案',
    description: '',
    command: 'python train.py',
    working_directory: '.',
    environment_version_id: 'envv-1',
    environment_variables: {},
    input_bindings: inputBindings,
    compute_plan_id: plan.id,
    compute_request: null,
    artifact_rules: [],
  }
}

function renderModal(editing: RunConfiguration | null = makeConfiguration()) {
  return render(
    <RunConfigurationModal
      open
      projectId="prj-1"
      plans={[plan]}
      environments={[environment]}
      editing={editing}
      onClose={vi.fn()}
      onSaved={vi.fn()}
    />,
  )
}

function expandAdvanced() {
  fireEvent.click(screen.getByText(/^高级设置/))
  const details = screen.getByText(/^高级设置/).parentElement! as HTMLDetailsElement
  details.open = true
  fireEvent(details, new Event('toggle'))
}

describe('Simple Run configuration', () => {
  beforeEach(() => {
    vi.spyOn(api, 'listSharedResources').mockResolvedValue([resource])
    vi.spyOn(api, 'getSharedResource').mockResolvedValue(resourceDetail)
    vi.spyOn(api, 'updateRunConfiguration').mockResolvedValue(makeConfiguration())
    vi.spyOn(api, 'createRunConfiguration').mockResolvedValue(makeConfiguration())
  })
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('saves a minimal command with the sole exact environment and plan, and a visible optional output', async () => {
    renderModal(null)
    expect(screen.getByText(/运行产物 · outputs/)).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /^运行环境/ })).toHaveValue('envv-1')
    expect(screen.getByRole('combobox', { name: /^算力方案/ })).toHaveValue('plan-1')
    expect(screen.getByRole('textbox', { name: '方案名称' })).toBeVisible()
    expect(screen.getByRole('textbox', { name: '说明' })).toBeVisible()
    fireEvent.change(screen.getByRole('textbox', { name: /^执行命令/ }), {
      target: { value: 'python train.py' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    await waitFor(() =>
      expect(api.createRunConfiguration).toHaveBeenCalledWith(
        'prj-1',
        expect.objectContaining({
          command: 'python train.py',
          environment_version_id: 'envv-1',
          compute_plan_id: 'plan-1',
          compute_request: null,
          artifact_rules: [{ path: 'outputs/', name: '', optional: true }],
        }),
      ),
    )
  })

  it('does not restore a deleted output rule when editing', async () => {
    renderModal()
    expect(screen.getByText('运行产物 · 不收集')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    await waitFor(() =>
      expect(api.updateRunConfiguration).toHaveBeenCalledWith(
        'rc-1',
        expect.objectContaining({ artifact_rules: [] }),
      ),
    )
  })

  it('adds a grant-discovered exact resource version in advanced settings', async () => {
    renderModal()
    expandAdvanced()
    const add = await screen.findByRole('button', { name: '添加运行输入' })
    await waitFor(() => expect(add).toBeEnabled())
    fireEvent.click(add)
    fireEvent.change(screen.getByRole('combobox', { name: /^资源版本 1/ }), {
      target: { value: 'shrv-2' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: /^输入访问路径 1/ }), {
      target: { value: '/inputs/train' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: '来源子路径 1' }), {
      target: { value: 'train/' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    await waitFor(() =>
      expect(api.updateRunConfiguration).toHaveBeenCalledWith(
        'rc-1',
        expect.objectContaining({
          input_bindings: [
            {
              source_type: 'shared_resource_version',
              source_id: 'shrv-2',
              access_path: '/inputs/train',
              source_subpath: 'train/',
            },
          ],
        }),
      ),
    )
  })

  it('restores and edits an exact binding without discarding artifact inputs', async () => {
    renderModal(
      makeConfiguration([
        {
          source_type: 'shared_resource_version',
          source_id: 'shrv-1',
          source_subpath: 'train',
          access_path: '/inputs/train',
        },
        {
          source_type: 'artifact',
          source_id: 'art-1',
          source_subpath: '',
          access_path: '/inputs/model',
        },
      ]),
    )
    expandAdvanced()
    await screen.findByRole('option', { name: /训练数据 · v2/ })
    expect(screen.getByRole('combobox', { name: /^资源版本 1/ })).toHaveValue('shrv-1')
    fireEvent.change(screen.getByRole('combobox', { name: /^资源版本 1/ }), {
      target: { value: 'shrv-2' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    await waitFor(() =>
      expect(api.updateRunConfiguration).toHaveBeenCalledWith(
        'rc-1',
        expect.objectContaining({
          input_bindings: [
            expect.objectContaining({ source_id: 'shrv-2' }),
            expect.objectContaining({ source_id: 'art-1' }),
          ],
        }),
      ),
    )
  })

  it('removes a binding and preserves the other configuration fields', async () => {
    renderModal(
      makeConfiguration([
        {
          source_type: 'shared_resource_version',
          source_id: 'shrv-1',
          source_subpath: '',
          access_path: '/inputs/data',
        },
      ]),
    )
    expandAdvanced()
    fireEvent.click(await screen.findByRole('button', { name: '删除运行输入 1' }))
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    await waitFor(() =>
      expect(api.updateRunConfiguration).toHaveBeenCalledWith(
        'rc-1',
        expect.objectContaining({
          name: '训练方案',
          input_bindings: [],
          environment_version_id: 'envv-1',
        }),
      ),
    )
  })

  it('reveals conflicting input paths when saving folded advanced settings', async () => {
    renderModal(
      makeConfiguration([
        {
          source_type: 'shared_resource_version',
          source_id: 'shrv-1',
          source_subpath: '',
          access_path: '/inputs/data',
        },
        {
          source_type: 'shared_resource_version',
          source_id: 'shrv-2',
          source_subpath: '',
          access_path: '/inputs/data/train',
        },
      ]),
    )
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    expect(await screen.findByText('输入访问路径不能重复或互相包含')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /^输入访问路径 1/ })).toBeVisible()
    expect(api.updateRunConfiguration).not.toHaveBeenCalled()
  })

  it('reports server rejection and keeps the edited configuration', async () => {
    vi.mocked(api.updateRunConfiguration).mockRejectedValue(
      new ApiError(404, 'not_found', 'unavailable', ['请选择当前可使用的资源版本'], 'req-81'),
    )
    renderModal()
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    expect(await screen.findByText('无法保存运行方案')).toBeInTheDocument()
    expect(screen.getByText('请求标识：req-81')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: /^执行命令/ })).toHaveValue('python train.py')
  })
  it('deleting the suggested output saves an explicit empty list', async () => {
    renderModal(null)
    fireEvent.change(screen.getByRole('textbox', { name: /^执行命令/ }), {
      target: { value: 'echo ok' },
    })
    const details = screen.getByText(/^运行产物/).parentElement! as HTMLDetailsElement
    details.open = true
    fireEvent(details, new Event('toggle'))
    fireEvent.click(screen.getByRole('button', { name: '删除产物规则 1' }))
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    await waitFor(() =>
      expect(api.createRunConfiguration).toHaveBeenCalledWith(
        'prj-1',
        expect.objectContaining({ artifact_rules: [] }),
      ),
    )
  })

  it('keeps custom resources when folded and rejects values beyond the plan bounds', async () => {
    renderModal()
    const details = screen.getByText(/^调整资源/).parentElement! as HTMLDetailsElement
    details.open = true
    fireEvent(details, new Event('toggle'))
    fireEvent.change(screen.getByRole('spinbutton', { name: 'CPU 核数' }), {
      target: { value: '9' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    expect(await screen.findAllByText('请输入 1 至 8 之间的整数')).not.toHaveLength(0)
    expect(api.updateRunConfiguration).not.toHaveBeenCalled()
    fireEvent.change(screen.getByRole('spinbutton', { name: 'CPU 核数' }), {
      target: { value: '3' },
    })
    details.open = false
    fireEvent(details, new Event('toggle'))
    fireEvent.click(screen.getByRole('button', { name: '保存运行方案' }))
    await waitFor(() =>
      expect(api.updateRunConfiguration).toHaveBeenCalledWith(
        'rc-1',
        expect.objectContaining({ compute_request: expect.objectContaining({ cpus: 3 }) }),
      ),
    )
  })
})
