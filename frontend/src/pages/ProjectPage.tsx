import {
  DiffIcon,
  HistoryIcon,
  PencilIcon,
  TriangleDownIcon,
  VersionsIcon,
} from '@primer/octicons-react'
import { Button as PrimerButton, SelectPanel, Text } from '@primer/react'
import type { ActionListItemInput } from '@primer/react/deprecated'
import { BranchesOutlined } from '@ant-design/icons'
import { Card, Empty, Tag } from 'antd'
import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import type {
  ActivityPage,
  Environment,
  ForkSource,
  Project,
  ProjectVersionDetail,
  ProjectVersionPage,
  RunConfiguration,
  RunPage,
  WorkingChange,
} from '../api/types'
import { can } from '../api/types'
import { useAsync, type AsyncState as AsyncResource } from '../api/useAsync'
import { ActivityFeed } from '../components/activity/ActivityFeed'
import { AsyncSection } from '../components/common/AsyncSection'
import { AsyncState } from '../components/common/AsyncState'
import { ListCard } from '../components/layout/ListCard'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { FileBrowser } from '../components/project/FileBrowser'
import { VersionPanel } from '../components/project/VersionPanel'
import { FileViewer } from '../components/project/FileViewer'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import { RunTable } from '../components/run/RunTable'
import { SubmitRunModal } from '../components/run/SubmitRunModal'
import { RunConfigurationPanel } from '../components/runconfig/RunConfigurationPanel'
import { tablePagination } from '../utils/pagination'
import { formatRelative } from '../utils/format'
import styles from './ProjectPage.module.css'

type ProjectSection = 'files' | 'runs' | 'activity' | 'settings'
type FilesView = 'working' | 'changes' | 'versions'
type RunsView = 'history' | 'configurations'

const PAGE_TITLES = {
  latest: 'Files',
  working: 'Working State',
  changes: 'Changes',
  versions: 'Versions',
  history: 'Run history',
  configurations: 'Run configurations',
  activity: 'Activity',
  settings: 'Settings',
  version: 'Version',
  file: 'File',
} as const
type ProjectView = 'latest' | FilesView | RunsView | 'activity' | 'settings' | 'version' | 'file'

interface ProjectLocation {
  section: ProjectSection
  view: ProjectView
  currentPath: string
  versionId?: string
  filePath?: string
}

function resolveProjectPath(pathname: string, projectId: string): ProjectLocation {
  const prefix = `/projects/${projectId}`
  const segments = pathname.startsWith(prefix)
    ? pathname.slice(prefix.length).split('/').filter(Boolean).map(decodeURIComponent)
    : []
  const section = segments[0]
  if (section === 'activity') return { section: 'activity', view: 'activity', currentPath: '' }
  if (section === 'settings') return { section: 'settings', view: 'settings', currentPath: '' }
  if (section === 'runs') {
    return {
      section: 'runs',
      view: segments[1] === 'configurations' ? 'configurations' : 'history',
      currentPath: '',
    }
  }
  if (section !== 'files') return { section: 'files', view: 'latest', currentPath: '' }
  if (segments[1] === 'working') {
    if (segments[2] === 'file' && segments[3]) {
      return {
        section: 'files',
        view: 'file',
        currentPath: segments.slice(2, -1).join('/'),
        filePath: segments.slice(2).join('/'),
      }
    }
    return {
      section: 'files',
      view: 'working',
      currentPath: segments[2] === 'tree' ? segments.slice(3).join('/') : '',
    }
  }
  if (segments[1] === 'file' && segments[2]) {
    return {
      section: 'files',
      view: 'file',
      currentPath: segments.slice(2, -1).join('/'),
      filePath: segments.slice(2).join('/'),
    }
  }
  if (segments[1] === 'changes') return { section: 'files', view: 'changes', currentPath: '' }
  if (segments[1] === 'versions') {
    if (segments[2] && segments[3] === 'file' && segments[4]) {
      return {
        section: 'files',
        view: 'file',
        versionId: segments[2],
        currentPath: segments.slice(4, -1).join('/'),
        filePath: segments.slice(4).join('/'),
      }
    }
    if (segments[2])
      return {
        section: 'files',
        view: 'version',
        versionId: segments[2],
        currentPath: segments[3] === 'tree' ? segments.slice(4).join('/') : '',
      }
    return { section: 'files', view: 'versions', currentPath: '' }
  }
  return { section: 'files', view: 'latest', currentPath: '' }
}

