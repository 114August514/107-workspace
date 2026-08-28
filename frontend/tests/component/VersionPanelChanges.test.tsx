// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { VersionPanel } from '../../src/components/project/VersionPanel'
import type {
  Project,
  ProjectVersionPage,
  WorkingChange,
  WorkingChangeDetail,
} from '../../src/api/types'

/**
 * VersionPanel 未保存变更测试（Issue #47）。
 *
 * 守的是「变更标签点开是内容级差异，不是只有 added/modified/removed 标签」、
 * 「放弃指定变更要确认，且放弃后历史版本不动」、
 * 「只读角色看得到差异但没有放弃入口」。
 */

const mocks = vi.hoisted(() => ({
  listVersions: vi.fn(),
  workingChanges: vi.fn(),
  saveVersion: vi.fn(),
  restoreVersion: vi.fn(),
  workingChangeDetail: vi.fn(),
  discardChanges: vi.fn(),
  listUserGroups: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../src/api/client', () => ({ api: mocks }))

const writer = {
  capabilities: ['project.content.write'],
} as Project

function makeVersionPage(): ProjectVersionPage {
  return {
    items: [
      {
        id: 'ver-1',
        label: 'v1',
        sequence: 1,
        created_at: '2026-08-12T10:00:00Z',
        created_by: 'user-1',
        file_count: 2,
        message: '初始版本',
        project_id: 'proj-1',
        total_size: 256,
      },
    ],
    page: 1,
    page_size: 20,
    total: 1,
    has_more: false,
  }
}

const changes: WorkingChange[] = [
  { path: 'a.txt', change: 'modified' },
  { path: 'new.txt', change: 'added' },
]

const detail: WorkingChangeDetail = {
  path: 'a.txt',
  change: 'modified',
  previous: { path: 'a.txt', content: 'original a', truncated: false },
  current: { path: 'a.txt', content: 'changed a', truncated: false },
}

const addedDetail: WorkingChangeDetail = {
  path: 'new.txt',
  change: 'added',
  previous: null,
  current: { path: 'new.txt', content: 'brand new', truncated: false },
}

function renderPanel(access: Project | undefined, onVersionSaved = () => {}) {
  return render(
    <MemoryRouter>
      <VersionPanel
        projectId="proj-1"
        projectName="测试项目"
        access={access}
        refreshToken={0}
        onVersionSaved={onVersionSaved}
      />
    </MemoryRouter>,
  )
}

describe('VersionPanel 未保存变更', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('点击变更标签打开内容级差异并展示两侧内容', async () => {
    mocks.listVersions.mockResolvedValue(makeVersionPage())
    mocks.workingChanges.mockResolvedValue(changes)
    mocks.workingChangeDetail.mockResolvedValueOnce(detail).mockResolvedValueOnce(addedDetail)

    renderPanel(writer)
    await screen.findByText(/有 2 处未保存的变更/)

    fireEvent.click(screen.getByRole('button', { name: '修改 a.txt' }))

    await waitFor(() => {
      expect(mocks.workingChangeDetail).toHaveBeenCalledWith('proj-1', 'a.txt')
      expect(screen.getByText('original a')).toBeInTheDocument()
      expect(screen.getByText('changed a')).toBeInTheDocument()
    })
    // 新增路径在基线中不存在时要有明确说明，而不是渲染一个空面板。
    fireEvent.click(screen.getByRole('button', { name: '新增 new.txt' }))
    await waitFor(() => {
      expect(screen.getByText(/此路径在基线版本中不存在/)).toBeInTheDocument()
    })
  })

  it('放弃指定变更需要确认，成功后刷新变更列表', async () => {
    mocks.listVersions.mockResolvedValue(makeVersionPage())
    mocks.workingChanges.mockResolvedValue(changes)
    mocks.workingChangeDetail.mockResolvedValue(detail)
    mocks.discardChanges.mockResolvedValue([])

    const onVersionSaved = vi.fn()
    renderPanel(writer, onVersionSaved)
    await screen.findByText(/有 2 处未保存的变更/)

    fireEvent.click(screen.getByRole('button', { name: '修改 a.txt' }))
    fireEvent.click(await screen.findByRole('button', { name: /放弃此变更/ }))
    fireEvent.click(await screen.findByRole('button', { name: /放\s*弃\s*变\s*更/ }))

    await waitFor(() => {
      expect(mocks.discardChanges).toHaveBeenCalledWith('proj-1', ['a.txt'])
      expect(onVersionSaved).toHaveBeenCalled()
    })
  })

  it('只读角色能看到变更标签但没有放弃入口', async () => {
    mocks.listVersions.mockResolvedValue(makeVersionPage())
    mocks.workingChanges.mockResolvedValue(changes)
    mocks.workingChangeDetail.mockResolvedValue(detail)

    renderPanel(undefined)
    await screen.findByText(/有 2 处未保存的变更/)

    fireEvent.click(screen.getByRole('button', { name: '修改 a.txt' }))
    await waitFor(() => {
      expect(screen.getByText('original a')).toBeInTheDocument()
    })
    expect(screen.queryByRole('button', { name: /放弃此变更/ })).toBeNull()
  })

  it('详情加载失败时显示错误并可重试', async () => {
    mocks.listVersions.mockResolvedValue(makeVersionPage())
    mocks.workingChanges.mockResolvedValue(changes)
    mocks.workingChangeDetail
      .mockRejectedValueOnce(new Error('详情暂时不可用'))
      .mockResolvedValueOnce(detail)

    renderPanel(writer)
    await screen.findByText(/有 2 处未保存的变更/)
    const opener = screen.getByRole('button', { name: '修改 a.txt' })
    opener.focus()
    expect(opener).toHaveFocus()
    fireEvent.click(opener)

    const errorText = await screen.findByText('详情暂时不可用')
    const errorAlert = errorText.closest<HTMLElement>('[role="alert"]')
    if (!errorAlert) throw new Error('找不到详情错误提示')
    fireEvent.click(within(errorAlert).getByRole('button', { name: /重\s*试/ }))

    expect(await screen.findByText('changed a')).toBeInTheDocument()
    expect(mocks.workingChangeDetail).toHaveBeenCalledTimes(2)
  })
})
