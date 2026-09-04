import { Label } from '@primer/react'
import { useOutletContext } from 'react-router-dom'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import { can, type Environment, type Home } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { loadGroupEnvironments } from './groupAssets'
import { RepoList } from './RepoList'
import { DEFAULT_REPO_TYPE_FLAGS, ENVIRONMENT_TYPE_FILTERS } from './repoType'
import { userGroupPageCopy as copy } from './userGroupCopy'

function compareName(left: Environment, right: Environment): number {
  return left.name.localeCompare(right.name, 'zh')
}

export function EnvironmentsSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const environments = useAsync(() => loadGroupEnvironments(userGroup.id), [userGroup.id])
  const me = useAsync<Home>(() => api.home(), [])
  const currentUserId = me.data?.user.id
  const items = (environments.data ?? []).slice().sort(compareName)
  const contributedIds = useAsync(async () => {
    const list = environments.data ?? []
    if (!currentUserId || list.length === 0) return new Set<string>()
    const matches = await Promise.all(
      list.map(async (environment) => {
        try {
          const attempts = await api.environmentPublicationAttempts(environment.id)
          return attempts.some((attempt) => attempt.created_by === currentUserId)
            ? environment.id
            : null
        } catch {
          return null
        }
      }),
    )
    return new Set(matches.filter((id): id is string => id !== null))
  }, [currentUserId, environments.data])
  const publicIds = useAsync(async () => {
    const list = environments.data ?? []
    if (list.length === 0) return new Set<string>()
    try {
      const grants = await api.listGrants({
        grantor_kind: 'user_group',
        grantor_id: userGroup.id,
      })
      if (grants.some((grant) => grant.target_kind === 'all')) {
        return new Set(list.map((environment) => environment.id))
      }
      return new Set(
        grants
          .filter((grant) => grant.target_kind === 'environment')
          .map((grant) => grant.target_id),
      )
    } catch {
      return new Set<string>()
    }
  }, [environments.data, userGroup.id])

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
      typeFilters={ENVIRONMENT_TYPE_FILTERS}
      items={items.map((environment) => {
        const availableCount = environment.versions.filter(
          (version) => version.availability === 'available',
        ).length
        const isPublic = publicIds.data?.has(environment.id) ?? false
        return {
          id: environment.id,
          name: environment.name,
          to: `/environments/${environment.id}`,
          description: environment.description,
          types: {
            ...DEFAULT_REPO_TYPE_FLAGS,
            contributed: contributedIds.data?.has(environment.id) ?? false,
            admin: can(userGroup, 'user_group.update'),
            isPublic,
          },
          badges: isPublic ? (
            <Label size="small" variant="secondary">
              {copy.list.visibilityPublic}
            </Label>
          ) : null,
          meta: copy.list.availableVersions(availableCount, environment.versions.length),
        }
      })}
    />
  )
}
