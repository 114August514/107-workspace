import { describe, expect, it } from 'vitest'

import type { Notification } from '../../api/types'
import { notificationLabel, notificationPath } from './notificationTypes'

function notification(patch: Partial<Notification> = {}): Notification {
  return {
    id: 'ntf_1',
    type: 'workspace_invited',
    title: '邀请你加入「算法组」',
    body: '角色：member',
    workspace_id: 'ws_1',
    target_type: 'workspace',
    target_id: 'ws_1',
    mandatory: false,
    created_at: '2026-07-26T10:00:00Z',
    read_at: null,
    ...patch,
  }
}

describe('notificationLabel', () => {
  it('每种通知都有中文说法', () => {
    // 表的完整性由 typecheck 保证（Record<NotificationType, ...> 少一个键编译不过）
    expect(notificationLabel('workspace_invited')).toBe('邀请')
    expect(notificationLabel('run_failed')).toBe('Run 失败')
  })
})

describe('notificationPath', () => {
  it('能定位的对象给出链接', () => {
    expect(notificationPath(notification())).toBe('/workspaces/ws_1')
    expect(notificationPath(notification({ target_type: 'run', target_id: 'run_7' }))).toBe(
      '/runs/run_7',
    )
  })

  it('被移出空间的通知不给链接', () => {
    // 他已经看不到那个空间了，链过去只会是 404——
    // 后端也不给 target_id，这里是双保险
    const removed = notification({
      type: 'member_removed',
      target_type: null,
      target_id: null,
      mandatory: true,
    })
    expect(notificationPath(removed)).toBeNull()
  })

  it('缺少任一定位字段都不拼链接', () => {
    expect(notificationPath(notification({ target_id: null }))).toBeNull()
    expect(notificationPath(notification({ target_type: null }))).toBeNull()
  })
})
