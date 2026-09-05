// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Home } from '../../src/api/types'
import { PrimerRoot } from '../../src/primer/setup'
import { ProfilePage } from '../../src/pages/ProfilePage'

const homeData: Home = {
  user: { id: 'usr_abc', username: 'student', display_name: '同学', email: 'student@mail.ustc.edu.cn' },
  user_groups: [
    {
      id: 'grp-1',
      name: '计算物理课题组',
      description: '',
      created_by_id: 'usr_abc',
      created_at: '2026-08-15T10:00:00Z',
      role: 'owner',
      capabilities: [],
    },
  ],
  personal_execution_context: {
    owner: { kind: 'user', id: 'usr_abc', display_name: '同学' },
    entitlements: [],
  },
  recent_projects: [],
  recent_runs: [],
}

function renderProfile(home: Home = homeData) {
  return render(
    <MemoryRouter>
      <PrimerRoot>
        <ProfilePage
          home={{
            data: home,
            loading: false,
            error: undefined,
            reload: vi.fn(),
          }}
        />
      </PrimerRoot>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('个人资料页面', () => {
  it('只读展示身份、邮箱、用户 ID、所属 User Group 与执行上下文入口', () => {
    renderProfile()

    expect(screen.getByRole('heading', { name: '个人资料' })).toBeVisible()
    expect(screen.getByRole('heading', { name: '同学' })).toBeVisible()
    expect(screen.getByText('@student')).toBeVisible()
    expect(screen.getByText('student@mail.ustc.edu.cn')).toBeVisible()
    expect(screen.getByText('usr_abc')).toBeVisible()
    expect(screen.getByRole('link', { name: '进入 计算物理课题组' })).toHaveAttribute(
      'href',
      '/user-groups/grp-1',
    )
    expect(screen.getByText('所有者')).toBeVisible()
    expect(screen.getByRole('link', { name: '个人执行上下文' })).toHaveAttribute(
      'href',
      '/execution-context',
    )
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(screen.queryByRole('img')).toBeNull()
  })

  it('没有 User Group 时显示空状态', () => {
    renderProfile({ ...homeData, user_groups: [] })
    expect(screen.getByText('还没有加入 User Group')).toBeVisible()
  })

  it('复制用户 ID', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    renderProfile()

    fireEvent.click(screen.getByRole('button', { name: '复制用户 ID' }))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('usr_abc'))
    expect(await screen.findByText('已复制')).toBeVisible()
  })
})
