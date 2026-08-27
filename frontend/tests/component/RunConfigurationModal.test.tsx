// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
      image: 'python:3.12',
      setup_command: '',
      available: true,
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

async function chooseSelect(label: string, option: string | RegExp) {
  const select = within(screen.getByRole('dialog')).getByRole('combobox', { name: label })
  fireEvent.mouseDown(select)
  fireEvent.click(await screen.findByText(option))
}

describe('RunConfigurationModal 运行输入', () => {
  beforeEach(() => {
    vi.spyOn(api, 'listSharedResources').mockResolvedValue([resource])
    vi.spyOn(api, 'getSharedResource').mockResolvedValue(resourceDetail)
    vi.spyOn(api, 'updateRunConfiguration').mockResolvedValue(makeConfiguration())
  })

  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-44 添加确定资源版本、来源子路径和输入访问路径', async () => {
    renderModal()

    const dialog = within(screen.getByRole('dialog'))
    const addButton = await dialog.findByRole('button', { name: /添加运行输入/ })
    await waitFor(() => expect(addButton).toBeEnabled())
    fireEvent.click(addButton)
    await chooseSelect('共享资源', /训练数据/)
    await chooseSelect('资源版本', /v2/)
    fireEvent.change(dialog.getByPlaceholderText('例如：train/'), {
      target: { value: 'train/' },
    })
    fireEvent.change(dialog.getByPlaceholderText('/inputs/train'), {
      target: { value: '/inputs/train' },
    })

    fireEvent.click(dialog.getByRole('button', { name: /保\s*存/ }))

    await waitFor(() => {
      expect(api.updateRunConfiguration).toHaveBeenCalledWith(
        'rc-1',
        expect.objectContaining({
          input_bindings: [
            {
              source_type: 'shared_resource_version',
              source_id: 'shrv-2',
              source_subpath: 'train/',
              access_path: '/inputs/train',
            },
          ],
        }),
      )
    })
  })

  it('REQ-44 重新打开后还原绑定并可更换 exact Version', async () => {
    renderModal(
      makeConfiguration([
        {
          source_type: 'shared_resource_version',
          source_id: 'shrv-1',
          source_subpath: 'train',
          access_path: '/inputs/train',
        },
      ]),
    )

    const dialog = within(screen.getByRole('dialog'))
    expect(await dialog.findByDisplayValue('train')).toBeInTheDocument()
    expect(dialog.getByDisplayValue('/inputs/train')).toBeInTheDocument()
    expect(dialog.getByText(/训练数据/)).toBeInTheDocument()
    expect(dialog.getByText(/v1/)).toBeInTheDocument()

    await chooseSelect('资源版本', /v2/)
    fireEvent.change(dialog.getByRole('textbox', { name: '输入访问路径' }), {
      target: { value: '/inputs/training' },
    })
    fireEvent.click(dialog.getByRole('button', { name: /保\s*存/ }))

    await waitFor(() => {
      expect(api.updateRunConfiguration).toHaveBeenCalledWith(
        'rc-1',
        expect.objectContaining({
          input_bindings: [
            expect.objectContaining({ source_id: 'shrv-2', access_path: '/inputs/training' }),
          ],
        }),
      )
    })
  })

  it('REQ-44 可解除 Shared Resource 绑定且不触碰其他配置字段', async () => {
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

    const dialog = within(screen.getByRole('dialog'))
    fireEvent.click(await dialog.findByRole('button', { name: '删除运行输入 1' }))
    fireEvent.click(dialog.getByRole('button', { name: /保\s*存/ }))

    await waitFor(() => {
      expect(api.updateRunConfiguration).toHaveBeenCalledWith(
        'rc-1',
        expect.objectContaining({
          name: '训练方案',
          environment_version_id: 'envv-1',
          input_bindings: [],
        }),
      )
    })
  })

  it('REQ-44 冲突的输入访问路径不能提交', async () => {
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

    const dialog = within(screen.getByRole('dialog'))
    await waitFor(() => expect(dialog.getAllByText(/训练数据/)).toHaveLength(2))
    fireEvent.click(dialog.getByRole('button', { name: /保\s*存/ }))

    expect((await dialog.findAllByText('输入访问路径不能重复或互相包含')).length).toBeGreaterThan(0)
    expect(api.updateRunConfiguration).not.toHaveBeenCalled()
  })

  it('REQ-44 服务端授权或可用性失败时展示问题和请求标识', async () => {
    vi.mocked(api.updateRunConfiguration).mockRejectedValue(
      new ApiError(
        404,
        'not_found',
        '资源版本不存在或当前没有 USE 资格',
        ['请选择当前可使用的资源版本'],
        'req-44',
      ),
    )
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

    const dialog = within(screen.getByRole('dialog'))
    await dialog.findByText(/训练数据/)
    fireEvent.click(dialog.getByRole('button', { name: /保\s*存/ }))

    expect(await dialog.findByText('无法保存运行方案')).toBeInTheDocument()
    expect(dialog.getByText('请选择当前可使用的资源版本')).toBeInTheDocument()
    expect(dialog.getByText('请求标识：req-44')).toBeInTheDocument()
  })
})
