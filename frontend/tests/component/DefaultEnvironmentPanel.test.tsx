// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { Environment, UserGroup } from '../../src/api/types'
import { DefaultEnvironmentPanel } from '../../src/components/workspace/DefaultEnvironmentPanel'
import { PrimerRoot } from '../../src/primer/setup'

const group: UserGroup = {
  id: 'grp_lab',
  name: 'GPU Lab',
  description: '',
  default_environment_version_id: 'envv_python',
  created_by_id: 'usr_alice',
  created_at: '2026-08-26T00:00:00Z',
  role: 'owner',
  capabilities: ['user_group.view', 'user_group.update'],
}

const environments: Environment[] = [
  {
    id: 'env_python',
    name: 'Python',
    description: '',
    owner: { kind: 'user_group', id: 'grp_lab', display_name: 'GPU Lab' },
    versions: [
      {
        id: 'envv_python',
        environment_id: 'env_python',
        version: '3.12',
        description: '',
        image: 'python:3.12',
        setup_command: '',
        available: true,
      },
      {
        id: 'envv_python_retired',
        environment_id: 'env_python',
        version: '3.11',
        description: '',
        image: 'python:3.11',
        setup_command: '',
        available: false,
      },
    ],
  },
]

function renderPanel(userGroup: UserGroup = group) {
  const onUserGroupChanged = vi.fn()
  render(
    <MemoryRouter>
      <PrimerRoot>
        <DefaultEnvironmentPanel userGroup={userGroup} onUserGroupChanged={onUserGroupChanged} />
      </PrimerRoot>
    </MemoryRouter>,
  )
  return { onUserGroupChanged }
}

beforeEach(() => {
  vi.spyOn(api, 'environmentsForUserGroup').mockResolvedValue(environments)
  vi.spyOn(api, 'updateUserGroup').mockResolvedValue(group)
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('DefaultEnvironmentPanel', () => {
  it('shows and saves one exact available Environment Version', async () => {
    const { onUserGroupChanged } = renderPanel()

    const region = screen.getByRole('region', { name: '默认 Environment Version' })
    expect(await within(region).findByRole('link', { name: 'Python · 3.12' })).toHaveAttribute(
      'href',
      '/environment-versions/envv_python',
    )
    const select = within(region).getByRole('combobox', { name: '选择确定版本' })
    expect(within(select).getByRole('option', { name: '3.11（当前不可用）' })).toBeDisabled()

    fireEvent.change(select, { target: { value: '' } })
    fireEvent.click(within(region).getByRole('button', { name: '保存默认版本' }))

    await waitFor(() => {
      expect(api.updateUserGroup).toHaveBeenCalledWith('grp_lab', {
        default_environment_version_id: null,
      })
    })
    expect(onUserGroupChanged).toHaveBeenCalledOnce()
  })

  it('keeps members read-only when backend does not grant update capability', async () => {
    renderPanel({ ...group, role: 'member', capabilities: ['user_group.view'] })

    const region = screen.getByRole('region', { name: '默认 Environment Version' })
    expect(await within(region).findByRole('combobox', { name: '选择确定版本' })).toBeDisabled()
    expect(within(region).queryByRole('button', { name: '保存默认版本' })).toBeNull()
  })
})