function projectViewHref(projectId: string, section: ProjectSection, view?: FilesView | RunsView) {
  if (section === 'activity' || section === 'settings') return `/projects/${projectId}/${section}`
  if (section === 'files') {
    if (view === 'changes') return `/projects/${projectId}/files/changes`
    if (view === 'versions') return `/projects/${projectId}/files/versions`
    return `/projects/${projectId}/files`
  }
  return view === 'configurations'
    ? `/projects/${projectId}/runs/configurations`
    : `/projects/${projectId}/runs`
}

function FilesContextControls({
  projectId,
  mode,
  selectedVersion,
}: {
  projectId: string
  mode: 'working' | 'version'
  selectedVersion?: ProjectVersionDetail
}) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const versions = useAsync<ProjectVersionPage>(
    () => api.listVersions(projectId, { page: 1, page_size: 50 }),
    [projectId],
  )
  const changes = useAsync<WorkingChange[]>(
    () => (mode === 'working' ? api.workingChanges(projectId) : Promise.resolve([])),
    [projectId, mode],
  )
  const options: ActionListItemInput[] = (versions.data?.items ?? []).map((version) => ({
    id: version.id,
    text: version.label,
  }))
  const selected = options.find((option) => option.id === selectedVersion?.id)
  const error = toAsyncError(versions.error)
  const close = () => {
    setOpen(false)
    setQuery('')
  }
  return (
    <div className={styles.fileContextControls} aria-label="Files context">
      {mode === 'working' ? (
        <span className={styles.refControl}>
          <PencilIcon size={16} /> Working State
        </span>
      ) : (
        <SelectPanel
          open={open}
          onOpenChange={(nextOpen) => (nextOpen ? setOpen(true) : close())}
          renderAnchor={({ children: _children, ...anchorProps }) => (
            <PrimerButton
              {...anchorProps}
              leadingVisual={VersionsIcon}
              trailingVisual={TriangleDownIcon}
              aria-label="选择 Project Version"
              aria-haspopup="dialog"
            >
              {selectedVersion?.label ?? 'Project Version'}
            </PrimerButton>
          )}
          title="选择 Project Version"
          placeholder={selectedVersion?.label ?? 'Project Version'}
          placeholderText="搜索 Project Version"
          inputLabel="搜索 Project Version"
          filterValue={query}
          onFilterChange={setQuery}
          items={options}
          selected={selected}
          onSelectedChange={(item: ActionListItemInput | undefined) => {
            if (!item) return
            close()
            navigate(`/projects/${projectId}/files/versions/${item.id}`)
          }}
          loading={versions.loading}
          initialLoadingType="spinner"
          message={
            error
              ? {
                  variant: 'error' as const,
                  title: '无法加载 Project Versions。',
                  body: <Text size="small">{error.problems?.join(' ') || '请重试。'}</Text>,
                  action: <PrimerButton onClick={() => void versions.reload()}>重试</PrimerButton>,
                }
              : !versions.loading && options.length === 0
                ? {
                    variant: 'empty' as const,
                    title: '还没有保存的 Version。',
                    body: '进入 Working State 保存第一个 Version。',
                  }
                : undefined
          }
          width="auto"
          height="auto"
          overlayProps={{ maxWidth: 'small', maxHeight: 'medium' }}
          align="start"
          disableFullscreenOnNarrow
          aria-label="Project Versions"
        />
      )}
      {mode === 'working' ? (
        <Link to={projectViewHref(projectId, 'files', 'changes')} className={styles.contextLink}>
          <DiffIcon size={16} /> {changes.data?.length ?? '—'} changes
        </Link>
      ) : (
        <Link to={projectViewHref(projectId, 'files', 'versions')} className={styles.contextLink}>
          <HistoryIcon size={16} /> {versions.data?.total ?? '—'} Versions
        </Link>
      )}
    </div>
  )
}

