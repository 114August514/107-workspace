// @vitest-environment jsdom

import { createRef } from 'react'
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import type { Home, Project, UserGroup } from '../../src/api/types'
import type { AsyncState } from '../../src/api/useAsync'
import { GlobalNavigationDrawer } from '../../src/components/layout/GlobalNavigationDrawer'
import { PrimerRoot } from '../../src/primer/setup'

function makeUserGroup(index: number): UserGroup {
  return {
    id: `group-${index}`,
    name: `User Group ${index}`,
    description: '',
    created_by_id: 'user-1',
    created_at: '2026-08-15T10:00:00Z',
    role: 'member',
    capabilities: [],
  }
}

function makeProject(index: number, workspaceId = `group-${index}`): Project {
  return {
    id: `project-${index}`,
    name: `Project ${index}`,
    description: '',
    workspace_id: workspaceId,
    owner: { kind: 'user_group', id: workspaceId, display_name: `Group ${index}` },
    visibility: 'owner_scope',
    status: 'active',
    created_by: 'user-1',
    created_at: '2026-08-15T10:00:00Z',
    updated_at: '2026-08-16T10:00:00Z',
    default_run_configuration_id: null,
    environment_version_id: null,
  }
}

function makeHome({
  userGroupCount = 7,
  projectCount = 7,
  personalResourceContextId = 'personal-1',
}: {
  userGroupCount?: number
  projectCount?: number
  personalResourceContextId?: string | null
} = {}): Home {
  return {
    user: { id: 'user-1', username: 'student', display_name: '同学' },
    user_groups: Array.from({ length: userGroupCount }, (_, index) => makeUserGroup(index + 1)),
    personal_resource_context_id: personalResourceContextId,
    recent_projects: Array.from({ length: projectCount }, (_, index) => makeProject(index + 1)),
    recent_runs: [],
  }
}

function readyHome(data: Home): AsyncState<Home> {
  return { data, loading: false, error: undefined, reload: vi.fn() }
}

function renderDrawer(home: Home, initialEntry = '/') {
  const returnFocusRef = createRef<HTMLButtonElement>()
  const onClose = vi.fn()
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <PrimerRoot>
        <button ref={returnFocusRef}>打开导航</button>
        <GlobalNavigationDrawer
          id="global-navigation"
          home={readyHome(home)}
          returnFocusRef={returnFocusRef}
          onClose={onClose}
        />
      </PrimerRoot>
    </MemoryRouter>,
  )
  return { onClose }
}

function hrefs(container: HTMLElement, prefix: string) {
  return within(container)
    .getAllByRole('link')
    .map((link) => link.getAttribute('href'))
    .filter((href): href is string => href?.startsWith(prefix) ?? false)
}

afterEach(cleanup)

describe('GlobalNavigationDrawer', () => {
  it('使用独立全局信息架构，按后端顺序展示前五项并可展开剩余项', async () => {
    renderDrawer(makeHome())

    const dialog = await screen.findByRole('dialog', { name: '107 Workspace' })
    expect(within(dialog).getByRole('navigation', { name: '全局导航' })).toBeVisible()
    expect(within(dialog).getByRole('heading', { name: '你的 User Group' })).toBeVisible()
    expect(within(dialog).getByRole('heading', { name: '最近使用的 Project' })).toBeVisible()
    expect(hrefs(dialog, '/user-groups/')).toEqual([
      '/user-groups/group-1',
      '/user-groups/group-2',
      '/user-groups/group-3',
      '/user-groups/group-4',
      '/user-groups/group-5',
    ])
    expect(hrefs(dialog, '/projects/')).toEqual([
      '/projects/project-1',
      '/projects/project-2',
      '/projects/project-3',
      '/projects/project-4',
      '/projects/project-5',
    ])
    expect(within(dialog).queryByRole('link', { name: /User Group 6/ })).toBeNull()
    expect(within(dialog).queryByRole('link', { name: /Project 6/ })).toBeNull()
    expect(dialog).not.toHaveTextContent('Run')
    expect(dialog).not.toHaveTextContent('Activity')

    const moreUserGroups = within(dialog).getByRole('button', {
      name: '显示其余 2 个 User Group',
    })
    expect(moreUserGroups).toHaveTextContent('显示其余 2 个')
    fireEvent.click(moreUserGroups)
    expect(hrefs(dialog, '/user-groups/')).toEqual(
      Array.from({ length: 7 }, (_, index) => `/user-groups/group-${index + 1}`),
    )
    expect(within(dialog).queryByRole('button', { name: /User Group/ })).toBeNull()

    const moreProjects = within(dialog).getByRole('button', {
      name: '显示其余 2 个 Project',
    })
    expect(moreProjects).toHaveTextContent('显示其余 2 个')
    fireEvent.click(moreProjects)
    expect(hrefs(dialog, '/projects/')).toEqual(
      Array.from({ length: 7 }, (_, index) => `/projects/project-${index + 1}`),
    )
    expect(within(dialog).queryByRole('button', { name: /Project/ })).toBeNull()
  })

  it('只在后端提供个人资源上下文时显示入口，并标记唯一的当前 route', async () => {
    const home = makeHome({ projectCount: 3 })
    home.recent_projects[1] = makeProject(2, 'personal-1')
    renderDrawer(home, '/projects/project-2')

    const dialog = await screen.findByRole('dialog', { name: '107 Workspace' })
    expect(within(dialog).getByRole('link', { name: '个人资源' })).toHaveAttribute(
      'href',
      '/workspaces/personal-1',
    )
    const personalProject = within(dialog).getByRole('link', { name: /Project 2/ })
    expect(personalProject).toHaveTextContent('个人资源')
    const currentLinks = within(dialog)
      .getAllByRole('link')
      .filter((link) => link.getAttribute('aria-current') === 'page')
    expect(currentLinks).toEqual([personalProject])
  })

  it('没有个人资源上下文时不显示个人资源入口', async () => {
    renderDrawer(makeHome({ personalResourceContextId: null }))

    const dialog = await screen.findByRole('dialog', { name: '107 Workspace' })
    expect(within(dialog).queryByRole('link', { name: '个人资源' })).toBeNull()
  })
})
