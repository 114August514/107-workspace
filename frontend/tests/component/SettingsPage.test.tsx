// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../src/api/client'
import type { Home } from '../../src/api/types'
import { PrimerRoot } from '../../src/primer/setup'
import { SettingsPage } from '../../src/pages/SettingsPage'

const homeData: Home = {
  user: { id: 'u-1', username: 'student', display_name: '同学', email: 'student@mail.ustc.edu.cn' },
  user_groups: [],
  personal_execution_context: {
    owner: { kind: 'user', id: 'u-1', display_name: '同学' },
    entitlements: [],
  },
  recent_projects: [],
  recent_runs: [],
}

function renderSettings(home: Home = homeData, reload = vi.fn()) {
  return render(
    <MemoryRouter>
      <PrimerRoot>
        <SettingsPage
          home={{
            data: home,
            loading: false,
            error: undefined,
            reload,
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

describe('设置页面', () => {
  it('展示可编辑的显示名称和用户名，邮箱只读说明', () => {
    renderSettings()
    expect(screen.getByRole('heading', { name: '设置' })).toBeVisible()
    expect(screen.getByRole('textbox', { name: /显示名称/ })).toHaveValue('同学')
    expect(screen.getByRole('textbox', { name: /用户名/ })).toHaveValue('student')
    expect(screen.getByText(/student@mail.ustc.edu.cn/)).toBeVisible()
    expect(screen.queryByRole('heading', { name: '个人执行上下文' })).toBeNull()
  })

  it('保存时提交显示名称和用户名并刷新当前用户', async () => {
    const reload = vi.fn()
    const updateProfile = vi.spyOn(api, 'updateProfile').mockResolvedValue({
      ...homeData.user,
      display_name: '新同学',
      username: 'student-2',
    })
    renderSettings(homeData, reload)

    fireEvent.change(screen.getByRole('textbox', { name: /显示名称/ }), {
      target: { value: '新同学' },
    })
    fireEvent.change(screen.getByRole('textbox', { name: /用户名/ }), {
      target: { value: 'student-2' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存设置' }))

    await waitFor(() =>
      expect(updateProfile).toHaveBeenCalledWith({
        display_name: '新同学',
        username: 'student-2',
      }),
    )
    expect(await screen.findByText('设置已保存。')).toBeVisible()
    expect(reload).toHaveBeenCalled()
  })
})
