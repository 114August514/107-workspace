import { Label } from '@primer/react'
import { useOutletContext } from 'react-router-dom'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import { can, type Home, type Project, type UserGroup } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { formatRelative } from '../../utils/format'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { loadGroupProjects } from './groupAssets'
import { RepoList } from './RepoList'
import { DEFAULT_REPO_TYPE_FLAGS, PROJECT_TYPE_FILTERS } from './repoType'
import { userGroupPageCopy as copy } from './userGroupCopy'

function compareUpdatedDesc(left: Project, right: Project): number {
  return (right.updated_at ?? right.created_at ?? '').localeCompare(
    left.updated_at ?? left.created_at ?? '',
  )
}

function ProjectMeta({ project }: { project: Project }) {
  const updated = project.updated_at ?? project.created_at
  if (!updated) return null
  return <>更新于 {formatRelative(updated)}</>
}

function hasProjectAdmin(project: Project, userGroup: UserGroup): boolean {
  if (can(project, 'project.update')) return true
  // 发现列表不投影 capabilities；组页上的组拥有 Project，当前成员具备 project.update。
  return project.owner.kind === 'user_group' && project.owner.id === userGroup.id
}

export function ProjectsSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const projects = useAsync(() => loadGroupProjects(userGroup.id), [userGroup.id])
  const me = useAsync<Home>(() => api.home(), [])
  const currentUserId = me.data?.user.id
  const items = (projects.data?.items ?? []).slice().sort(compareUpdatedDesc)
  const forkedIds = projects.data?.forkedIds ?? new Set<string>()
  const sourceIds = projects.data?.sourceIds ?? new Set<string>()

  return (
    <RepoList
      titleId="user-group-projects-title"
      listLabel="Project 列表"
      searchPlaceholder={copy.list.searchProjects}
      countLabel={copy.list.countProjects}
      noMatches={copy.list.noMatches}
      loading={projects.loading && !projects.data}
      loadingText={copy.list.loadingProjects}
      error={toAsyncError(projects.error)}
      onRetry={projects.reload}
      emptyText={copy.list.emptyProjects}
      emptyDescription={copy.list.emptyProjectsHint}
      truncatedNote={projects.data?.truncated ? copy.list.truncatedProjects : null}
      typeFilters={PROJECT_TYPE_FILTERS}
      items={items.map((project) => {
        const forked = forkedIds.has(project.id)
        const source = sourceIds.has(project.id)
        return {
          id: project.id,
          name: project.name,
          to: `/projects/${project.id}`,
          description: project.description,
          types: {
            ...DEFAULT_REPO_TYPE_FLAGS,
            contributed: currentUserId !== undefined && project.created_by === currentUserId,
            admin: hasProjectAdmin(project, userGroup),
            isPublic: project.visibility === 'public',
            source,
            fork: forked,
            archived: project.status === 'archived',
            template: false,
          },
          badges: (
            <>
              <Label size="small" variant="secondary">
                {project.visibility === 'public'
                  ? copy.list.visibilityPublic
                  : copy.list.visibilityOwnerScope}
              </Label>
              {forked ? (
                <Label size="small" variant="secondary">
                  {copy.list.forked}
                </Label>
              ) : null}
              {project.status === 'archived' ? (
                <Label size="small" variant="attention">
                  {copy.list.archived}
                </Label>
              ) : null}
            </>
          ),
          meta: <ProjectMeta project={project} />,
        }
      })}
    />
  )
}