function ProjectAbout({ project, projectId }: { project: Project | undefined; projectId: string }) {
  const versions = useAsync<ProjectVersionPage>(
    () => api.listVersions(projectId, { page: 1, page_size: 1 }),
    [projectId],
  )
  const environments = useAsync<Environment[]>(
    () => api.environmentsForProject(projectId),
    [projectId],
  )
  if (!project) return null
  const latestVersion = versions.data?.items[0]
  const defaultEnvironment = environments.data
    ?.flatMap((environment) => environment.versions.map((version) => ({ environment, version })))
    .find(({ version }) => version.id === project.environment_version_id)
  return (
    <aside className={styles.aboutRail} aria-label="About">
      <div className={styles.aboutCard}>
        <h2>About</h2>
        <p>{project.description || '这个 Project 还没有填写说明。'}</p>
        <dl className={styles.aboutFacts}>
          <div>
            <dt>Latest version</dt>
            <dd>{latestVersion?.label ?? '—'}</dd>
          </div>
          <div>
            <dt>Updated</dt>
            <dd>{formatRelative(project.updated_at)}</dd>
          </div>
          <div>
            <dt>Owner</dt>
            <dd>{project.owner.display_name}</dd>
          </div>
          <div>
            <dt>Visibility</dt>
            <dd>{project.visibility}</dd>
          </div>
          {defaultEnvironment && (
            <div>
              <dt>Default environment</dt>
              <dd>{`${defaultEnvironment.environment.name} · ${defaultEnvironment.version.version}`}</dd>
            </div>
          )}
        </dl>
        {environments.data && environments.data.length > 0 && (
          <section className={styles.relatedResources} aria-labelledby="related-resources-title">
            <h3 id="related-resources-title">Related resources</h3>
            {environments.data.map((environment) => (
              <Link key={environment.id} to={`/environments/${environment.id}`}>
                {environment.name}
              </Link>
            ))}
          </section>
        )}
      </div>
    </aside>
  )
}
/**
 * Project 页面：以 Files / Runs / Activity / Settings 组织既有 Project 能力。
 *
 * 本页面只收敛导航归属，不新增 Version、Run Configuration、Activity 或 Settings 业务。
 */
