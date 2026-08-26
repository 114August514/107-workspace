// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { RunTable } from '../../src/components/run/RunTable'
import type { Run } from '../../src/api/types'

/**
 * RunTable 新增的「版本」列：显示 label，可点击跳转到 Version 详情页。
 *
 * 这条断言守的是一个可观察契约——Run History 里每行 Run 都能溯源到
 * 它当时跑的是哪个不可变版本，而 label（v3）比 raw id 更人可读。
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

describe('RunTable 版本列', () => {
  it('显示 project_version_label 并链接到 /versions/:id', () => {
    const runs = [makeRun()]

    render(
      <MemoryRouter>
        <RunTable runs={runs} />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', { name: 'v3' })
    expect(link).toHaveAttribute('href', '/versions/ver-1')
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
