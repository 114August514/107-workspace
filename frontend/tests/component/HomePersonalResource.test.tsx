// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { Home } from '../../src/api/types'
import { HomePage } from '../../src/pages/HomePage'
import { PrimerRoot } from '../../src/primer/setup'

function home(personalResourceContextId: string | null): Home {
  return {
    user: {
      id: 'usr_alice',
      username: 'alice',
      display_name: 'Alice',
      email: null,
    },
    user_groups: [],
    recent_projects: [],
    recent_runs: [],
    personal_resource_context_id: personalResourceContextId,
  }
}

describe('Home personal resource discovery', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('shows a normal personal resource entry for retained data without recent Projects', async () => {
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    render(
      <PrimerRoot>
        <MemoryRouter>
          <HomePage
            username="alice"
            home={{
              data: home('ws_personal_alice'),
              loading: false,
              error: undefined,
              reload: vi.fn(),
            }}
          />
        </MemoryRouter>
      </PrimerRoot>,
    )

    expect(await screen.findByRole('link', { name: '查看个人资源' })).toHaveAttribute(
      'href',
      '/workspaces/ws_personal_alice',
    )
    expect(document.body.textContent).not.toMatch(/旧|Workspace|Legacy|兼容/)
  })

  it('does not show the entry for a user without retained personal data', async () => {
    vi.spyOn(api, 'listInvitations').mockResolvedValue([])
    vi.spyOn(api, 'computePlans').mockResolvedValue([])

    render(
      <PrimerRoot>
        <MemoryRouter>
          <HomePage
            username="alice"
            home={{ data: home(null), loading: false, error: undefined, reload: vi.fn() }}
          />
        </MemoryRouter>
      </PrimerRoot>,
    )

    await screen.findByRole('heading', { name: 'Alice，欢迎回来' })
    expect(screen.queryByRole('link', { name: '查看个人资源' })).not.toBeInTheDocument()
  })
})
