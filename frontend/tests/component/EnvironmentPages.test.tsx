// @vitest-environment jsdom

import type { ReactNode } from 'react'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { Environment, EnvironmentPublicationAttempt } from '../../src/api/types'
import { EnvironmentListPage } from '../../src/pages/EnvironmentListPage'
import { EnvironmentPage } from '../../src/pages/EnvironmentPage'
import { EnvironmentVersionPage } from '../../src/pages/EnvironmentVersionPage'
import { EnvironmentProvider } from '../../src/components/environment/EnvironmentHeader'
import { PrimerRoot } from '../../src/primer/setup'

const runtimeFields = {
  runtime_kind: 'modules' as const,
  definition: { modules: ['cuda/12.6'] },
  definition_hash: 'a'.repeat(64),
  execution_spec: { kind: 'modules', commands: [] },
  validation_summary: 'Validated modules',
  validation_evidence: { validator: 'modules_allowlist_v1' },
  availability: 'available' as const,
  availability_reason: 'validated',
  availability_detail: 'Current platform evidence',
  availability_checked_at: '2026-08-29T00:00:00Z',
}

const environment: Environment = {
  capabilities: ['environment.version.create'],
  id: 'env_cuda',
  name: 'CUDA Research',
  description: 'GPU training base',
  owner: { kind: 'user_group', id: 'grp_gpu', display_name: 'GPU Lab' },
  versions: [
    {
      id: 'envv_cuda_124',
      environment_id: 'env_cuda',
      version: '12.4',
      description: 'Stable CUDA toolchain',
      ...runtimeFields,
    },
    {
      id: 'envv_cuda_125',
      environment_id: 'env_cuda',
      version: '12.5',
      description: 'Retired image',
      ...runtimeFields,
      availability: 'unavailable',
    },
  ],
}

