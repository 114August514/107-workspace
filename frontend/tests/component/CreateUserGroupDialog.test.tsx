// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import { api, ApiError } from '../../src/api/client'
import type { UserGroup } from '../../src/api/types'
import { CreateUserGroupDialog } from '../../src/components/workspace/CreateUserGroupDialog'
import { PrimerRoot } from '../../src/primer/setup'

function makeUserGroup(overrides: Partial<UserGroup> = {}): UserGroup {
  return {
    id: 'grp-new',
    name: '计算物理课题组',
    description: '',
    created_at: '2026-08-16T08:00:00Z',
    created_by_id: 'student',
    role: 'owner',
    capabilities: [],
    ...overrides,
  }
}

function renderDialog(onCreated = vi.fn(), onClose = vi.fn(), open = true) {
  render(
    <MemoryRouter>
      <PrimerRoot>
        <CreateUserGroupDialog open={open} onClose={onClose} onCreated={onCreated} />
      </PrimerRoot>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('CreateUserGroupDialog', () => {
  it('open=false 时不渲染', () => {
    renderDialog(vi.fn(), vi.fn(), false)
    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('打开时名称输入框获得焦点', async () => {
    renderDialog()
    await waitFor(() => expect(screen.getByRole('textbox', { name: /名称/ })).toHaveFocus())
  })

  it('说明字段提供可选标记、用途提示和适合长文本的尺寸', () => {
    renderDialog()

    const description = screen.getByRole('textbox', { name: '说明（可选）' })
    expect(description).toHaveAttribute('placeholder', '例如：用于计算物理课题组的课程项目')
    expect(description).toHaveAttribute('rows', '4')
    expect(description).toHaveAttribute('maxlength', '500')
    expect(screen.getByText('简要写明这个 User Group 用于哪些 Project 或协作任务。')).toBeVisible()
  })

  it('名称为空时就地报表单错误并将焦点留在名称输入框', async () => {
    const create = vi.spyOn(api, 'createUserGroup')
    renderDialog()

    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    expect(await screen.findByText('请填写 User Group 名称')).toBeVisible()
    expect(screen.getByRole('textbox', { name: /名称/ })).toHaveFocus()
    expect(create).not.toHaveBeenCalled()
  })

  it('创建成功后把新 User Group 交给调用方并关闭', async () => {
    const userGroup = makeUserGroup()
    const created = vi.spyOn(api, 'createUserGroup').mockResolvedValue(userGroup)
    const onCreated = vi.fn()
    const onClose = vi.fn()
    renderDialog(onCreated, onClose)

    fireEvent.change(screen.getByLabelText(/名称/), {
      target: { value: '计算物理课题组' },
    })
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(userGroup))
    expect(onClose).toHaveBeenCalled()
    expect(created).toHaveBeenCalledWith('计算物理课题组', '')
  })

  it('说明填写了就随名称一起提交', async () => {
    const created = vi.spyOn(api, 'createUserGroup').mockResolvedValue(makeUserGroup())
    renderDialog()

    fireEvent.change(screen.getByLabelText(/名称/), { target: { value: 'A' } })
    fireEvent.change(screen.getByLabelText(/说明/), { target: { value: '课题组成果共享' } })
    fireEvent.click(screen.getByRole('button', { name: '创建' }))

    await waitFor(() => expect(created).toHaveBeenCalledWith('A', '课题组成果共享'))
  })

  it('提交前检查错误逐条显示在弹窗内，弹窗不关闭', async () => {
    vi.spyOn(api, 'createUserGroup').mockRejectedValue(
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
