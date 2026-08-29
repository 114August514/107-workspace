// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'

import { RunTable } from '../../src/components/run/RunTable'
import type { Run } from '../../src/api/types'

afterEach(cleanup)

/**
 * Run history 先展示状态、名称和耗时；Project 版本与发起用户作为可追溯上下文。
 * 调度任务和退出码属于单次 Run 的诊断信息，不占用历史列表主列。
 */
function makeRun(overrides: Partial<Run> = {}): Run {
  return {
    id: 'run-1',
    name: '首次运行',
    status: 'succeeded',
    project_id: 'proj-1',
    initiated_by_user_id: 'user-1',
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
    project_version_label: 'v3',
    ...overrides,
  }
}

describe('RunTable 用户语义', () => {
  it('保留可点击的 Project 版本与 canonical Run 链接', () => {
    const runs = [makeRun()]

    render(
      <MemoryRouter>
        <RunTable runs={runs} />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: 'v3' })
    expect(link).toHaveAttribute('href', '/versions/ver-1')
    expect(screen.getByRole('link', { name: '首次运行' })).toHaveAttribute(
      'href',
      '/projects/proj-1/runs/run-1',
    )
  })

  it('把自动生成的名称收敛为短 Run 标识，并把上下文放在同一行', () => {
    render(
      <MemoryRouter>
        <RunTable
          projectName="Demo Project"
          runs={[
            makeRun({
              id: 'run_abcdef123456',
              name: 'Demo Project · v3',
              queued_seconds: 2,
              running_seconds: 8,
            }),
          ]}
        />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Run #abcdef12' })).toHaveAttribute(
      'href',
      '/projects/proj-1/runs/run_abcdef123456',
    )
    expect(screen.getByText('运行 8 秒')).toBeVisible()
    expect(screen.queryByText(/user-1/)).toBeNull()
    expect(screen.getAllByRole('columnheader').map((header) => header.textContent)).toEqual([
      '状态',
      'Run',
      '执行时间',
      '创建时间',
    ])
    expect(screen.queryByRole('columnheader', { name: '退出码' })).toBeNull()
    expect(screen.queryByText(/调度任务/)).toBeNull()
  })

  it('多行 Run 各自显示自己的版本', () => {
    const runs = [
      makeRun({ id: 'run-a', project_version_id: 'ver-1', project_version_label: 'v1' }),
      makeRun({ id: 'run-b', project_version_id: 'ver-2', project_version_label: 'v2' }),
    ]

    render(
      <MemoryRouter>
        <RunTable runs={runs} />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'v1' })).toHaveAttribute('href', '/versions/ver-1')
    expect(screen.getByRole('link', { name: 'v2' })).toHaveAttribute('href', '/versions/ver-2')
  })
})
