import { describe, expect, it } from 'vitest'

import type { Activity } from '../../src/api/types'
import { targetPath } from '../../src/components/activity/actions'

function makeRunActivity(projectId: string | null): Activity {
  return {
    id: 'activity-1',
    action: 'run_submitted',
    actor_id: 'user-1',
    actor_name: '同学',
    created_at: '2026-08-27T08:00:00Z',
    detail: '',
    owner: { kind: 'user', id: 'user-1' },
    project_id: projectId,
    target_id: 'run-1',
    target_name: '首次运行',
    target_type: 'run',
  }
}

describe('Run activity routes', () => {
  it('uses the canonical Project-contained route when Project context is available', () => {
    expect(targetPath(makeRunActivity('project-1'))).toBe('/projects/project-1/runs/run-1')
  })

  it('keeps ID-only activity links on the resolver route', () => {
    expect(targetPath(makeRunActivity(null))).toBe('/runs/run-1')
  })

  it('keeps deleted Project activity as historical text without a dead link', () => {
    const activity: Activity = {
      ...makeRunActivity(null),
      action: 'project_deleted',
      target_id: 'project-deleted',
      target_name: '已删除 Project',
      target_type: 'project',
    }
    expect(targetPath(activity)).toBeNull()
  })
})
