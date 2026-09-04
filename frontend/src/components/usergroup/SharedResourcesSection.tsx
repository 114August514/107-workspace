import { useOutletContext } from 'react-router-dom'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import { can, type Home, type SharedResource } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { formatRelative } from '../../utils/format'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { loadGroupSharedResources } from './groupAssets'
import { RepoList } from './RepoList'
import { DEFAULT_REPO_TYPE_FLAGS, SHARED_RESOURCE_TYPE_FILTERS } from './repoType'
import { userGroupPageCopy as copy } from './userGroupCopy'

function compareCreatedDesc(left: SharedResource, right: SharedResource): number {
  return right.created_at.localeCompare(left.created_at)
}

function isPublicSharedResource(resource: SharedResource): boolean {
  return resource.use_qualifications.some((qualification) => qualification.scope !== 'owner')
}

export function SharedResourcesSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const resources = useAsync(() => loadGroupSharedResources(userGroup.id), [userGroup.id])
  const me = useAsync<Home>(() => api.home(), [])
  const currentUserId = me.data?.user.id
  const items = (resources.data ?? []).slice().sort(compareCreatedDesc)
  const contributedIds = useAsync(async () => {
    const list = resources.data ?? []
    if (!currentUserId || list.length === 0) return new Set<string>()
    const matches = await Promise.all(
      list.map(async (resource) => {
        try {
          const detail = await api.getSharedResource(resource.id)
          return detail.versions.some((version) => version.created_by === currentUserId)
            ? resource.id
            : null
        } catch {
          return null
        }
      }),
    )
    return new Set(matches.filter((id): id is string => id !== null))
  }, [currentUserId, resources.data])

  return (
    <RepoList
      titleId="user-group-shared-resources-title"
      listLabel="共享资源列表"
      searchPlaceholder={copy.list.searchSharedResources}
      countLabel={copy.list.countSharedResources}
      noMatches={copy.list.noMatches}
      loading={resources.loading && !resources.data}
      loadingText={copy.list.loadingSharedResources}
      error={toAsyncError(resources.error)}
      onRetry={resources.reload}
      emptyText={copy.list.emptySharedResources}
      emptyDescription={copy.list.emptySharedResourcesHint}
      typeFilters={SHARED_RESOURCE_TYPE_FILTERS}
      items={items.map((resource) => ({
        id: resource.id,
        name: resource.name,
        to: `/shared-resources/${resource.id}`,
        description: resource.description,
        types: {
          ...DEFAULT_REPO_TYPE_FLAGS,
          contributed: contributedIds.data?.has(resource.id) ?? false,
          admin: can(resource, 'shared_resource.manage'),
          isPublic: isPublicSharedResource(resource),
        },
        meta: copy.list.createdAt(formatRelative(resource.created_at)),
      }))}
    />
  )
}
