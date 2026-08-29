/**
 * User Group 拥有资产的读取。
 *
 * Contract 没有组级资产列表端点：发现列表返回「当前 User 可见」的资产，
 * 组拥有集合由 owner 投影（OwnerSummaryOut）客户端过滤得出。
 */
import { api } from '../../api/client'
import type { Environment, OwnerSummary, Project, SharedResource } from '../../api/types'

const PROJECT_PAGE_SIZE = 200
const PROJECT_PAGE_LIMIT = 5

export interface GroupAssetsResult<T> {
  items: T[]
  truncated: boolean
}

export function isOwnedByGroup(owner: OwnerSummary, groupId: string): boolean {
  return owner.kind === 'user_group' && owner.id === groupId
}

export async function loadGroupProjects(groupId: string): Promise<GroupAssetsResult<Project>> {
  const items: Project[] = []
  for (let page = 1; page <= PROJECT_PAGE_LIMIT; page += 1) {
    const result = await api.listProjects({ page, page_size: PROJECT_PAGE_SIZE })
    items.push(...result.items.filter((project) => isOwnedByGroup(project.owner, groupId)))
    if (!result.has_more) return { items, truncated: false }
  }
  return { items, truncated: true }
}

export async function loadGroupSharedResources(groupId: string): Promise<SharedResource[]> {
  const resources = await api.listSharedResources()
  return resources.filter((resource) => isOwnedByGroup(resource.owner, groupId))
}

export async function loadGroupEnvironments(groupId: string): Promise<Environment[]> {
  const environments = await api.environments()
  return environments.filter((environment) => isOwnedByGroup(environment.owner, groupId))
}
