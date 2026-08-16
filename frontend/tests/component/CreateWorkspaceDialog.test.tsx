// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import { api, ApiError } from '../../src/api/client'
import type { Workspace } from '../../src/api/types'
import { CreateWorkspaceDialog } from '../../src/components/workspace/CreateWorkspaceDialog'
import { PrimerRoot } from '../../src/primer/setup'

function makeWorkspace(overrides: Partial<Workspace> = {}): Workspace {
  return {
    id: 'ws-new',
    name: '计算物理课题组',
    kind: 'collaborative',
    description: '',
    created_at: '2026-08-16T08:00:00Z',
    owner_id: 'student',
    role: 'owner',
    capabilities: [],
    default_environment_version_id: null,
    ...overrides,
  }
}

function renderDialog(onCreated = vi.fn(), onClose = vi.fn(), open = true) {
  render(
    <MemoryRouter>
      <PrimerRoot>
        <CreateWorkspaceDialog open={open} onClose={onClose} onCreated={onCreated} />
      </PrimerRoot>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('CreateWorkspaceDialog', () => {
  it('open=false 时不渲染', () => {
    renderDialog(vi.fn(), vi.fn(), false)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('名称为空时就地报表单错误，不请求接口', async () => {
    const create = vi.spyOn(api, 'createWorkspace')
    renderDialog()

    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    expect(await screen.findByText('请填写 Workspace 名称')).toBeVisible()
    expect(create).not.toHaveBeenCalled()
  })

  it('创建成功后把新空间交给调用方并关闭', async () => {
    const workspace = makeWorkspace()
    const created = vi.spyOn(api, 'createWorkspace').mockResolvedValue(workspace)
    const onCreated = vi.fn()
    const onClose = vi.fn()
    renderDialog(onCreated, onClose)

    fireEvent.change(screen.getByLabelText(/名称/), {
      target: { value: '计算物理课题组' },
    })
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(workspace))
    expect(onClose).toHaveBeenCalled()
    expect(created).toHaveBeenCalledWith('计算物理课题组', '')
  })

  it('说明填写了就随名称一起提交', async () => {
    const created = vi.spyOn(api, 'createWorkspace').mockResolvedValue(makeWorkspace())
    renderDialog()

    fireEvent.change(screen.getByLabelText(/名称/), { target: { value: 'A' } })
    fireEvent.change(screen.getByLabelText(/说明/), { target: { value: '课题组成果共享' } })
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(created).toHaveBeenCalledWith('A', '课题组成果共享'))
  })

  it('提交前检查错误逐条显示在弹窗内，弹窗不关闭', async () => {
    vi.spyOn(api, 'createWorkspace').mockRejectedValue(
      new ApiError(
        422,
        'validation_error',
        '创建失败，请修正后重试。',
        ['名称不能为空', '说明超过 500 字'],
        'req-9',
      ),
    )
    const onClose = vi.fn()
    renderDialog(vi.fn(), onClose)

    fireEvent.change(screen.getByLabelText(/名称/), { target: { value: 'A' } })
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    expect(await screen.findByText('创建失败，请修正后重试。')).toBeVisible()
    expect(screen.getByText('名称不能为空')).toBeVisible()
    expect(screen.getByText('说明超过 500 字')).toBeVisible()
    expect(onClose).not.toHaveBeenCalled()
  })
})
