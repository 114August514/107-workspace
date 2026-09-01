import { BranchesOutlined } from '@ant-design/icons'
import { Card, Empty, Tag } from 'antd'
import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import type { ActivityPage, ForkSource, Project, RunConfiguration, RunPage } from '../api/types'
import { useAsync, type AsyncState as AsyncResource } from '../api/useAsync'
import { ActivityFeed } from '../components/activity/ActivityFeed'
import { AsyncSection } from '../components/common/AsyncSection'
import { AsyncState } from '../components/common/AsyncState'
import { ListCard } from '../components/layout/ListCard'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { FileBrowser } from '../components/project/FileBrowser'
import { VersionPanel } from '../components/project/VersionPanel'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import { RunTable } from '../components/run/RunTable'
import { SubmitRunModal } from '../components/run/SubmitRunModal'
import { RunConfigurationPanel } from '../components/runconfig/RunConfigurationPanel'
import { tablePagination } from '../utils/pagination'
import styles from './ProjectPage.module.css'

type ProjectSection = 'files' | 'runs' | 'activity' | 'settings'
type FilesView = 'working' | 'changes' | 'versions'
type RunsView = 'history' | 'configurations'

const PAGE_TITLES = {
  working: 'Working State',
  changes: 'Changes',
  versions: 'Versions',
  history: 'Run history',
  configurations: 'Run configurations',
  activity: 'Activity',
  settings: 'Settings',
} as const

function resolveProjectLocation(search: URLSearchParams): {
  section: ProjectSection
  view: FilesView | RunsView | 'activity' | 'settings'
} {
  const tab = search.get('tab')
  const view = search.get('view')
  if (tab === 'activity' || tab === 'activities') return { section: 'activity', view: 'activity' }
  if (tab === 'settings') return { section: 'settings', view: 'settings' }
  if (tab === 'runs' || tab === 'configurations') {
    return {
      section: 'runs',
      view: tab === 'configurations' || view === 'configurations' ? 'configurations' : 'history',
    }
  }
  return {
    section: 'files',
    view:
      tab === 'versions' || view === 'versions'
        ? 'versions'
        : view === 'changes'
          ? 'changes'
          : 'working',
  }
}

function projectViewHref(projectId: string, section: ProjectSection, view?: FilesView | RunsView) {
  if (section === 'activity' || section === 'settings')
    return `/projects/${projectId}?tab=${section}`
  return `/projects/${projectId}?tab=${section}&view=${view}`
}

function ProjectSubNavigation({
  projectId,
  section,
  view,
}: {
  projectId: string
  section: ProjectSection
  view: FilesView | RunsView | 'activity' | 'settings'
}) {
  const items =
    section === 'files'
      ? ([
          ['working', 'Working State'],
          ['changes', 'Changes'],
          ['versions', 'Versions'],
        ] as const)
      : section === 'runs'
        ? ([
            ['history', 'History'],
            ['configurations', 'Configurations'],
          ] as const)
        : null
  if (!items) return null
  return (
    <nav className={styles.subNavigation} aria-label={`${section} sections`}>
      {items.map(([itemView, label]) => (
        <Link
          key={itemView}
          to={projectViewHref(projectId, section, itemView)}
          className={styles.subNavigationLink}
          aria-current={view === itemView ? 'page' : undefined}
        >
          {label}
        </Link>
      ))}
    </nav>
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
  const { section, view } = resolveProjectLocation(new URLSearchParams(location.search))
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

  const content =
    view === 'working' ? (
      <Card>
        <FileBrowser projectId={projectId} access={project.data} onChanged={bump} />
      </Card>
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

  return (
    <Stack gap="large">
      <AsyncSection loading={project.loading} error={project.error}>
        {project.data && (
          <PageHeader
            title={PAGE_TITLES[view]}
            description={project.data.description || '这个 Project 还没有填写说明'}
            tags={forkSource.data ? <ForkSourceTag source={forkSource.data} /> : null}
          />
        )}
      </AsyncSection>

      <ProjectSubNavigation projectId={projectId} section={section} view={view} />
      {content}

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
