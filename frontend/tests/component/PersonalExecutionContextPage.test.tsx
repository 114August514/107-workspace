// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError } from '../../src/api/client'
import { ProductRoutes } from '../../src/App'
import type { Home } from '../../src/api/types'
import type { AsyncState } from '../../src/api/useAsync'
import { PersonalExecutionContextPage } from '../../src/pages/PersonalExecutionContextPage'
import { PrimerRoot } from '../../src/primer/setup'

const home: Home = {
  user: { id: 'usr_alice', username: 'alice', display_name: 'Alice' },
  user_groups: [],
  personal_execution_context: {
    owner: { kind: 'user', id: 'usr_alice', display_name: 'Alice' },
    entitlements: [
      {
        id: 'ent_1',
        compute_plan_id: 'plan_cpu',
        compute_plan_name: 'CPU 教学',
        expires_at: '2026-08-01T00:00:00+00:00',
        status: 'expired',
        status_reason: '权益已于 2026-08-01T00:00:00+00:00 过期',
      },
    ],
  },
  recent_projects: [],
  recent_runs: [],
}

function readyHome(data: Home = home): AsyncState<Home> {
  return { data, loading: false, error: undefined, reload: vi.fn() }
}

function renderPage(homeState = readyHome()) {
  return render(
    <MemoryRouter>
      <PrimerRoot>
        <PersonalExecutionContextPage username="alice" home={homeState} />
      </PrimerRoot>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderProductRoute() {
  const project: AsyncState<undefined> = {
    data: undefined,
    loading: false,
    error: undefined,
    reload: vi.fn(),
  }
  return render(
    <MemoryRouter initialEntries={['/execution-context']}>
      <PrimerRoot>
        <ProductRoutes username="alice" home={readyHome()} project={project} />
      </PrimerRoot>
    </MemoryRouter>,
  )
}

describe('PersonalExecutionContextPage #49', () => {
  it('由产品路由直接到达页面', async () => {
    vi.spyOn(api, 'listUserVariables').mockResolvedValue([])
    vi.spyOn(api, 'listUserSecrets').mockResolvedValue([])
    renderProductRoute()

    expect(screen.getByRole('heading', { name: '个人执行上下文' })).toBeVisible()
  })

  it('展示身份、服务端过期原因、引用边界与 Snapshot 不变说明', async () => {
    vi.spyOn(api, 'listUserVariables').mockResolvedValue([])
    vi.spyOn(api, 'listUserSecrets').mockResolvedValue([])
    renderPage()

    expect(screen.getByRole('heading', { name: '个人执行上下文' })).toBeVisible()
    expect(screen.getByText('@alice')).toBeVisible()
    expect(screen.getByText('CPU 教学')).toBeVisible()
    expect(screen.getByText(/权益已于 .* 过期/)).toBeVisible()
    expect(screen.getByText('${{ user.vars.NAME }}')).toBeVisible()
    expect(screen.getByText('${{ user.secrets.NAME }}')).toBeVisible()
    expect(screen.getByText(/Project Owner/)).toBeVisible()
    expect(screen.getByText(/不会回写已有 Run Snapshot/)).toBeVisible()
  })

  it('无权益时给出明确原因，配置列表有独立 loading 和 error', async () => {
    let resolveVariables!: (value: []) => void
    const pendingVariables = new Promise<[]>((resolve) => {
      resolveVariables = resolve
    })
    vi.spyOn(api, 'listUserVariables').mockReturnValue(pendingVariables)
    vi.spyOn(api, 'listUserSecrets').mockRejectedValue(
      new ApiError(500, 'internal_error', 'Secret 加载失败。', []),
    )
    renderPage(
      readyHome({
        ...home,
        personal_execution_context: { ...home.personal_execution_context, entitlements: [] },
      }),
    )

    expect(screen.getByText('当前没有 Resource Entitlement')).toBeVisible()
    expect(screen.getByText(/无法选择 Compute Plan 提交 Run/)).toBeVisible()
    expect(screen.getByText('正在加载 User Variables…')).toBeVisible()
    expect(await screen.findByText('Secret 加载失败。')).toBeVisible()
    resolveVariables([])
  })

  it('完成 Variable 新建、更新与删除', async () => {
    const list = vi
      .spyOn(api, 'listUserVariables')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ name: 'THREADS', value: '8' }])
      .mockResolvedValue([{ name: 'THREADS', value: '16' }])
    const setVariable = vi
      .spyOn(api, 'setUserVariable')
      .mockResolvedValueOnce({ name: 'THREADS', value: '8' })
      .mockResolvedValueOnce({ name: 'THREADS', value: '16' })
    const deleteVariable = vi.spyOn(api, 'deleteUserVariable').mockResolvedValue()
    vi.spyOn(api, 'listUserSecrets').mockResolvedValue([])
    renderPage()

    fireEvent.change(await screen.findByLabelText('Variable 名称'), {
      target: { value: 'THREADS' },
    })
    fireEvent.change(screen.getByLabelText('Variable 值'), { target: { value: '8' } })
    fireEvent.click(screen.getByRole('button', { name: '创建 Variable' }))
    await screen.findByText('THREADS')
    expect(setVariable).toHaveBeenCalledWith('usr_alice', { name: 'THREADS', value: '8' })

    fireEvent.click(screen.getByRole('button', { name: '编辑 THREADS' }))
    fireEvent.change(screen.getByLabelText('Variable 值'), { target: { value: '16' } })
    fireEvent.click(screen.getByRole('button', { name: '保存 Variable' }))
    await waitFor(() =>
      expect(setVariable).toHaveBeenLastCalledWith('usr_alice', {
        name: 'THREADS',
        value: '16',
      }),
    )

    fireEvent.click(screen.getByRole('button', { name: '删除 THREADS Variable' }))
    await waitFor(() => expect(deleteVariable).toHaveBeenCalledWith('usr_alice', 'THREADS'))
    expect(list).toHaveBeenCalled()
  })

  it('Secret 只展示名称，替换成功后从 DOM 和输入状态移除明文', async () => {
    vi.spyOn(api, 'listUserVariables').mockResolvedValue([])
    vi.spyOn(api, 'listUserSecrets').mockResolvedValueOnce(['TOKEN']).mockResolvedValue(['TOKEN'])
    const setSecret = vi.spyOn(api, 'setUserSecret').mockResolvedValue()
    const deleteSecret = vi.spyOn(api, 'deleteUserSecret').mockResolvedValue()
    renderPage()

    const secretSection = await screen.findByRole('region', { name: 'User Secrets' })
    expect(within(secretSection).getByText('TOKEN')).toBeVisible()
    fireEvent.click(within(secretSection).getByRole('button', { name: '替换或轮换 TOKEN' }))
    const valueInput = screen.getByLabelText('Secret 值') as HTMLInputElement
    fireEvent.change(valueInput, { target: { value: 'plaintext-never-render' } })
    fireEvent.click(screen.getByRole('button', { name: '替换 / 轮换 Secret' }))

    await waitFor(() =>
      expect(setSecret).toHaveBeenCalledWith('usr_alice', {
        name: 'TOKEN',
        value: 'plaintext-never-render',
      }),
    )
    await waitFor(() => expect(valueInput.value).toBe(''))
    expect(document.body).not.toHaveTextContent('plaintext-never-render')

    fireEvent.click(within(secretSection).getByRole('button', { name: '删除 TOKEN Secret' }))
    await waitFor(() => expect(deleteSecret).toHaveBeenCalledWith('usr_alice', 'TOKEN'))
  })
})
