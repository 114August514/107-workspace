import { useOutletContext } from 'react-router-dom'

import { toAsyncError } from '../../api/errors'
import { can, type SharedResource } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { formatRelative } from '../../utils/format'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { loadGroupSharedResources } from './groupAssets'
import { RepoList } from './RepoList'
import { DEFAULT_REPO_TYPE_FLAGS } from './repoType'
import { userGroupPageCopy as copy } from './userGroupCopy'

function compareCreatedDesc(left: SharedResource, right: SharedResource): number {
  return right.created_at.localeCompare(left.created_at)
}

export function SharedResourcesSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const resources = useAsync(() => loadGroupSharedResources(userGroup.id), [userGroup.id])
  const items = (resources.data ?? []).slice().sort(compareCreatedDesc)

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
      items={items.map((resource) => ({
        id: resource.id,
        name: resource.name,
        to: `/shared-resources/${resource.id}`,
        description: resource.description,
        types: {
          ...DEFAULT_REPO_TYPE_FLAGS,
          admin: can(resource, 'shared_resource.manage'),
        },
        meta: copy.list.createdAt(formatRelative(resource.created_at)),
      }))}
    />
  )
}
