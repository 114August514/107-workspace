// @vitest-environment jsdom

import { cleanup, render, screen, waitFor } from '@testing-library/react'
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
    cleanup()
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

  it('查看 v5 时默认比较对象确实是跨页找到的前序版本 v4', async () => {
    // 分页边界正好夹在当前版本 v5 与其真正前序 v4 之间：
    // page 1 以 v5 收尾，page 2 以 v4 开头。
    // 若实现退化成「只读第一页」，v4 不会出现在基准选项里，diff 会错误对比 v8。
    mockListVersions
      .mockResolvedValueOnce({
        ...makeVersionPage([
          { id: 'ver-8', sequence: 8, label: 'v8' },
          { id: 'ver-7', sequence: 7, label: 'v7' },
          { id: 'ver-6', sequence: 6, label: 'v6' },
          { id: 'ver-5', sequence: 5, label: 'v5' },
        ]),
        page: 1,
        has_more: true,
      })
      .mockResolvedValueOnce({
        ...makeVersionPage([
          { id: 'ver-4', sequence: 4, label: 'v4' },
          { id: 'ver-3', sequence: 3, label: 'v3' },
          { id: 'ver-2', sequence: 2, label: 'v2' },
        ]),
        page: 2,
        has_more: false,
      })
    mockDiffVersions.mockResolvedValue([{ change: 'added', path: 'new.py' }])

    render(
      <MemoryRouter>
        <VersionDiffPanel projectId="proj-1" currentVersionId="ver-5" currentVersionSequence={5} />
      </MemoryRouter>,
    )

    // 核心契约：当前版本 v5 的默认比较对象必须是跨页找到的 v4，
    // 而不是第一页里 sequence 更大（更早）的 v8/v7/v6。
    await waitFor(() => {
      expect(mockDiffVersions).toHaveBeenCalledWith('ver-5', 'ver-4')
    })

    // 辅助断言：确实拉取了全部两页
    expect(mockListVersions).toHaveBeenCalledTimes(2)
    expect(mockListVersions).toHaveBeenNthCalledWith(1, 'proj-1', { page: 1, page_size: 100 })
    expect(mockListVersions).toHaveBeenNthCalledWith(2, 'proj-1', { page: 2, page_size: 100 })

    // diff 结果渲染
    await waitFor(() => {
      expect(screen.getByText('new.py')).toBeInTheDocument()
    })
  })
})
