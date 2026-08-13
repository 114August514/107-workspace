// @vitest-environment jsdom

import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { VersionDiffPanel } from '../../src/components/project/VersionDiffPanel'
import type { ProjectVersionPage, VersionDiff } from '../../src/api/types'

/**
 * VersionDiffPanel：文件级差异展示。
 *
 * 后端只提供文件粒度（哪些文件增删改），不提供行级 Diff。
 * 这里守的是「diff 结果正确映射到标签和颜色」以及「空 diff 和无基准版本
 * 两种边界都有明确提示」。
 */

const mockListVersions = vi.hoisted(() => vi.fn())
const mockDiffVersions = vi.hoisted(() => vi.fn())

vi.mock('../../src/api/client', () => ({
  api: {
    listVersions: mockListVersions,
    diffVersions: mockDiffVersions,
  },
}))

function makeVersionPage(versions: { id: string; sequence: number; label: string }[]) {
  return {
    items: versions.map((v) => ({
      id: v.id,
      label: v.label,
      sequence: v.sequence,
      created_at: '2026-08-12T10:00:00Z',
      created_by: 'user-1',
      file_count: 5,
      message: '',
      project_id: 'proj-1',
      total_size: 1024,
    })),
    page: 1,
    page_size: 20,
    total: versions.length,
    has_more: false,
  } satisfies ProjectVersionPage
}

describe('VersionDiffPanel', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  it('显示 diff 结果中的 added 和 modified 文件', async () => {
    mockListVersions.mockResolvedValue(
      makeVersionPage([
        { id: 'ver-1', sequence: 1, label: 'v1' },
        { id: 'ver-2', sequence: 2, label: 'v2' },
        { id: 'ver-3', sequence: 3, label: 'v3' },
      ]),
    )
    const diffs: VersionDiff[] = [
      { change: 'added', path: 'new_file.py' },
      { change: 'modified', path: 'main.py' },
    ]
    mockDiffVersions.mockResolvedValue(diffs)

    render(
      <MemoryRouter>
        <VersionDiffPanel projectId="proj-1" currentVersionId="ver-3" currentVersionSequence={3} />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('new_file.py')).toBeInTheDocument()
      expect(screen.getByText('main.py')).toBeInTheDocument()
    })

    // change 标签
    expect(screen.getByText('新增')).toBeInTheDocument()
    expect(screen.getByText('修改')).toBeInTheDocument()
  })

  it('两个版本内容相同时显示「完全相同」提示', async () => {
    mockListVersions.mockResolvedValue(
      makeVersionPage([
        { id: 'ver-1', sequence: 1, label: 'v1' },
        { id: 'ver-2', sequence: 2, label: 'v2' },
      ]),
    )
    mockDiffVersions.mockResolvedValue([])

    render(
      <MemoryRouter>
        <VersionDiffPanel projectId="proj-1" currentVersionId="ver-2" currentVersionSequence={2} />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/完全相同/)).toBeInTheDocument()
    })
  })

  it('当前版本是第一个版本时显示无可比较提示', async () => {
    mockListVersions.mockResolvedValue(makeVersionPage([{ id: 'ver-1', sequence: 1, label: 'v1' }]))

    render(
      <MemoryRouter>
        <VersionDiffPanel projectId="proj-1" currentVersionId="ver-1" currentVersionSequence={1} />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText(/没有可比较的历史版本/)).toBeInTheDocument()
    })
  })
})
