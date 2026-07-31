import { describe, expect, it } from 'vitest'

import { can } from './types'
import type { Workspace } from './types'

function workspace(capabilities: Workspace['capabilities']): Workspace {
  return {
    id: 'ws_1',
    kind: 'collaborative',
    name: '算法组',
    description: '',
    owner_id: 'usr_1',
    default_environment_version_id: null,
    created_at: null,
    role: 'member',
    capabilities,
  }
}

describe('can', () => {
  it('按后端给的能力清单判断', () => {
    const ws = workspace(['workspace.view', 'project.create'])

    expect(can(ws, 'project.create')).toBe(true)
    expect(can(ws, 'member.manage')).toBe(false)
  })

  it('空间还没加载出来时一律当作没有权限', () => {
    // 加载中就把按钮显示出来，用户点了才发现不行，比藏起来更糟
    expect(can(undefined, 'project.create')).toBe(false)
  })

  it('能力清单为空时不报错', () => {
    expect(can(workspace([]), 'workspace.view')).toBe(false)
  })
})
