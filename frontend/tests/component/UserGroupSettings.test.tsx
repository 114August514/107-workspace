// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { UserGroup } from '../../src/api/types'
import { OverviewSection } from '../../src/components/usergroup/OverviewSection'
import { SettingsSection } from '../../src/components/usergroup/SettingsSection'
import { UserGroupPage } from '../../src/pages/UserGroupPage'

const group: UserGroup = {
  id: 'grp_lab',
  name: 'Research Lab',
  description: 'Original description',
  created_by_id: 'usr_alice',
  created_at: '2026-08-17T00:00:00Z',
  role: 'owner',
  capabilities: ['user_group.view', 'user_group.update', 'member.view'],
}

function renderSettings(groupFixture: UserGroup = group) {
  vi.spyOn(api, 'getUserGroup').mockResolvedValue(groupFixture)
  return render(
    <MemoryRouter initialEntries={['/user-groups/grp_lab/settings']}>
      <Routes>
        <Route path="/user-groups/:userGroupId" element={<UserGroupPage />}>
          <Route path="settings" element={<SettingsSection />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  )
}

describe('User Group 设置分区', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('REQ-21-16 表单以当前名称与说明初始化并提交 trim 后的值', async () => {
    const update = vi
      .spyOn(api, 'updateUserGroup')
      .mockResolvedValue({ ...group, name: 'New Lab', description: 'New description' })
    renderSettings()

    const nameInput = (await screen.findByLabelText(/名称/)) as HTMLInputElement
    expect(nameInput.value).toBe('Research Lab')

    fireEvent.change(nameInput, { target: { value: '  New Lab  ' } })
    fireEvent.change(screen.getByLabelText(/说明/), { target: { value: '  New description  ' } })
    fireEvent.click(screen.getByRole('button', { name: '保存设置' }))

    await screen.findByText('User Group 设置已保存。')
    expect(update).toHaveBeenCalledWith('grp_lab', {
      name: 'New Lab',
      description: 'New description',
    })
  })

  it('REQ-21-17 保存成功后重新拉取 User Group 刷新页面头部', async () => {
    vi.spyOn(api, 'updateUserGroup').mockResolvedValue(group)
    vi.spyOn(api, 'getUserGroup').mockResolvedValue(group)
    renderSettings()

    await screen.findByLabelText(/名称/)
    fireEvent.click(screen.getByRole('button', { name: '保存设置' }))
    await screen.findByText('User Group 设置已保存。')

    expect(api.getUserGroup).toHaveBeenCalledTimes(2)
  })

  it('REQ-21-18 名称为空时校验失败且不发出请求', async () => {
    const update = vi.spyOn(api, 'updateUserGroup')
    renderSettings()

    const nameInput = await screen.findByLabelText(/名称/)
    fireEvent.change(nameInput, { target: { value: '   ' } })
    fireEvent.click(screen.getByRole('button', { name: '保存设置' }))

    expect(await screen.findByText('名称不能为空')).toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()
  })

  it('REQ-21-19 保存失败时展示稳定错误文案且可重试', async () => {
    const update = vi
      .spyOn(api, 'updateUserGroup')
      .mockRejectedValueOnce(new Error('forbidden'))
      .mockResolvedValueOnce(group)
    renderSettings()

    await screen.findByLabelText(/名称/)
    fireEvent.click(screen.getByRole('button', { name: '保存设置' }))

    expect(await screen.findByText('保存失败。')).toBeInTheDocument()
    expect(screen.queryByText('forbidden')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '保存设置' }))
    await screen.findByText('User Group 设置已保存。')
    expect(update).toHaveBeenCalledTimes(2)
  })

  it('REQ-21-20 Member 直达设置 URL 被重定向回概览且不渲染表单', async () => {
    const memberGroup: UserGroup = {
      ...group,
      role: 'member',
      capabilities: ['user_group.view', 'member.view'],
    }
    vi.spyOn(api, 'getUserGroup').mockResolvedValue(memberGroup)
    vi.spyOn(api, 'listMembers').mockResolvedValue([])
    vi.spyOn(api, 'listUserGroupActivities').mockResolvedValue({
      items: [],
      page: 1,
      page_size: 10,
      total: 0,
      has_more: false,
    })
    render(
      <MemoryRouter initialEntries={['/user-groups/grp_lab/settings']}>
        <Routes>
          <Route path="/user-groups/:userGroupId" element={<UserGroupPage />}>
            <Route index element={<OverviewSection />} />
            <Route path="settings" element={<SettingsSection />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: '基本信息' })).toBeInTheDocument()
    expect(screen.queryByLabelText(/名称/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '保存设置' })).not.toBeInTheDocument()
  })
})
