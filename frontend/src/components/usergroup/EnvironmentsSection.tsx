import { useOutletContext } from 'react-router-dom'

import { toAsyncError } from '../../api/errors'
import type { Environment } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { loadGroupEnvironments } from './groupAssets'
import { RepoList } from './RepoList'
import { DEFAULT_REPO_TYPE_FLAGS } from './repoType'
import { userGroupPageCopy as copy } from './userGroupCopy'

function compareName(left: Environment, right: Environment): number {
  return left.name.localeCompare(right.name, 'zh')
}

export function EnvironmentsSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const environments = useAsync(() => loadGroupEnvironments(userGroup.id), [userGroup.id])
  const items = (environments.data ?? []).slice().sort(compareName)

  return (
    <RepoList
      titleId="user-group-environments-title"
      listLabel="运行环境列表"
      searchPlaceholder={copy.list.searchEnvironments}
      countLabel={copy.list.countEnvironments}
      noMatches={copy.list.noMatches}
      loading={environments.loading && !environments.data}
      loadingText={copy.list.loadingEnvironments}
      error={toAsyncError(environments.error)}
      onRetry={environments.reload}
      emptyText={copy.list.emptyEnvironments}
      emptyDescription={copy.list.emptyEnvironmentsHint}
      items={items.map((environment) => {
        const availableCount = environment.versions.filter(
          (version) => version.availability === 'available',
        ).length
        return {
          id: environment.id,
          name: environment.name,
          to: `/environments/${environment.id}`,
          description: environment.description,
          types: DEFAULT_REPO_TYPE_FLAGS,
          meta: copy.list.availableVersions(availableCount, environment.versions.length),
        }
      })}
    />
  )
}
