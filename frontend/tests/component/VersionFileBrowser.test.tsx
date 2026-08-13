// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { VersionFileBrowser } from '../../src/components/project/VersionFileBrowser'
import type { ProjectVersionFile } from '../../src/api/types'

/**
 * VersionFileBrowser 测试：只读文件浏览。
 *
 * 守的是 Issue #12 的核心行为：Version 是不可变快照，
 * 用户能浏览版本里的文件内容，但不能编辑。
 * 这里断言「点击查看后调用 readVersionFile 并展示内容」和「只读标记可见」。
 */

const mockReadVersionFile = vi.hoisted(() => vi.fn())

vi.mock('../../src/api/client', () => ({
  api: {
    readVersionFile: mockReadVersionFile,
  },
}))

const files: ProjectVersionFile[] = [
  { path: 'train.py', content_hash: 'abc', size: 1024 },
  { path: 'README.md', content_hash: 'def', size: 256 },
]

describe('VersionFileBrowser', () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it('点击「查看」后读取并展示文件内容，显示只读标记', async () => {
    mockReadVersionFile.mockResolvedValue({
      content: 'print("hello")',
      path: 'train.py',
      truncated: false,
    })

    render(<VersionFileBrowser versionId="ver-1" files={files} />)

    // 文件列表中有两个文件
    expect(screen.getByText('train.py')).toBeInTheDocument()
    expect(screen.getByText('README.md')).toBeInTheDocument()

    // 点击 train.py 的「查看」链接
    const viewLinks = screen.getAllByText('查看')
    expect(viewLinks[0]).toBeDefined()
    fireEvent.click(viewLinks[0]!)

    // 等待文件内容加载并显示在 Drawer 中
    await waitFor(() => {
      expect(mockReadVersionFile).toHaveBeenCalledWith('ver-1', 'train.py')
    })

    // Drawer 中有只读标记和文件内容
    await waitFor(() => {
      expect(screen.getByText('只读')).toBeInTheDocument()
      expect(screen.getByDisplayValue('print("hello")')).toBeInTheDocument()
    })
  })

  it('文件超过 256 KiB 时显示截断提示', async () => {
    mockReadVersionFile.mockResolvedValue({
      content: 'x'.repeat(100),
      path: 'big.txt',
      truncated: true,
    })

    render(
      <VersionFileBrowser
        versionId="ver-1"
        files={[{ path: 'big.txt', content_hash: 'h', size: 300000 }]}
      />,
    )

    fireEvent.click(screen.getByText('查看'))

    await waitFor(() => {
      expect(screen.getByText('内容已截断')).toBeInTheDocument()
    })
  })
})
