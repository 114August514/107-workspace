import { TriangleDownIcon } from '@primer/octicons-react'
import { Button, IconButton, SelectPanel, Text } from '@primer/react'
import type { ActionListItemInput } from '@primer/react/deprecated'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import type { Project, ProjectPage } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import styles from './AppShell.module.css'

const EMPTY_PAGE: ProjectPage = {
  items: [],
  page: 1,
  page_size: 50,
  total: 0,
  has_more: false,
}

export function ProjectSwitcher({ project }: { project: Project }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedQuery(query), 200)
    return () => window.clearTimeout(timeout)
  }, [query])
  const projects = useAsync<ProjectPage>(
    () =>
      open
        ? api.listOwnerProjects(project.owner, {
            page_size: 50,
            query: debouncedQuery.trim() || undefined,
          })
        : Promise.resolve(EMPTY_PAGE),
    [open, project.owner.kind, project.owner.id, debouncedQuery],
  )
  const error = toAsyncError(projects.error)
  const options: ActionListItemInput[] = (projects.data?.items ?? []).map((item) => ({
    id: item.id,
    text: item.name,
  }))
  const selected = options.find((item) => item.id === project.id)
  const message = error
    ? {
        variant: 'error' as const,
        title: '无法加载 Project。',
        body: <Text size="small">{error.problems?.join(' ') || '请重试。'}</Text>,
        action: <Button onClick={() => void projects.reload()}>重试</Button>,
      }
    : !projects.loading && projects.data && options.length === 0
      ? {
          variant: 'empty' as const,
          title: '没有匹配的 Project。',
          body: '尝试搜索其他名称。',
        }
      : undefined

  const close = () => {
    setOpen(false)
    setQuery('')
    setDebouncedQuery('')
  }

  return (
    <SelectPanel
      open={open}
      onOpenChange={(nextOpen) => {
        if (nextOpen) setOpen(true)
        else close()
      }}
      renderAnchor={({ children: _children, ...anchorProps }) => (
        <IconButton
          {...anchorProps}
          className={styles.projectSwitcherTrigger}
          icon={TriangleDownIcon}
          variant="invisible"
          aria-label="切换 Project"
          aria-haspopup="dialog"
        />
      )}
      title="切换 Project"
      placeholder={project.name}
      placeholderText="搜索 Project"
      inputLabel="搜索 Project"
      filterValue={query}
      onFilterChange={(value) => setQuery(value)}
      loading={projects.loading}
      initialLoadingType="spinner"
      items={options}
      selected={selected}
      onSelectedChange={(item: ActionListItemInput | undefined) => {
        if (!item) return
        close()
        navigate(`/projects/${item.id}`)
      }}
      message={message}
      className={styles.projectSelectPanel}
      notice={
        projects.data?.has_more
          ? { text: '还有更多 Project，请输入名称继续搜索。', variant: 'info' }
          : undefined
      }
      width="auto"
      height="auto"
      overlayProps={{ maxWidth: 'small', maxHeight: 'medium' }}
      align="end"
      disableFullscreenOnNarrow
      aria-label={`${project.owner.display_name} 的 Projects`}
    />
  )
}
