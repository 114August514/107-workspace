// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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
it('可见范围在保存时才更新，并通知页面刷新', async () => {
  const update = vi
    .spyOn(api, 'updateProject')
    .mockResolvedValue({ ...project, visibility: 'public' })
  const changed = vi.fn()
  show(project, changed)
  const field = screen.getByRole('combobox', { name: '可见范围' })
  expect(field).toHaveValue('owner_scope')
  fireEvent.change(field, { target: { value: 'public' } })
  expect(update).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  await waitFor(() =>
    expect(update).toHaveBeenCalledWith('p', {
      name: 'Demo',
      description: '',
      visibility: 'public',
    }),
  )
  expect(await screen.findByText('Project 设置已保存。')).toBeVisible()
  expect(changed).toHaveBeenCalledOnce()
})
it('组拥有的项目可以从公开改回所属组范围，失败后保留输入以便重试', async () => {
  const update = vi
    .spyOn(api, 'updateProject')
    .mockRejectedValueOnce(new Error('保存失败'))
    .mockResolvedValue(project)
  show({
    ...project,
    owner: { kind: 'user_group', id: 'g', display_name: 'Group' },
    visibility: 'public',
  })
  expect(screen.getByRole('option', { name: '仅所属 User Group' })).toBeInTheDocument()
  fireEvent.change(screen.getByRole('combobox', { name: '可见范围' }), {
    target: { value: 'owner_scope' },
  })
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  expect(await screen.findByText('保存失败')).toBeVisible()
  expect(screen.getByRole('combobox', { name: '可见范围' })).toHaveValue('owner_scope')
  fireEvent.click(screen.getByRole('button', { name: '保存更改' }))
  await waitFor(() => expect(update).toHaveBeenCalledTimes(2))
})
it('没有修改权限时不能修改可见范围', () => {
  show({ ...project, capabilities: [] })
  expect(screen.getByRole('combobox', { name: '可见范围' })).toBeDisabled()
  expect(screen.queryByRole('button', { name: '保存更改' })).toBeNull()
})
