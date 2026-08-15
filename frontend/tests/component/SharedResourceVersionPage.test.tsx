// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SharedResourceVersionPage } from '../../src/pages/SharedResourceVersionPage'
import type { SharedResourceDetail, SharedResourceVersionDetail } from '../../src/api/types'

/**
 * SharedResourceVersionPage 文件预览状态。
 *
 * 守的是 Review #4：点击文件即打开 Dialog，内部走 加载 → 成功/失败 切换，
 * 而不是只在请求成功后才挂载 Dialog（那样 loading 看不见、失败不出现）。
 *
 * 断言用角色和可见文案，不绑定 Primer 私有 DOM/class。
 */

const mockGetSharedResourceVersion = vi.hoisted(() => vi.fn())
const mockGetSharedResource = vi.hoisted(() => vi.fn())
const mockReadSharedResourceVersionFile = vi.hoisted(() => vi.fn())

vi.mock('../../src/api/client', () => ({
  api: {
    getSharedResourceVersion: mockGetSharedResourceVersion,
    getSharedResource: mockGetSharedResource,
    readSharedResourceVersionFile: mockReadSharedResourceVersionFile,
  },
}))

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

const version: SharedResourceVersionDetail = {
  id: 'ver_test',
  shared_resource_id: 'res_test',
  label: 'v1',
  description: '首个版本',
  sequence: 1,
  file_count: 1,
  total_size: 100,
  created_at: '2026-08-14T10:00:00Z',
  created_by: 'student',
  files: [{ path: 'train.py', content_hash: 'abc', size: 100 }],
}

const resource: SharedResourceDetail = {
  id: 'res_test',
  name: '预训练权重',
  description: '',
  is_platform_owned: false,
  owner_workspace_id: 'ws_test',
  created_at: '2026-08-14T10:00:00Z',
  versions: [],
}

function renderPage(versionId = 'ver_test') {
  return render(
    <MemoryRouter initialEntries={[`/shared-resource-versions/${versionId}`]}>
      <Routes>
        <Route
          path="/shared-resource-versions/:versionId"
          element={<SharedResourceVersionPage />}
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SharedResourceVersionPage 文件预览', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', ResizeObserverStub)
    mockGetSharedResourceVersion.mockResolvedValue(version)
    mockGetSharedResource.mockResolvedValue(resource)
  })

  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('点击文件即打开预览，成功后展示内容', async () => {
    mockReadSharedResourceVersionFile.mockResolvedValue('import os\nprint(1)\n')

    renderPage()

    const fileButton = await screen.findByRole('button', { name: 'train.py' })
    fireEvent.click(fileButton)

    // Dialog 以文件名为标题打开
    const dialog = await screen.findByRole('dialog', { name: 'train.py' })
    expect(dialog).toBeInTheDocument()
    await waitFor(() => {
      // 内容渲染在 <pre> 里；scope 到 dialog 内部，避免匹配到祖先文本节点。
      expect(dialog.querySelector('pre')?.textContent).toContain('import os')
    })
    expect(mockReadSharedResourceVersionFile).toHaveBeenCalledWith('ver_test', 'train.py')
  })

  it('加载期间显示「正在读取文件」', async () => {
    // 不 resolve，让 loading 持续
    mockReadSharedResourceVersionFile.mockReturnValue(new Promise(() => {}))

    renderPage()

    const fileButton = await screen.findByRole('button', { name: 'train.py' })
    fireEvent.click(fileButton)

    expect(await screen.findByText('正在读取文件…')).toBeInTheDocument()
    expect(screen.queryByText('文件预览失败。')).not.toBeInTheDocument()
  })

  it('读取失败时展示「文件预览失败。」并保留 Dialog', async () => {
    mockReadSharedResourceVersionFile.mockRejectedValue(new Error('网络异常'))

    renderPage()

    const fileButton = await screen.findByRole('button', { name: 'train.py' })
    fireEvent.click(fileButton)

    await waitFor(() => {
      expect(screen.getByText('文件预览失败。')).toBeInTheDocument()
    })
    // 失败时 Dialog 仍在（由 selectedPath 挂载，不随请求成败消失）
    expect(screen.getByRole('dialog', { name: 'train.py' })).toBeInTheDocument()
    expect(screen.getByText('网络异常')).toBeInTheDocument()
  })

  it('关闭预览后 Dialog 卸载', async () => {
    mockReadSharedResourceVersionFile.mockResolvedValue('content')

    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'train.py' }))
    await screen.findByRole('dialog', { name: 'train.py' })

    fireEvent.click(screen.getByRole('button', { name: '关闭' }))
    await waitFor(() => {
      expect(screen.queryByRole('dialog', { name: 'train.py' })).not.toBeInTheDocument()
    })
  })
})