function renderRoute(entry: string, path: string, element: ReactNode) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <PrimerRoot>
        <EnvironmentProvider>
          <Routes>
            <Route path={path} element={element} />
          </Routes>
        </EnvironmentProvider>
      </PrimerRoot>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.spyOn(api, 'environmentPublicationOptions').mockResolvedValue({
    modules: ['cuda/12.6'],
    architecture: 'x86_64',
    max_upload_bytes: 1024,
    max_import_bytes: 4096,
    import_timeout_seconds: 900,
  })
  vi.spyOn(api, 'environments').mockResolvedValue([environment])
  vi.spyOn(api, 'environment').mockResolvedValue(environment)
  vi.spyOn(api, 'environmentVersion').mockResolvedValue(environment.versions[0]!)
  vi.spyOn(api, 'environmentPublicationAttempts').mockResolvedValue([])
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('Environment Core surfaces', () => {
  it('lists backend-authorized environments with owner and version availability', async () => {
    renderRoute('/environments', '/environments', <EnvironmentListPage />)

    expect(await screen.findByRole('heading', { name: '运行环境' })).toBeVisible()
    const environmentLink = screen.getByRole('link', { name: /CUDA Research/ })
    expect(environmentLink).toHaveAttribute('href', '/environments/env_cuda')
    expect(environmentLink).toHaveTextContent('GPU Lab')
    expect(environmentLink).toHaveTextContent('1/2 个版本可用')
  })

  it('shows an actionable empty state instead of inventing platform environments', async () => {
    vi.mocked(api.environments).mockResolvedValue([])
    renderRoute('/environments', '/environments', <EnvironmentListPage />)

    expect(await screen.findByText('当前没有可使用的运行环境。')).toBeVisible()
    expect(screen.getByText(/建立 USE Grant/)).toBeVisible()
  })

  it('shows owner, every exact version and current availability on detail', async () => {
    renderRoute('/environments/env_cuda', '/environments/:environmentId', <EnvironmentPage />)

    expect(await screen.findByRole('heading', { name: 'CUDA Research' })).toBeVisible()
    expect(screen.getByText('GPU Lab')).toBeVisible()
    expect(screen.getByRole('link', { name: /12.4/ })).toHaveAttribute(
      'href',
      '/environment-versions/envv_cuda_124',
    )
    expect(screen.getByRole('link', { name: /12.5/ })).toHaveTextContent('不可用')
  })

  it('publishes ordered modules and shows the persisted history', async () => {
    const attempt = makeAttempt()
    const publish = vi.spyOn(api, 'publishModulesEnvironment').mockImplementation(async () => {
      vi.mocked(api.environmentPublicationAttempts).mockResolvedValue([attempt])
      return attempt
    })
    renderRoute('/environments/env_cuda', '/environments/:environmentId', <EnvironmentPage />)
    fireEvent.click(await screen.findByRole('button', { name: '发布版本' }))
    const dialog = within(screen.getByRole('dialog'))
    fireEvent.change(await dialog.findByLabelText(/版本名称/), { target: { value: 'new-modules' } })
    fireEvent.change(dialog.getByLabelText('说明'), { target: { value: 'For training' } })
    fireEvent.change(dialog.getByLabelText(/加载模块/), {
      target: { value: 'cuda/12.6\npython3.12/3.12' },
    })
    fireEvent.click(dialog.getByRole('button', { name: '发布版本' }))
    expect(await screen.findByText('等待处理')).toBeVisible()
    expect(publish).toHaveBeenCalledWith('env_cuda', {
      version: 'new-modules',
      description: 'For training',
      modules: ['cuda/12.6', 'python3.12/3.12'],
    })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('retries failed remote imports with source and description, retaining input on submission errors', async () => {
    vi.mocked(api.environmentPublicationAttempts).mockResolvedValue([
      makeAttempt({
        status: 'failed',
        runtime_kind: 'apptainer_sif',
        source_kind: 'import',
        expected_sha256: 'b'.repeat(64),
        source_uri: 'docker://alpine:3.22',
        description: 'Small base',
        failure_reason: '拉取失败',
      }),
    ])
    const publish = vi.spyOn(api, 'importEnvironment').mockRejectedValue(new Error('offline'))
    renderRoute(
      '/environments/env_cuda?tab=history',
      '/environments/:environmentId',
      <EnvironmentPage />,
    )
    fireEvent.click(await screen.findByRole('button', { name: '重新发布' }))
    const dialog = within(screen.getByRole('dialog'))
    expect(await dialog.findByLabelText(/镜像地址/)).toHaveValue('docker://alpine:3.22')
    expect(dialog.getByLabelText('说明')).toHaveValue('Small base')
    fireEvent.click(dialog.getByRole('button', { name: '发布版本' }))
    expect(await dialog.findByText('offline')).toBeVisible()
    expect(dialog.getByLabelText(/镜像地址/)).toHaveValue('docker://alpine:3.22')
    expect(publish).toHaveBeenCalledWith('env_cuda', {
      version: 'new-modules',
      description: 'Small base',
      source_uri: 'docker://alpine:3.22',
      expected_sha256: 'b'.repeat(64),
    })
  })

  it('uploads the selected SIF with description and prevents an oversized upload', async () => {
    const publish = vi.spyOn(api, 'publishSifEnvironment').mockResolvedValue(makeAttempt())
    renderRoute('/environments/env_cuda', '/environments/:environmentId', <EnvironmentPage />)
    fireEvent.click(await screen.findByRole('button', { name: '发布版本' }))
    const dialog = within(screen.getByRole('dialog'))
    fireEvent.change(await dialog.findByLabelText(/版本名称/), { target: { value: 'sif-v1' } })
    fireEvent.change(dialog.getByLabelText('说明'), { target: { value: 'My SIF' } })
    fireEvent.change(dialog.getByLabelText('运行方式'), { target: { value: 'apptainer_sif' } })
    fireEvent.change(dialog.getByLabelText('SIF 文件'), {
      target: { files: [new File(['x'.repeat(2048)], 'large.sif')] },
    })
    fireEvent.click(dialog.getByRole('button', { name: '发布版本' }))
    expect(await dialog.findByText(/请选择不超过/)).toBeVisible()
    expect(publish).not.toHaveBeenCalled()
    const file = new File(['sif'], 'runtime.sif')
    fireEvent.change(dialog.getByLabelText('SIF 文件'), { target: { files: [file] } })
    fireEvent.click(dialog.getByRole('button', { name: '发布版本' }))
    await waitFor(() =>
      expect(publish).toHaveBeenCalledWith('env_cuda', {
        version: 'sif-v1',
        description: 'My SIF',
        sif: file,
        source_uri: '',
        source_digest: '',
        architecture: 'x86_64',
      }),
    )
  })

  it('does not expose publishing or query history for readers', async () => {
    vi.mocked(api.environment).mockResolvedValue({ ...environment, capabilities: [] })
    renderRoute(
      '/environments/env_cuda?tab=history',
      '/environments/:environmentId',
      <EnvironmentPage />,
    )
    await screen.findByRole('heading', { name: 'CUDA Research' })
    expect(screen.queryByRole('button', { name: '发布版本' })).not.toBeInTheDocument()
    expect(api.environmentPublicationAttempts).not.toHaveBeenCalled()
  })

  it('shows modules and availability while keeping technical details folded', async () => {
    renderRoute(
      '/environment-versions/envv_cuda_124',
      '/environment-versions/:versionId',
      <EnvironmentVersionPage />,
    )
    expect(await screen.findByRole('heading', { name: 'CUDA Research' })).toBeVisible()
    expect(screen.getByText('当前可用')).toBeVisible()
    expect(screen.getByText('cuda/12.6')).toBeVisible()
    expect(screen.getByText('Validated modules')).toBeVisible()
    const disclosure = screen.getByText('技术信息').closest('details')!
    expect(disclosure.open).toBe(false)
    fireEvent.click(screen.getByText('技术信息'))
    expect(screen.getByText('envv_cuda_124')).toBeVisible()
    expect(screen.getByText(/modules_allowlist_v1/)).toBeVisible()
  })

  it('offers retry when the environment catalog request fails', async () => {
    vi.mocked(api.environments).mockRejectedValue(new Error('offline'))
    renderRoute('/environments', '/environments', <EnvironmentListPage />)

    expect(await screen.findByText('offline')).toBeVisible()
    expect(screen.getByRole('button', { name: '重试' })).toBeVisible()
  })
})

function makeAttempt(
  overrides: Partial<EnvironmentPublicationAttempt> = {},
): EnvironmentPublicationAttempt {
  return {
    id: 'evpa_1',
    environment_id: 'env_cuda',
    status: 'pending',
    version: 'new-modules',
    description: '',
    runtime_kind: 'modules',
    source_kind: 'modules',
    source_uri: '',
    stage: '',
    source_digest: '',
    expected_sha256: '',
    modules: [],
    validation_summary: '等待运行环境校验',
    validation_evidence: {},
    failure_code: null,
    failure_reason: null,
    version_id: null,
    created_by: 'usr_1',
    created_at: '2026-08-29T00:00:00Z',
    started_at: null,
    finished_at: null,
    ...overrides,
  }
}
