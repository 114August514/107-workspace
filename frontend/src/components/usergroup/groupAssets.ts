/**
 * User Group 拥有资产的读取。
 *
 * Contract 没有组级资产列表端点：发现列表返回「当前 User 可见」的资产，
 * 组拥有集合由 owner 投影（OwnerSummaryOut）客户端过滤得出。
 */
import { api } from '../../api/client'
import type { Environment, OwnerSummary, Project, SharedResource } from '../../api/types'

const PROJECT_PAGE_SIZE = 200
// 防御性安全阀：跟随 has_more 直到列表耗尽；只有后端分页异常
// （一万条仍报 has_more）才会命中并标记 truncated，避免无限请求。
const PROJECT_PAGE_LIMIT = 50

export interface GroupAssetsResult<T> {
  items: T[]
  truncated: boolean
}

export interface GroupProjectList extends GroupAssetsResult<Project> {
  /** 组内 Project 自己是派生副本。 */
  forkedIds: Set<string>
  /** 组内 Project 被其他可见 Project 当作 Fork 来源。 */
  sourceIds: Set<string>
}

export function isOwnedByGroup(owner: OwnerSummary, groupId: string): boolean {
  return owner.kind === 'user_group' && owner.id === groupId
}

export async function loadGroupProjects(groupId: string): Promise<GroupProjectList> {
  const items: Project[] = []
  const visible: Project[] = []
  let truncated = true
  for (let page = 1; page <= PROJECT_PAGE_LIMIT; page += 1) {
    const result = await api.listProjects({ page, page_size: PROJECT_PAGE_SIZE })
    visible.push(...result.items)
    items.push(...result.items.filter((project) => isOwnedByGroup(project.owner, groupId)))
    if (!result.has_more) {
      truncated = false
      break
    }
  }

  const groupIds = new Set(items.map((project) => project.id))
  const forkedIds = new Set<string>()
  const sourceIds = new Set<string>()
  await Promise.all(
    visible.map(async (project) => {
      try {
        const source = await api.forkSource(project.id)
        if (source === null) return
        if (groupIds.has(project.id)) forkedIds.add(project.id)
        if (groupIds.has(source.source_project_id)) sourceIds.add(source.source_project_id)
      } catch {
        // 单条来源读失败时不影响列表，该条既不标 Fork 也不标 Source。
      }
    }),
  )

  return { items, truncated, forkedIds, sourceIds }
}

export async function loadGroupSharedResources(groupId: string): Promise<SharedResource[]> {
  const resources = await api.listSharedResources()
  return resources.filter((resource) => isOwnedByGroup(resource.owner, groupId))
}

export async function loadGroupEnvironments(groupId: string): Promise<Environment[]> {
  const environments = await api.environments()
  return environments.filter((environment) => isOwnedByGroup(environment.owner, groupId))
}
