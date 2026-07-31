import { describe, expect, it } from 'vitest'

import type { Activity } from '../../api/types'
import { describeAction, describeDetail, showsTarget, targetPath } from './actions'

function activity(patch: Partial<Activity>): Activity {
  return {
    id: 'act_1',
    workspace_id: 'ws_1',
    project_id: null,
    actor_id: 'usr_1',
    actor_name: 'alice',
    action: 'project_created',
    target_type: 'project',
    target_id: 'prj_1',
    target_name: '实验',
    detail: '',
    created_at: '2026-07-26T10:00:00Z',
    ...patch,
  }
}

describe('describeAction', () => {
  it('每个动作都有中文说法', () => {
    // 这张表的完整性由 typecheck 保证（Record<ActivityAction, string> 少一个键就编译不过），
    // 这里只抽查几条，确认接出来的话读得通
    expect(describeAction('project_created')).toBe('创建了 Project')
    expect(describeAction('member_removed')).toBe('移除了')
    expect(describeAction('run_finished')).toBe('的 Run 结束了')
  })

  it('接上主语和宾语之后读得通', () => {
    // 活动流里一条就是一句话，动作文案是句子中间那截，
    // 单看没问题、拼起来别扭的情况只有这样才发现得了
    const line = (a: Activity) =>
      `${a.actor_name} ${describeAction(a.action)} ${showsTarget(a) ? a.target_name : ''}`.trim()

    expect(line(activity({ action: 'project_created', target_name: '实验' }))).toBe(
      'alice 创建了 Project 实验',
    )
    expect(
      line(
        activity({
          action: 'member_joined',
          target_type: 'member',
          actor_id: 'usr_1',
          target_id: 'usr_1',
          target_name: 'alice',
        }),
      ),
    ).toBe('alice 加入了空间')
    expect(line(activity({ action: 'run_finished', target_name: '实验 · v2' }))).toBe(
      'alice 的 Run 结束了 实验 · v2',
    )
  })
})

describe('showsTarget', () => {
  it('操作者就是对象本人时不重复显示名字', () => {
    // 否则会读成「guest 加入了空间 guest」
    const joined = activity({
      action: 'member_joined',
      target_type: 'member',
      actor_id: 'usr_9',
      target_id: 'usr_9',
    })
    expect(showsTarget(joined)).toBe(false)
  })

  it('操作别人时正常显示', () => {
    const removed = activity({
      action: 'member_removed',
      target_type: 'member',
      actor_id: 'usr_1',
      target_id: 'usr_2',
    })
    expect(showsTarget(removed)).toBe(true)
  })
})

describe('describeDetail', () => {
  it('Run 结束的状态翻成中文', () => {
    // 后端存的是 run.status.value，直接显示就是「failed」
    expect(describeDetail(activity({ action: 'run_finished', detail: 'failed' }))).toBe('失败')
    expect(describeDetail(activity({ action: 'run_finished', detail: 'succeeded' }))).toBe('成功')
  })

  it('认不出来的取值原样显示', () => {
    // 后端加了新状态而前端还没跟上时，显示原文也比显示空白强
    expect(describeDetail(activity({ action: 'run_finished', detail: 'whatever' }))).toBe(
      'whatever',
    )
  })

  it('其他动作的补充说明不做翻译', () => {
    expect(
      describeDetail(activity({ action: 'member_role_changed', detail: 'member → admin' })),
    ).toBe('member → admin')
  })
})

describe('targetPath', () => {
  it('能定位的对象给出链接', () => {
    expect(targetPath(activity({ target_type: 'project', target_id: 'prj_9' }))).toBe(
      '/projects/prj_9',
    )
    expect(targetPath(activity({ target_type: 'run', target_id: 'run_9' }))).toBe('/runs/run_9')
    expect(targetPath(activity({ target_type: 'workspace', target_id: 'ws_9' }))).toBe(
      '/workspaces/ws_9',
    )
  })

  it('版本没有独立页面，跳到所属 Project', () => {
    expect(targetPath(activity({ target_type: 'project_version', project_id: 'prj_7' }))).toBe(
      '/projects/prj_7',
    )
  })

  it('成员不给链接', () => {
    // 没有用户主页，链过去也没东西看
    expect(targetPath(activity({ target_type: 'member', target_id: 'usr_2' }))).toBeNull()
  })

  it('缺少定位信息时返回 null 而不是拼出一个坏链接', () => {
    expect(targetPath(activity({ target_type: 'project_version', project_id: null }))).toBeNull()
  })
})
