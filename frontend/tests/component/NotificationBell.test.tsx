// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router-dom'

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
    ...overrides,
  }
}

function makePage(items: Notification[]): NotificationPage {
  return { items, total: items.length, page: 1, page_size: 30, has_more: false }
}
function LocationProbe() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}</output>
}

function renderBell(username = 'student') {
  return render(
    <MemoryRouter>
      <PrimerRoot>
        <NotificationBell username={username} />
        <LocationProbe />
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

  it('全部标为已读触发刷新后，旧的未读请求不能恢复徽标', async () => {
    let resolveFirst!: (count: number) => void
    let calls = 0
    vi.spyOn(api, 'unreadCount').mockImplementation(() => {
      calls += 1
      if (calls === 1)
        return new Promise<number>((resolve) => {
          resolveFirst = resolve
        })
      return Promise.resolve(0)
    })
    vi.spyOn(api, 'listNotifications').mockResolvedValue(makePage([makeNotification()]))
    vi.spyOn(api, 'markAllNotificationsRead').mockResolvedValue(undefined)

    renderBell()
    fireEvent.click(screen.getByRole('button', { name: '通知' }))
    fireEvent.click(await screen.findByRole('button', { name: '全部标为已读' }))
    await waitFor(() => expect(calls).toBeGreaterThan(1))
    await act(async () => resolveFirst(3))
    expect(screen.queryByRole('button', { name: '通知，3 条未读' })).toBeNull()
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

  it.each([
    ['user_group_invited', '你收到一个 User Group 邀请'],
    ['member_removed', '你已被移出 User Group'],
  ] as const)('%s 通知没有不可访问的导航链接', async (type, title) => {
    vi.spyOn(api, 'unreadCount').mockResolvedValue(1)
    vi.spyOn(api, 'listNotifications').mockResolvedValue(
      makePage([
        makeNotification({
          type,
          title,
          target_id: null,
          target_type: null,
        }),
      ]),
    )

    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知，1 条未读' }))

    expect(await screen.findByText(title)).toBeVisible()
    expect(screen.queryByRole('link', { name: title })).not.toBeInTheDocument()
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

  it('linked unread success navigates and closes the overlay', async () => {
    vi.spyOn(api, 'unreadCount').mockResolvedValue(1)
    vi.spyOn(api, 'listNotifications').mockResolvedValue(makePage([makeNotification()]))
    const markOne = vi.spyOn(api, 'markNotificationRead').mockResolvedValue(undefined)
    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知，1 条未读' }))
    fireEvent.click(await screen.findByRole('link', { name: /首次运行/ }))
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/runs/run-1'))
    expect(markOne).toHaveBeenCalledWith('n-1')
    expect(screen.queryByText('通知')).toBeNull()
  })

  it('linked unread failure still navigates and closes the overlay', async () => {
    vi.spyOn(api, 'unreadCount').mockResolvedValue(1)
    vi.spyOn(api, 'listNotifications').mockResolvedValue(makePage([makeNotification()]))
    const markOne = vi
      .spyOn(api, 'markNotificationRead')
      .mockRejectedValue(new ApiError(500, 'internal_error', '标记已读失败。', [], 'req-44'))
    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知，1 条未读' }))
    fireEvent.click(await screen.findByRole('link', { name: /首次运行/ }))
    await waitFor(() => expect(markOne).toHaveBeenCalledWith('n-1'))
    expect(screen.getByTestId('location')).toHaveTextContent('/runs/run-1')
    expect(screen.queryByText('通知')).toBeNull()
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
    expect(screen.getByTestId('location')).toHaveTextContent('/')
    expect(screen.getByText('通知')).toBeVisible()
  })

  it('无目标未读通知提供语义化标记操作，已读通知保持静态', async () => {
    const unread = makeNotification({ target_id: null, target_type: null })
    const read = makeNotification({
      id: 'n-2',
      title: '你已被移出 User Group',
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
    expect(screen.queryByRole('button', { name: '将「你已被移出 User Group」标为已读' })).toBeNull()

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
  it('通知设置使用类别标签并标明重要通知不可关闭', async () => {
    vi.spyOn(api, 'unreadCount').mockResolvedValue(0)
    vi.spyOn(api, 'listNotifications').mockResolvedValue(makePage([]))
    const setPreference = vi.spyOn(api, 'setNotificationPreference').mockResolvedValue({
      type: 'run_succeeded',
      enabled: false,
      mandatory: false,
    })
    vi.spyOn(api, 'listNotificationPreferences').mockResolvedValue([
      { type: 'run_succeeded', enabled: true, mandatory: false },
      { type: 'member_removed', enabled: true, mandatory: true },
    ])

    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知' }))
    fireEvent.click(await screen.findByRole('button', { name: '通知设置' }))

    expect(await screen.findByText('Run 成功')).toBeVisible()
    expect(screen.getByText('成员变动')).toBeVisible()
    expect(screen.getByText('始终开启')).toBeVisible()
    expect(screen.getByRole('checkbox', { name: '成员变动（始终开启）' })).toBeDisabled()

    fireEvent.click(screen.getByRole('checkbox', { name: 'Run 成功' }))
    await waitFor(() => expect(setPreference).toHaveBeenCalledWith('run_succeeded', false))
  })
})

describe('NotificationBell read state toggle', () => {
  it('lets a previously read notification become unread', async () => {
    const notification = makeNotification({ read_at: '2026-08-15T09:00:00Z' })
    vi.spyOn(api, 'unreadCount').mockResolvedValue(0)
    vi.spyOn(api, 'listNotifications').mockResolvedValue(makePage([notification]))
    const markUnread = vi.spyOn(api, 'markNotificationUnread').mockResolvedValue(undefined)

    renderBell()
    fireEvent.click(await screen.findByRole('button', { name: '通知' }))
    const button = await screen.findByRole('button', {
      name: '将「Run「首次运行」已成功」标为未读',
    })
    fireEvent.click(button)
    await waitFor(() => expect(markUnread).toHaveBeenCalledWith('n-1'))
  })
})
