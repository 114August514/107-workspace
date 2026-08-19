// @vitest-environment jsdom
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import { api, ApiError } from '../../src/api/client'
import type { LogChunk, RunDetail, LegacyWorkspaceContext } from '../../src/api/types'
import { RunPage } from '../../src/pages/RunPage'

const runDetailFixture = (): RunDetail => ({
  run: {
    id: 'run-1',
    name: 'test-run',
    project_id: 'project-1',
    workspace_id: 'workspace-1',
    project_version_id: 'version-1',
    project_version_label: 'v1',
    snapshot_id: 'snapshot-1',
    source_run_id: null,
    source_run_configuration_id: null,
    status: 'succeeded',
    created_by: 'student',
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
    environment_image: 'python:3.11',
    environment_setup_command: '',
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
    created_by: 'student',
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
    source_run_configuration_id: null,
    working_directory: '',
  },
})

const workspaceFixture = (): LegacyWorkspaceContext => ({
  id: 'workspace-1',
  name: 'test-workspace',
  kind: 'personal',
  role: 'owner',
  capabilities: ['run.submit', 'run.cancel'],
  default_environment_version_id: null,
  owner_id: 'student',
})

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <ConfigProvider locale={zhCN}>
      <MemoryRouter initialEntries={['/runs/run-1']}>
        <Routes>
          <Route path="/runs/:runId" element={children} />
        </Routes>
      </MemoryRouter>
    </ConfigProvider>
  )
}

describe('RunPage backend unavailable', () => {
  beforeEach(() => {
    vi.resetAllMocks()
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
    vi.spyOn(api, 'getLegacyWorkspaceContext').mockResolvedValue(workspaceFixture())

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
    expect(screen.getByRole('heading', { name: 'test-run' })).toBeInTheDocument()
  })
})
