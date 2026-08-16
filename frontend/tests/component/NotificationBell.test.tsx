// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

import { api, ApiError } from '../../src/api/client'
import type { Notification, NotificationPage } from '../../src/api/types'
import { NotificationBell } from '../../src/components/notification/NotificationBell'
import { PrimerRoot } from '../../src/primer/setup'

function makeNotification(overrides: Partial<Notification> = {}): Notification {
  return {
    id: 'n-1',
    type: 'run_succeeded',
    title: 'Run「首次运行」已成功',
    body: '',
    mandatory: false,
    read_at: null,
    created_at: '2026-08-15T08:00:00Z',
    target_id: 'run-1',
    target_type: 'run',
    workspace_id: 'ws-1',
    ...overrides,
  }
}

function makePage(items: Notification[]): NotificationPage {
  return { items, total: items.length, page: 1, page_size: 30, has_more: false }
}

function renderBell(username = 'student') {
  return render(
    <MemoryRouter>
      <PrimerRoot>
        <NotificationBell username={username} />
      </PrimerRoot>
    </MemoryRouter>,
  )
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('NotificationBell 未读数轮询契约', () => {
  it('挂载时拉一次，30 秒后再拉一次', async () => {
    vi.useFakeTimers()
    try {
      const unread = vi.spyOn(api, 'unreadCount').mockResolvedValue(2)
      renderBell()

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(unread).toHaveBeenCalledTimes(1)

      await act(async () => {
        await vi.advanceTimersByTimeAsync(30_000)
      })
      expect(unread).toHaveBeenCalledTimes(2)
      expect(screen.getByRole('button', { name: '通知，2 条未读' })).toBeTruthy()
    } finally {
      vi.useRealTimers()
    }
  })

  it('未读数拉取失败不打扰用户：铃铛仍可访问', async () => {
    vi.spyOn(api, 'unreadCount').mockRejectedValue(new Error('boom'))
    renderBell()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '通知' })).toBeTruthy()
    })
  })
})

describe('NotificationBell 通知浮层', () => {
  it('展开后渲染列表：类型标签、链接指向通知目标', async () => {
    vi.spyOn(api, 'unreadCount').mockResolvedValue(1)
    vi.spyOn(api, 'listNotifications').mockResolvedValue(makePage([makeNotification()]))

    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知，1 条未读' }))

    const title = await screen.findByText('Run「首次运行」已成功')
    expect(title).toBeVisible()
    expect(screen.getByText('Run 成功')).toBeVisible()
    const link = screen.getByRole('link', { name: /首次运行/ })
    expect(link).toHaveAttribute('href', '/runs/run-1')
  })

  it('点击未读条目标记已读并刷新未读数', async () => {
    const unread = vi.spyOn(api, 'unreadCount').mockResolvedValue(1)
    const markOne = vi
      .spyOn(api, 'markNotificationRead')
      .mockImplementation(async () => Promise.resolve())
    vi.spyOn(api, 'listNotifications').mockResolvedValue(makePage([makeNotification()]))

    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知，1 条未读' }))
    await screen.findByText('Run「首次运行」已成功')

    fireEvent.click(screen.getByRole('link', { name: /首次运行/ }))
    await waitFor(() => expect(markOne).toHaveBeenCalledWith('n-1'))
    await waitFor(() => expect(unread.mock.calls.length).toBeGreaterThan(1))
  })

  it('标记已读失败在浮层内显示错误，不再弹全局提示', async () => {
    vi.spyOn(api, 'unreadCount').mockResolvedValue(1)
    vi.spyOn(api, 'listNotifications').mockResolvedValue(
      makePage([makeNotification({ target_id: null, target_type: null })]),
    )
    vi.spyOn(api, 'markNotificationRead').mockRejectedValue(
      new ApiError(500, 'internal_error', '标记已读失败。', [], 'req-42'),
    )

    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知，1 条未读' }))
    fireEvent.click(
      await screen.findByRole('button', { name: '将「Run「首次运行」已成功」标为已读' }),
    )

    expect(await screen.findByText('标记已读失败。')).toBeVisible()
  })

  it('无目标未读通知提供语义化标记操作，已读通知保持静态', async () => {
    const unread = makeNotification({ target_id: null, target_type: null })
    const read = makeNotification({
      id: 'n-2',
      title: '你已被移出 Workspace',
      target_id: null,
      target_type: null,
      read_at: '2026-08-15T09:00:00Z',
    })
    vi.spyOn(api, 'unreadCount').mockResolvedValue(1)
    vi.spyOn(api, 'listNotifications').mockResolvedValue(makePage([unread, read]))
    const markOne = vi.spyOn(api, 'markNotificationRead').mockResolvedValue(undefined)

    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知，1 条未读' }))

    const markButton = await screen.findByRole('button', {
      name: '将「Run「首次运行」已成功」标为已读',
    })
    expect(markButton).toBeVisible()
    expect(screen.queryByRole('button', { name: '将「你已被移出 Workspace」标为已读' })).toBeNull()

    fireEvent.click(markButton)
    await waitFor(() => expect(markOne).toHaveBeenCalledWith('n-1'))
  })

  it('全部标为已读失败同样就地显示', async () => {
    vi.spyOn(api, 'unreadCount').mockResolvedValue(1)
    vi.spyOn(api, 'listNotifications').mockResolvedValue(makePage([makeNotification()]))
    vi.spyOn(api, 'markAllNotificationsRead').mockRejectedValue(
      new ApiError(500, 'internal_error', '批量标记失败。', [], 'req-43'),
    )

    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知，1 条未读' }))
    fireEvent.click(await screen.findByRole('button', { name: '全部标为已读' }))

    expect(await screen.findByText('批量标记失败。')).toBeVisible()
  })
})
