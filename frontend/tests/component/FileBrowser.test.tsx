// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FileBrowser } from '../../src/components/project/FileBrowser'
import type { Project, ProjectFile } from '../../src/api/types'

/**
 * FileBrowser 测试：Working State 文件管理 Core（Issue #47）。
 *
 * 守的是验收条件里最容易被回归的三件事：
 * 「上传有明确的成败状态，失败时能看到具体原因」、
 * 「危险操作（删除）必须先确认」、
 * 「只读场景完全不暴露写入口」。
 */

const mocks = vi.hoisted(() => ({
  listFiles: vi.fn(),
  readFile: vi.fn(),
  writeFile: vi.fn(),
  uploadFiles: vi.fn(),
  uploadArchive: vi.fn(),
  movePath: vi.fn(),
  copyPath: vi.fn(),
  createDirectory: vi.fn(),
  deletePath: vi.fn(),
  downloadFile: vi.fn(),
}))

vi.mock('../../src/api/client', () => ({ api: mocks }))

const writer: Project = {
  capabilities: ['project.content.write'],
  created_at: '2026-08-12T10:00:00Z',
  created_by: 'user-1',
  default_run_configuration_id: null,
  description: '测试项目',
  environment_version_id: null,
  id: 'proj-1',
  name: '测试项目',
  owner: { display_name: 'Alice', id: 'user-1', kind: 'user' },
  status: 'active',
  updated_at: '2026-08-12T10:00:00Z',
  visibility: 'owner_scope',
}

const reader: Project = {
  ...writer,
  capabilities: ['project.view'],
}

const files: ProjectFile[] = [
  {
    path: 'train.py',
    size: 128,
    content_hash: 'abc',
    updated_at: '2026-08-12T10:00:00Z',
  },
]

function makeFile(name: string): File {
  return new File(['content'], name, { type: 'text/plain' })
}

function pickInput(container: HTMLElement, multiple: boolean): HTMLInputElement {
  const input = container.querySelector<HTMLInputElement>(
    `input[type="file"]${multiple ? '[multiple]' : ':not([multiple])'}`,
  )
  if (!input) throw new Error('找不到隐藏的上传 input')
  return input
}

describe('FileBrowser', () => {
  afterEach(() => {
    cleanup()
    vi.resetAllMocks()
  })
  function renderBrowser(access: Project = writer, currentPath = '') {
    return render(
      <MemoryRouter>
        <FileBrowser
          projectId="proj-1"
          access={access}
          onChanged={() => {}}
          currentPath={currentPath}
        />
      </MemoryRouter>,
    )
  }

  it('逐个上传多个文件时展示上传中、成功和失败状态', async () => {
    mocks.listFiles.mockResolvedValue([])
    let resolveFirstUpload!: (files: ProjectFile[]) => void
    const firstUpload = new Promise<ProjectFile[]>((resolve) => {
      resolveFirstUpload = resolve
    })
    mocks.uploadFiles
      .mockReturnValueOnce(firstUpload)
      .mockRejectedValueOnce(new Error('超过单个文件上限'))

    const { container } = renderBrowser()
    await screen.findByRole('button', { name: /上传文件/ })

    const input = pickInput(container, true)
    Object.defineProperty(input, 'files', { value: [makeFile('a.py'), makeFile('b.py')] })
    fireEvent.change(input)

    expect(await screen.findByText('a.py（上传中）')).toBeInTheDocument()
    expect(screen.getByText('b.py（上传中）')).toBeInTheDocument()

    await act(async () => {
      resolveFirstUpload([])
      await firstUpload
    })

    expect(await screen.findByText('a.py')).toBeInTheDocument()
    expect(await screen.findByText('b.py：超过单个文件上限')).toBeInTheDocument()
    expect(screen.queryByText('a.py（上传中）')).not.toBeInTheDocument()
  })

  it('压缩包被整体拒绝时展示失败原因', async () => {
    mocks.listFiles.mockResolvedValue([])
    mocks.uploadArchive.mockRejectedValue(new Error('压缩包包含符号链接条目「link」，已拒绝展开'))

    const { container } = renderBrowser()
    fireEvent.click(screen.getByRole('button', { name: '添加文件' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '上传压缩包（zip）' }))

    const input = pickInput(container, false)
    Object.defineProperty(input, 'files', { value: [makeFile('bundle.zip')] })
    fireEvent.change(input)

    await waitFor(() => {
      expect(mocks.uploadArchive).toHaveBeenCalledWith('proj-1', expect.any(File))
      // 失败原因要原样可见，用户才知道换什么内容重传。
      expect(screen.getByText(/已拒绝展开/)).toBeInTheDocument()
    })
  })

  it('在目录页使用目录上下文操作，而不是列表行操作', async () => {
    mocks.listFiles
      .mockResolvedValueOnce([
        {
          path: 'data/raw/input.csv',
          size: 12,
          content_hash: 'nested',
          updated_at: '2026-08-12T10:00:00Z',
        },
      ])
      .mockResolvedValueOnce([])
    mocks.deletePath.mockResolvedValue(undefined)

    renderBrowser(writer, 'data')

    expect(await screen.findByRole('link', { name: 'raw' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /更多操作/ })).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '目录操作' }))
    fireEvent.click(await screen.findByRole('menuitem', { name: '删除目录' }))
    fireEvent.click(await screen.findByRole('button', { name: '删除目录' }))

    await waitFor(() => {
      expect(mocks.deletePath).toHaveBeenCalledWith('proj-1', 'data')
    })
    expect(
      await screen.findByText('还没有文件。先新建一个，再保存 Project Version。'),
    ).toBeInTheDocument()
  })

  it('只读场景不暴露任何写入口', async () => {
    mocks.listFiles.mockResolvedValue(files)

    renderBrowser(reader)
    await screen.findByText('train.py')

    expect(screen.queryByRole('button', { name: /上传文件/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /上传压缩包/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /新建目录/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /新建文件/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /改名/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /复制/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /删除/ })).not.toBeInTheDocument()
  })
})
