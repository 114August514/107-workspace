// @vitest-environment jsdom

import type { ReactNode } from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { Environment } from '../../src/api/types'
import { EnvironmentListPage } from '../../src/pages/EnvironmentListPage'
import { EnvironmentPage } from '../../src/pages/EnvironmentPage'
import { EnvironmentVersionPage } from '../../src/pages/EnvironmentVersionPage'
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
        <Routes>
          <Route path={path} element={element} />
        </Routes>
      </PrimerRoot>
    </MemoryRouter>,
  )
}

beforeEach(() => {
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
    expect(screen.getByText('归属：GPU Lab')).toBeVisible()
    expect(screen.getByRole('link', { name: /12.4/ })).toHaveAttribute(
      'href',
      '/environment-versions/envv_cuda_124',
    )
    expect(screen.getByRole('link', { name: /12.5/ })).toHaveTextContent('不可用')
  })

  it('shows a durable pending publication attempt', async () => {
    vi.spyOn(api, 'publishModulesEnvironment').mockResolvedValue({
      id: 'evpa_1',
      environment_id: 'env_cuda',
      status: 'pending',
      version: 'new-modules',
      description: '',
      runtime_kind: 'modules',
      validation_summary: '等待运行环境校验',
      validation_evidence: {},
      failure_code: null,
      failure_reason: null,
      version_id: null,
      created_by: 'usr_1',
      created_at: '2026-08-29T00:00:00Z',
      started_at: null,
      finished_at: null,
    })
    renderRoute('/environments/env_cuda', '/environments/:environmentId', <EnvironmentPage />)
    await screen.findByRole('heading', { name: 'CUDA Research' })
    fireEvent.change(screen.getAllByRole('textbox')[0]!, { target: { value: 'new-modules' } })
    fireEvent.click(screen.getByRole('button', { name: '创建发布尝试' }))
    expect(await screen.findByText('pending')).toBeVisible()
    expect(screen.getByText(/等待运行环境校验/)).toBeVisible()
    expect(screen.getByRole('button', { name: '刷新校验状态' })).toBeVisible()
  })

  it('hydrates failed attempts and submits Apptainer SIF multipart state', async () => {
    vi.mocked(api.environmentPublicationAttempts).mockResolvedValue([
      {
        id: 'evpa_failed',
        environment_id: 'env_cuda',
        status: 'failed',
        version: 'bad-sif',
        description: '',
        runtime_kind: 'apptainer_sif',
        validation_summary: '运行环境校验失败',
        validation_evidence: {},
        failure_code: 'validation_failed',
        failure_reason: 'Apptainer 拒绝该 SIF',
        version_id: null,
        created_by: 'usr_1',
        created_at: '2026-08-29T00:00:00Z',
        started_at: '2026-08-29T00:00:01Z',
        finished_at: '2026-08-29T00:00:02Z',
      },
    ])
    const pending = {
      id: 'evpa_sif',
      environment_id: 'env_cuda',
      status: 'pending' as const,
      version: 'sif-v1',
      description: '',
      runtime_kind: 'apptainer_sif' as const,
      validation_summary: '等待运行环境校验',
      validation_evidence: {},
      failure_code: null,
      failure_reason: null,
      version_id: null,
      created_by: 'usr_1',
      created_at: '2026-08-29T00:00:03Z',
      started_at: null,
      finished_at: null,
    }
    const publish = vi.spyOn(api, 'publishSifEnvironment').mockResolvedValue(pending)
    const view = renderRoute(
      '/environments/env_cuda',
      '/environments/:environmentId',
      <EnvironmentPage />,
    )
    expect(await screen.findByText(/Apptainer 拒绝该 SIF/)).toBeVisible()
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'apptainer_sif' } })
    const file = new File(['sif'], 'runtime.sif', { type: 'application/octet-stream' })
    const fileInput = view.container.querySelector('input[type="file"]')
    expect(fileInput).not.toBeNull()
    fireEvent.change(fileInput!, { target: { files: [file] } })
    const inputs = screen.getAllByRole('textbox')
    fireEvent.change(inputs[0]!, { target: { value: 'sif-v1' } })
    fireEvent.change(inputs[1]!, { target: { value: 'https://example.invalid/runtime.sif' } })
    fireEvent.change(inputs[2]!, { target: { value: 'sha256:source' } })
    fireEvent.click(screen.getByRole('button', { name: '创建发布尝试' }))
    expect(await screen.findByText('pending')).toBeVisible()
    expect(publish).toHaveBeenCalledWith('env_cuda', {
      version: 'sif-v1',
      sif: file,
      source_uri: 'https://example.invalid/runtime.sif',
      source_digest: 'sha256:source',
      architecture: 'x86_64',
    })
  })
  it('shows exact version identity and execution basis', async () => {
    renderRoute(
      '/environment-versions/envv_cuda_124',
      '/environment-versions/:versionId',
      <EnvironmentVersionPage />,
    )

    expect(await screen.findByRole('heading', { name: 'CUDA Research · 12.4' })).toBeVisible()
    expect(screen.getByText('当前可用')).toBeVisible()
    expect(screen.getByText('envv_cuda_124')).toBeVisible()
    expect(screen.getByText('modules')).toBeVisible()
    expect(screen.getByText('Validated modules')).toBeVisible()
    expect(screen.getByText(/modules_allowlist_v1/)).toBeVisible()
    expect(screen.getByText('Current platform evidence')).toBeVisible()
  })

  it('offers retry when the environment catalog request fails', async () => {
    vi.mocked(api.environments).mockRejectedValue(new Error('offline'))
    renderRoute('/environments', '/environments', <EnvironmentListPage />)

    expect(await screen.findByText('offline')).toBeVisible()
    expect(screen.getByRole('button', { name: '重试' })).toBeVisible()
  })
})
