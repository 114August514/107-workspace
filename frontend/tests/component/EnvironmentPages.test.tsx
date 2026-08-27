// @vitest-environment jsdom

import type { ReactNode } from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { Environment } from '../../src/api/types'
import { EnvironmentListPage } from '../../src/pages/EnvironmentListPage'
import { EnvironmentPage } from '../../src/pages/EnvironmentPage'
import { EnvironmentVersionPage } from '../../src/pages/EnvironmentVersionPage'
import { PrimerRoot } from '../../src/primer/setup'

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
      image: 'cuda:12.4',
      setup_command: 'module load cuda/12.4',
      available: true,
    },
    {
      id: 'envv_cuda_125',
      environment_id: 'env_cuda',
      version: '12.5',
      description: 'Retired image',
      image: 'cuda:12.5',
      setup_command: '',
      available: false,
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

  it('shows exact version identity and execution basis', async () => {
    renderRoute(
      '/environment-versions/envv_cuda_124',
      '/environment-versions/:versionId',
      <EnvironmentVersionPage />,
    )

    expect(await screen.findByRole('heading', { name: 'CUDA Research · 12.4' })).toBeVisible()
    expect(screen.getByText('当前可用')).toBeVisible()
    expect(screen.getByText('envv_cuda_124')).toBeVisible()
    expect(screen.getByText('cuda:12.4')).toBeVisible()
    expect(screen.getByText('module load cuda/12.4')).toBeVisible()
  })

  it('offers retry when the environment catalog request fails', async () => {
    vi.mocked(api.environments).mockRejectedValue(new Error('offline'))
    renderRoute('/environments', '/environments', <EnvironmentListPage />)

    expect(await screen.findByText('offline')).toBeVisible()
    expect(screen.getByRole('button', { name: '重试' })).toBeVisible()
  })
})