export function ProjectPage({ project }: { project: AsyncResource<Project | undefined> }) {
  const { projectId = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { section, view, currentPath, versionId, filePath } = resolveProjectPath(
    location.pathname,
    projectId,
  )
  const version = useAsync<ProjectVersionDetail | undefined>(
    () => (versionId ? api.getVersion(versionId) : Promise.resolve(undefined)),
    [versionId],
  )
  const latestVersion = useAsync<ProjectVersionDetail | undefined>(async () => {
    if (view !== 'latest') return undefined
    const page = await api.listVersions(projectId, { page: 1, page_size: 1 })
    const latest = page.items[0]
    return latest ? api.getVersion(latest.id) : undefined
  }, [projectId, view])
  const selectedVersion = version.data ?? latestVersion.data
  const [token, setToken] = useState(0)
  const bump = () => {
    setToken((value) => value + 1)
    void project.reload({ silent: true })
  }

  const [runPage, setRunPage] = useState(1)
  const runs = useAsync<RunPage>(
    () => api.listRuns(projectId, { page: runPage }),
    [projectId, token, runPage],
  )
  const runError = toAsyncError(runs.error)

  const [submitting, setSubmitting] = useState<RunConfiguration | null>(null)
  const forkSource = useAsync<ForkSource | null>(() => api.forkSource(projectId), [projectId])
  const activities = useAsync<ActivityPage>(
    () => api.listProjectActivities(projectId, { page_size: 20 }),
    [projectId, token],
  )
  const fileBasePath = selectedVersion
    ? `/projects/${projectId}/files/versions/${selectedVersion.id}`
    : view === 'working' || (view === 'file' && !versionId)
      ? `/projects/${projectId}/files/working`
      : `/projects/${projectId}/files`
  const fileBackHref = currentPath
    ? `${fileBasePath}/tree/${currentPath.split('/').map(encodeURIComponent).join('/')}`
    : fileBasePath
  const workingFileHref = filePath
    ? `/projects/${projectId}/files/working/file/${filePath.split('/').map(encodeURIComponent).join('/')}`
    : undefined
  const startEditingAction = can(project.data, 'project.content.write') ? (
    <PrimerButton
      leadingVisual={PencilIcon}
      onClick={() => navigate(`/projects/${projectId}/files/working`)}
    >
      开始编辑
    </PrimerButton>
  ) : undefined

  const content =
    view === 'latest' ? (
      <AsyncSection loading={latestVersion.loading} error={latestVersion.error}>
        {latestVersion.data ? (
          <FileBrowser
            projectId={projectId}
            access={project.data}
            onChanged={() => undefined}
            currentPath={currentPath}
            basePath={fileBasePath}
            version={latestVersion.data}
            toolbarAction={startEditingAction}
            contextControls={
              <FilesContextControls
                projectId={projectId}
                mode="version"
                selectedVersion={latestVersion.data}
              />
            }
          />
        ) : (
          <div className={styles.noVersion}>
            <h2>尚未保存 Project Version</h2>
            <p>进入 Working State 保存第一个 Version。</p>
            <Link to={`/projects/${projectId}/files/working`}>进入 Working State</Link>
          </div>
        )}
      </AsyncSection>
    ) : view === 'working' ? (
      <FileBrowser
        projectId={projectId}
        access={project.data}
        onChanged={bump}
        currentPath={currentPath}
        basePath={`/projects/${projectId}/files/working`}
        contextControls={<FilesContextControls projectId={projectId} mode="working" />}
      />
    ) : view === 'changes' ? (
      <Card>
        <VersionPanel
          section="changes"
          projectId={projectId}
          projectName={project.data?.name ?? ''}
          access={project.data}
          refreshToken={token}
          onVersionSaved={bump}
        />
      </Card>
    ) : view === 'versions' ? (
      <Card>
        <VersionPanel
          section="versions"
          projectId={projectId}
          projectName={project.data?.name ?? ''}
          access={project.data}
          refreshToken={token}
          onVersionSaved={bump}
        />
      </Card>
    ) : view === 'file' ? (
      <AsyncSection
        loading={versionId ? version.loading : false}
        error={versionId ? version.error : undefined}
      >
        {filePath && (!versionId || version.data) && (
          <FileViewer
            projectId={projectId}
            access={project.data}
            path={filePath}
            backHref={fileBackHref}
            rootHref={fileBasePath}
            version={version.data}
            workingHref={versionId ? workingFileHref : undefined}
          />
        )}
      </AsyncSection>
    ) : view === 'version' ? (
      <AsyncSection loading={version.loading} error={version.error}>
        {version.data && (
          <FileBrowser
            projectId={projectId}
            access={project.data}
            onChanged={() => undefined}
            currentPath={currentPath}
            basePath={fileBasePath}
            version={version.data}
            toolbarAction={startEditingAction}
            contextControls={
              <FilesContextControls
                projectId={projectId}
                mode="version"
                selectedVersion={version.data}
              />
            }
          />
        )}
      </AsyncSection>
    ) : view === 'history' ? (
      <PrimerListCard>
        <AsyncState
          loading={runs.loading}
          loadingText="正在加载 Run 历史…"
          error={runError ? { ...runError, message: '无法加载 Run 历史。' } : undefined}
          onRetry={runs.reload}
          empty={runs.data?.total === 0}
          emptyText="这个 Project 还没有 Run。"
          emptyDescription="提交 Run 后，可以在这里查看状态、日志、运行产物和运行快照。"
        >
          <RunTable
            runs={runs.data?.items ?? []}
            projectName={project.data?.name}
            pagination={tablePagination(runs.data, setRunPage)}
          />
        </AsyncState>
      </PrimerListCard>
    ) : view === 'configurations' ? (
      <Card>
        <RunConfigurationPanel
          projectId={projectId}
          access={project.data}
          defaultConfigurationId={project.data?.default_run_configuration_id ?? null}
          onSubmitRun={setSubmitting}
          onChanged={bump}
        />
      </Card>
    ) : view === 'activity' ? (
      <ListCard padded>
        <ActivityFeed
          page={activities.data}
          loading={activities.loading}
          error={activities.error}
          emptyText="这个 Project 还没有活动记录"
        />
      </ListCard>
    ) : (
      <Card>
        <Empty description="Project 自身管理配置入口；编辑能力不在本 Issue 范围内。" />
      </Card>
    )

  const filesContent =
    section === 'files' ? (
      <div className={styles.filesLayout}>
        <div className={styles.filesMain}>{content}</div>
        <ProjectAbout project={project.data} projectId={projectId} />
      </div>
    ) : (
      content
    )

  return (
    <Stack gap="large">
      {section === 'files' && (view === 'working' || view === 'latest') ? null : (
        <AsyncSection loading={project.loading} error={project.error}>
          {project.data && (
            <PageHeader
              title={
                view === 'version' && version.data
                  ? `${version.data.label} · 只读`
                  : PAGE_TITLES[view]
              }
              description={project.data.description || '这个 Project 还没有填写说明'}
              tags={forkSource.data ? <ForkSourceTag source={forkSource.data} /> : null}
            />
          )}
        </AsyncSection>
      )}

      {filesContent}

      <SubmitRunModal
        open={submitting !== null}
        projectId={projectId}
        configuration={submitting}
        onClose={() => setSubmitting(null)}
        onSubmitted={(run) => navigate(`/projects/${run.project_id}/runs/${run.id}`)}
      />
    </Stack>
  )
}

/**
 * 「派生自 X 的 v3」。
 *
 * 名字是 Fork 那一刻抄下来的，源改名或删除之后这句话仍然读得通。
 * 链接单独判断：源可能已经删了或者当前用户看不到，链过去是 404，
 * 所以只有拿得到 ID 时才做成链接，**文字任何时候都在**。
 */
function ForkSourceTag({ source }: { source: ForkSource }) {
  const label = `派生自 ${source.source_project_name} · ${source.source_version_label}`
  return (
    <Tag icon={<BranchesOutlined />}>
      {source.source_project_id ? (
        <Link to={`/projects/${source.source_project_id}`}>{label}</Link>
      ) : (
        label
      )}
    </Tag>
  )
}
