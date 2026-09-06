// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../../src/api/client'
import type { Project } from '../../src/api/types'
import { ProjectSettingsPanel } from '../../src/components/project/ProjectSettingsPanel'

const project: Project = {
  id: 'p',
  name: 'Demo',
  description: '',
  status: 'active',
  visibility: 'owner_scope',
  owner: { kind: 'user', id: 'u', display_name: 'User' },
  environment_version_id: null,
  default_run_configuration_id: null,
  capabilities: ['project.update'],
  created_by: 'u',
  created_at: null,
  updated_at: null,
}
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})
function show(access = project, onChanged = vi.fn()) {
  render(
    <MemoryRouter>
      <ProjectSettingsPanel projectId={access.id} access={access} onChanged={onChanged} />
    </MemoryRouter>,
  )
}
it.each(['user', 'user_group'] as const)('%s 拥有的项目经独立确认后才能公开', async (kind) => {
  const access = { ...project, owner: { ...project.owner, kind } }
  const update = vi
    .spyOn(api, 'updateProject')
    .mockResolvedValue({ ...access, visibility: 'public' })
  const changed = vi.fn()
  show(access, changed)
  const danger = screen.getByRole('region', { name: '危险操作' })
  fireEvent.click(within(danger).getByRole('button', { name: '更改可见范围' }))
  const dialog = await screen.findByRole('alertdialog')
  expect(within(dialog).getByText(/所有已登录用户/)).toBeVisible()
  expect(update).not.toHaveBeenCalled()
  fireEvent.click(within(dialog).getByRole('button', { name: '取消' }))
  expect(update).not.toHaveBeenCalled()
  fireEvent.click(within(danger).getByRole('button', { name: '更改可见范围' }))
  fireEvent.click(screen.getByRole('button', { name: '确认改为平台公开' }))
  await waitFor(() => expect(update).toHaveBeenCalledWith('p', { visibility: 'public' }))
  expect(await screen.findByText('当前：平台公开')).toBeVisible()
  expect(changed).toHaveBeenCalledOnce()
})
it('组项目可改回所属组范围，失败后保留确认弹窗并可重试', async () => {
  const access: Project = {
    ...project,
    owner: { kind: 'user_group', id: 'g', display_name: 'Group' },
    visibility: 'public',
  }
  const update = vi
    .spyOn(api, 'updateProject')
    .mockRejectedValueOnce(new Error('保存失败'))
    .mockResolvedValue({ ...access, visibility: 'owner_scope' })
  show(access)
  fireEvent.click(screen.getByRole('button', { name: '更改可见范围' }))
  expect(screen.getByText(/已有 Fork 是独立项目/)).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '确认改为仅所属 User Group' }))
  expect(await screen.findByText('保存失败')).toBeVisible()
  expect(screen.getByRole('alertdialog')).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: '确认改为仅所属 User Group' }))
  expect(await screen.findByText('当前：仅所属 User Group')).toBeVisible()
  expect(update).toHaveBeenLastCalledWith('p', { visibility: 'owner_scope' })
})
it('没有修改权限时只显示当前可见范围', () => {
  show({ ...project, capabilities: [] })
  expect(screen.getByText('当前：仅自己')).toBeVisible()
  expect(screen.queryByRole('button', { name: '更改可见范围' })).toBeNull()
})
