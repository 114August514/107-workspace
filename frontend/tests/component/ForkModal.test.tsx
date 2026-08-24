// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type {
  LegacyWorkspaceContext,
  Project,
  ProjectVersion,
  UserGroup,
} from '../../src/api/types'
import { ForkModal } from '../../src/components/project/ForkModal'

const version: ProjectVersion = {
  id: 'pv_source',
  project_id: 'prj_source',
  label: 'v1',
  sequence: 1,
  message: 'initial',
  file_count: 1,
  total_size: 10,
  created_by: 'alice',
  created_at: '2026-08-17T00:00:00Z',
}

const groups: UserGroup[] = [
  {
    id: 'grp_writer',
    name: 'Writer Lab',
    description: '',
    created_by_id: 'usr_alice',
    created_at: '2026-08-17T00:00:00Z',
    role: 'member',
    capabilities: ['user_group.view', 'member.view'],
  },
  {
    id: 'grp_read_only',
    name: 'Read-only Lab',
    description: '',
    created_by_id: 'usr_bob',
    created_at: '2026-08-17T00:00:00Z',
    role: 'member',
    capabilities: ['user_group.view', 'member.view'],
  },
]

function context(group: UserGroup, capabilities: LegacyWorkspaceContext['capabilities']) {
  return {
    id: group.id,
    kind: 'collaborative' as const,
    name: group.name,
    owner_id: group.created_by_id ?? '',
    default_environment_version_id: null,
    role: group.role,
    capabilities,
  }
}

function renderModal() {
  return render(
    <ForkModal
      open
      version={version}
      sourceProjectName="Source Project"
      onClose={vi.fn()}
      onForked={vi.fn()}
    />,
  )
}

describe('ForkModal target eligibility', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('uses transitional target context and submits the selected eligible target', async () => {
    vi.spyOn(api, 'listUserGroups').mockResolvedValue(groups)
    vi.spyOn(api, 'getLegacyWorkspaceContext').mockImplementation(async (id) => {
      const group = groups.find((item) => item.id === id)
      if (!group) throw new Error('missing group')
      return context(
        group,
        id === 'grp_writer'
          ? ['user_group.view', 'project.view', 'project.create']
          : ['user_group.view', 'project.view'],
      )
    })
    const created: Project = {
      id: 'prj_forked',
      workspace_id: 'grp_writer',
      owner: { kind: 'user_group', id: 'grp_writer', display_name: 'Writer Lab' },
      visibility: 'owner_scope',
      name: 'Source Project',
      description: '',
      status: 'active',
      environment_version_id: null,
      default_run_configuration_id: null,
      created_by: 'alice',
      created_at: null,
      updated_at: null,
    }
    const fork = vi.spyOn(api, 'forkVersion').mockResolvedValue(created)

    renderModal()

    const target = await screen.findByRole('combobox', { name: '创建到哪个 User Group' })
    fireEvent.mouseDown(target)
    fireEvent.click(await screen.findByText('Writer Lab'))
    expect(screen.queryByText('Read-only Lab')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /创\s*建/ }))
    await waitFor(() =>
      expect(fork).toHaveBeenCalledWith('pv_source', {
        target_workspace_id: 'grp_writer',
        name: 'Source Project',
        description: '',
      }),
    )
  })

  it('shows a load failure instead of falling back when an anchor is missing', async () => {
    vi.spyOn(api, 'listUserGroups').mockResolvedValue(groups)
    vi.spyOn(api, 'getLegacyWorkspaceContext').mockRejectedValue(
      new Error('required target context is missing'),
    )

    renderModal()

    expect(await screen.findByText('无法加载可创建 Project 的 User Group')).toBeInTheDocument()
    expect(screen.queryByText('Writer Lab')).not.toBeInTheDocument()
  })
})
