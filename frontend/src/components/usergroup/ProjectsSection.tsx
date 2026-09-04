import { Label } from '@primer/react'
import { useOutletContext } from 'react-router-dom'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import { can, type Home, type Project } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { formatRelative } from '../../utils/format'
import type { UserGroupOutletContext } from '../../pages/UserGroupPage'
import { loadGroupProjects } from './groupAssets'
import { RepoList } from './RepoList'
import { DEFAULT_REPO_TYPE_FLAGS } from './repoType'
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

export function ProjectsSection() {
  const { userGroup } = useOutletContext<UserGroupOutletContext>()
  const projects = useAsync(() => loadGroupProjects(userGroup.id), [userGroup.id])
  const me = useAsync<Home>(() => api.home(), [])
  const currentUserId = me.data?.user.id
  const items = (projects.data?.items ?? []).slice().sort(compareUpdatedDesc)

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
      items={items.map((project) => ({
        id: project.id,
        name: project.name,
        to: `/projects/${project.id}`,
        description: project.description,
        types: {
          ...DEFAULT_REPO_TYPE_FLAGS,
          contributed: currentUserId !== undefined && project.created_by === currentUserId,
          admin: can(project, 'project.update'),
          isPublic: project.visibility === 'public',
          archived: project.status === 'archived',
        },
        badges: (
          <>
            <Label size="small" variant="secondary">
              {project.visibility === 'public'
                ? copy.list.visibilityPublic
                : copy.list.visibilityOwnerScope}
            </Label>
            {project.status === 'archived' ? (
              <Label size="small" variant="attention">
                {copy.list.archived}
              </Label>
            ) : null}
          </>
        ),
        meta: <ProjectMeta project={project} />,
      }))}
    />
  )
}
