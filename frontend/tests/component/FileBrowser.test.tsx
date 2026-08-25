// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FileBrowser } from '../../src/components/project/FileBrowser'
import type { ProjectFile, LegacyWorkspaceContext } from '../../src/api/types'

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

const writer = {
  capabilities: ['project.content.write'],
} as unknown as LegacyWorkspaceContext

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
    vi.clearAllMocks()
  })

  it('逐个上传多个文件并分别标记成败', async () => {
    mocks.listFiles.mockResolvedValue([])
    // 第一个成功，第二个失败：状态必须能区分开。
    mocks.uploadFiles.mockResolvedValueOnce([]).mockRejectedValueOnce(new Error('超过单个文件上限'))

    const { container } = render(
      <FileBrowser projectId="proj-1" workspace={writer} onChanged={() => {}} />,
    )
    await screen.findByRole('button', { name: /上传文件/ })

    const input = pickInput(container, true)
    Object.defineProperty(input, 'files', { value: [makeFile('a.py'), makeFile('b.py')] })
    fireEvent.change(input)

    await waitFor(() => {
      expect(mocks.uploadFiles).toHaveBeenCalledTimes(2)
      expect(mocks.uploadFiles).toHaveBeenNthCalledWith(1, 'proj-1', [expect.any(File)])
      expect(mocks.uploadFiles).toHaveBeenNthCalledWith(2, 'proj-1', [expect.any(File)])
    })

    await waitFor(() => {
      expect(screen.getByText(/a\.py/)).toBeInTheDocument()
      expect(screen.getByText(/b\.py.*超过单个文件上限/)).toBeInTheDocument()
    })
  })

  it('压缩包被整体拒绝时展示失败原因', async () => {
    mocks.listFiles.mockResolvedValue([])
    mocks.uploadArchive.mockRejectedValue(new Error('压缩包包含符号链接条目「link」，已拒绝展开'))

    const { container } = render(
      <FileBrowser projectId="proj-1" workspace={writer} onChanged={() => {}} />,
    )
    await screen.findByRole('button', { name: /上传压缩包/ })

    const input = pickInput(container, false)
    Object.defineProperty(input, 'files', { value: [makeFile('bundle.zip')] })
    fireEvent.change(input)

    await waitFor(() => {
      expect(mocks.uploadArchive).toHaveBeenCalledWith('proj-1', expect.any(File))
      // 失败原因要原样可见，用户才知道换什么内容重传。
      expect(screen.getByText(/已拒绝展开/)).toBeInTheDocument()
    })
  })

  it('新建目录走 mkdir 并刷新列表', async () => {
    mocks.listFiles.mockResolvedValue(files)
    mocks.createDirectory.mockResolvedValue({})

    render(<FileBrowser projectId="proj-1" workspace={writer} onChanged={() => {}} />)
    await screen.findByText('train.py')

    fireEvent.click(screen.getByRole('button', { name: /新建目录/ }))
    fireEvent.change(screen.getByPlaceholderText('src/train.py'), {
      target: { value: 'data/raw' },
    })
    fireEvent.click(screen.getByRole('button', { name: /确\s*定/ }))

    await waitFor(() => {
      expect(mocks.createDirectory).toHaveBeenCalledWith('proj-1', 'data/raw')
    })
  })

  it('改名提交时携带源路径和新路径', async () => {
    mocks.listFiles.mockResolvedValue(files)
    mocks.movePath.mockResolvedValue([])

    render(<FileBrowser projectId="proj-1" workspace={writer} onChanged={() => {}} />)
    await screen.findByText('train.py')

    fireEvent.click(screen.getByRole('button', { name: /改名/ }))
    const inputs = screen.getAllByDisplayValue('train.py')
    // 第一个是禁用的源路径回显，第二个才是可编辑的新路径。
    const editable = inputs.find((element) => !(element as HTMLInputElement).disabled)
    if (!editable) throw new Error('找不到新路径输入框')
    fireEvent.change(editable, { target: { value: 'scripts/train_v2.py' } })
    fireEvent.click(screen.getByRole('button', { name: /确\s*定/ }))

    await waitFor(() => {
      expect(mocks.movePath).toHaveBeenCalledWith('proj-1', 'train.py', 'scripts/train_v2.py')
    })
  })

  it('复制提交时调用 copyPath', async () => {
    mocks.listFiles.mockResolvedValue(files)
    mocks.copyPath.mockResolvedValue([])

    render(<FileBrowser projectId="proj-1" workspace={writer} onChanged={() => {}} />)
    await screen.findByText('train.py')

    fireEvent.click(screen.getByRole('button', { name: /复制/ }))
    const inputs = screen.getAllByDisplayValue('train.py-copy')
    const editable = inputs.find((element) => !(element as HTMLInputElement).disabled)
    if (!editable) throw new Error('找不到目标路径输入框')
    fireEvent.click(screen.getByRole('button', { name: /确\s*定/ }))

    await waitFor(() => {
      expect(mocks.copyPath).toHaveBeenCalledWith('proj-1', 'train.py', 'train.py-copy')
    })
  })

  it('删除前必须经过危险操作确认', async () => {
    mocks.listFiles.mockResolvedValue(files)
    mocks.deletePath.mockResolvedValue(undefined)

    render(<FileBrowser projectId="proj-1" workspace={writer} onChanged={() => {}} />)
    await screen.findByText('train.py')

    const deleteButton = document.querySelector('button.ant-btn-dangerous')
    if (!deleteButton) throw new Error('找不到删除按钮')
    fireEvent.click(deleteButton)
    const confirmButton = await screen.findByRole('button', { name: /删\s*除/ })
    fireEvent.click(confirmButton)

    await waitFor(() => {
      expect(mocks.deletePath).toHaveBeenCalledWith('proj-1', 'train.py')
    })
  })

  it('点击下载调用下载接口', async () => {
    mocks.listFiles.mockResolvedValue(files)
    mocks.downloadFile.mockResolvedValue(undefined)

    render(<FileBrowser projectId="proj-1" workspace={writer} onChanged={() => {}} />)
    await screen.findByText('train.py')

    fireEvent.click(screen.getByRole('button', { name: /下载/ }))
    await waitFor(() => {
      expect(mocks.downloadFile).toHaveBeenCalledWith('proj-1', 'train.py')
    })
  })

  it('只读场景不暴露任何写入口', async () => {
    mocks.listFiles.mockResolvedValue(files)

    render(<FileBrowser projectId="proj-1" workspace={undefined} onChanged={() => {}} />)
    await screen.findByText('train.py')

    expect(screen.queryByRole('button', { name: /上传文件/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /新建目录/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /下载/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /改名/ })).toBeNull()
    expect(document.querySelector('button.ant-btn-dangerous')).toBeNull()
  })
})
