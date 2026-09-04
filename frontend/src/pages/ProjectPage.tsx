import { BranchesOutlined } from '@ant-design/icons'
import { Card, Tabs, Tag, Typography } from 'antd'
import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import { toAsyncError } from '../api/errors'
import { can } from '../api/types'
import type { ActivityPage, ForkSource, Project, RunConfiguration, RunPage } from '../api/types'
import { useAsync, type AsyncState as AsyncResource } from '../api/useAsync'
import { ActivityFeed } from '../components/activity/ActivityFeed'
import { AsyncSection } from '../components/common/AsyncSection'
import { AsyncState } from '../components/common/AsyncState'
import { ListCard } from '../components/layout/ListCard'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { FileBrowser } from '../components/project/FileBrowser'
import { ProjectSettingsPanel } from '../components/project/ProjectSettingsPanel'
import { VersionPanel } from '../components/project/VersionPanel'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import { RunTable } from '../components/run/RunTable'
import { SubmitRunModal } from '../components/run/SubmitRunModal'
import { RunConfigurationPanel } from '../components/runconfig/RunConfigurationPanel'
import { tablePagination } from '../utils/pagination'

const PAGE_TITLES: Record<string, string> = {
  files: 'Working State',
  versions: 'Version history',
  configurations: 'Run configurations',
  runs: 'Run history',
  activities: 'Project activity',
  settings: 'Settings',
}

/**
 * Project 页面：文件、版本、运行方案和 Run 历史。
 *
 * 页面顺序对应核心闭环：准备代码 -> 保存版本 -> 配置运行方案 -> 提交 Run。
 */
export function ProjectPage({ project }: { project: AsyncResource<Project | undefined> }) {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestedTab = searchParams.get('tab')
  const activeTab =
    requestedTab &&
    ['files', 'versions', 'configurations', 'runs', 'activities', 'settings'].includes(requestedTab)
      ? requestedTab
      : 'files'
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
  const canViewConfig = can(project.data, 'config.view')

  return (
    <Stack gap="large">
      <AsyncSection loading={project.loading} error={project.error}>
        {project.data && (
          <PageHeader
            title={PAGE_TITLES[activeTab]}
            description={project.data.description || '这个 Project 还没有填写说明'}
            tags={forkSource.data ? <ForkSourceTag source={forkSource.data} /> : null}
          />
        )}
      </AsyncSection>

      <Tabs
        activeKey={activeTab}
        onChange={(nextTab) => {
          const next = new URLSearchParams(searchParams)
          next.set('tab', nextTab)
          setSearchParams(next, { replace: true })
        }}
        items={[
          {
            key: 'files',
            label: '① 项目文件',
            children: (
              <Card>
                <FileBrowser projectId={projectId} access={project.data} onChanged={bump} />
              </Card>
            ),
          },
          {
            key: 'versions',
            label: '② 版本',
            children: (
              <Card>
                <VersionPanel
                  projectId={projectId}
                  projectName={project.data?.name ?? ''}
                  access={project.data}
                  refreshToken={token}
                  onVersionSaved={bump}
                />
              </Card>
            ),
          },
          {
            key: 'configurations',
            label: '③ 运行方案',
            children: (
              <Card>
                <RunConfigurationPanel
                  projectId={projectId}
                  access={project.data}
                  defaultConfigurationId={project.data?.default_run_configuration_id ?? null}
                  onSubmitRun={setSubmitting}
                  onChanged={bump}
                />
              </Card>
            ),
          },
          {
            key: 'runs',
            label: '④ Run 历史',
            children: (
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
            ),
          },
          {
            key: 'activities',
            label: '⑤ 近期活动',
            children: (
              <ListCard padded>
                <ActivityFeed
                  page={activities.data}
                  loading={activities.loading}
                  error={activities.error}
                  emptyText="这个 Project 还没有活动记录"
                />
              </ListCard>
            ),
          },
          {
            key: 'settings',
            label: '⑥ 设置',
            children: (
              <Card>
                {canViewConfig ? (
                  <ProjectSettingsPanel
                    projectId={projectId}
                    access={project.data}
                    onChanged={bump}
                  />
                ) : project.data ? (
                  <Typography.Text type="secondary">
                    你没有查看这个 Project 配置的权限。
                  </Typography.Text>
                ) : null}
              </Card>
            ),
          },
        ]}
      />

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
