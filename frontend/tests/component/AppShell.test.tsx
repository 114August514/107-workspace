// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import { api } from '../../src/api/client'
import { AppShell } from '../../src/components/layout/AppShell'
import { PrimerRoot } from '../../src/primer/setup'

function renderShell(username: string) {
  return render(
    <MemoryRouter>
      <PrimerRoot>
        <AppShell username={username} onUsernameChange={() => {}}>
          <p>页面内容</p>
        </AppShell>
      </PrimerRoot>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('AppShell 壳层', () => {
  it('品牌链接指向首页，页脚保留平台口径说明', () => {
    renderShell('student')
    expect(screen.getByRole('link', { name: '107 Workspace' })).toHaveAttribute('href', '/')
    expect(screen.getByText('GPU 型号、分区、QoS 和配额等信息以平台页面为准。')).toBeVisible()
  })

  it('顶栏创建按钮打开创建协作空间弹窗', async () => {
    renderShell('student')
    fireEvent.click(screen.getByRole('button', { name: '创建协作空间' }))
    expect(await screen.findByRole('dialog')).toBeVisible()
    expect(screen.getByText('创建协作空间', { selector: 'h1' })).toBeTruthy()
  })

  it('身份切换器展示当前身份并展开可选身份', async () => {
    renderShell('student')
    fireEvent.click(screen.getByRole('button', { name: '切换身份，当前 student' }))
    expect(await screen.findByRole('menuitem', { name: 'teacher' })).toBeVisible()
  })
})

describe('AppShell 身份切换的乱序防护', () => {
  it('旧身份迟到的未读数不能盖掉新身份刚拉到的数字', async () => {
    let calls = 0
    let resolveFirst!: (n: number) => void
    vi.spyOn(api, 'unreadCount').mockImplementation(() => {
      calls += 1
      if (calls === 1) {
        // student 的请求在网络上悬着，等身份已切换到 teacher 后才返回
        return new Promise<number>((resolve) => {
          resolveFirst = resolve
        })
      }
      return Promise.resolve(7)
    })

    const { rerender } = renderShell('student')
    rerender(
      <MemoryRouter>
        <PrimerRoot>
          <AppShell username="teacher" onUsernameChange={() => {}}>
            <p>页面内容</p>
          </AppShell>
        </PrimerRoot>
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '通知，7 条未读' })).toBeTruthy()
    })

    // student 的响应这时才落地：key 重挂载已丢弃旧实例，这声 setState 不该生效
    await act(async () => {
      resolveFirst(3)
    })
    expect(screen.getByRole('button', { name: '通知，7 条未读' })).toBeTruthy()
  })
})
