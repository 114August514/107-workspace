import {
  ArrowLeftIcon,
  ChevronRightIcon,
  KebabHorizontalIcon,
  ProjectIcon,
  StopIcon,
  SyncIcon,
} from '@primer/octicons-react'
import {
  ActionList,
  ActionMenu,
  Banner,
  Button,
  ConfirmationDialog,
  IconButton,
  Link,
} from '@primer/react'
import { useCallback, useEffect, useState } from 'react'
import { Link as RouterLink, useLocation, useNavigate, useParams } from 'react-router-dom'

import { api, newIdempotencyKey } from '../api/client'
import { toAsyncError, type AsyncErrorView } from '../api/errors'
import type {
  ComputePlan,
  Environment,
  EnvironmentVersion,
  LogChunk,
  Project,
  RunConfiguration,
  RunDetail,
} from '../api/types'
import { can, isTerminal } from '../api/types'
import { useAsync, usePolling } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { RunStatusTag } from '../components/common/RunStatusTag'
import { AdjustedRerunModal } from '../components/run/AdjustedRerunModal'
import { ArtifactPanel } from '../components/run/ArtifactPanel'
import { RunDiagnostics } from '../components/run/RunDiagnostics'
import { RunSummary } from '../components/run/RunSummary'
import { RunLogPanel } from '../components/run/RunLogPanel'
import styles from '../components/run/run.module.css'

const POLL_INTERVAL_MS = 2000
interface Feedback {
  variant: 'success' | 'critical'
  title: string
  description?: string
}

interface EnvironmentView {
  environment: Environment
  version: EnvironmentVersion
}

function contextualError(error: Error | undefined, message: string): AsyncErrorView | undefined {
  const view = toAsyncError(error)
  return view ? { ...view, message } : undefined
}

export function RunPage() {
  const { projectId = '', runId = '' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const [rerunKey, setRerunKey] = useState(newIdempotencyKey)
  const [rerunning, setRerunning] = useState(false)
  const [adjustedRerunOpen, setAdjustedRerunOpen] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [logsOpen, setLogsOpen] = useState(false)
  const [artifactsOpen, setArtifactsOpen] = useState(false)
  const detail = useAsync<RunDetail>(() => api.getRun(runId), [runId])
  const logs = useAsync<LogChunk[]>(() => api.readLogs(runId), [runId])
  const plans = useAsync<ComputePlan[]>(() => api.computePlans(), [])
  const run = detail.data?.run
  const project = useAsync<Project | undefined>(
    async () => (run ? api.getProject(run.project_id) : undefined),
    [run?.project_id],
  )
  const configurations = useAsync<RunConfiguration[]>(
    async () => (run ? api.listRunConfigurations(run.project_id) : []),
    [run?.project_id],
  )
  const sourceConfiguration = configurations.data?.find(
    (configuration) => configuration.id === detail.data?.snapshot.source_run_configuration_id,
  )
  const computePlan = plans.data?.find((plan) => plan.id === detail.data?.snapshot.compute_plan_id)
  const environmentVersionId = detail.data?.snapshot.environment_version_id
  const environment = useAsync<EnvironmentView | undefined>(async () => {
    if (!environmentVersionId) return undefined
    const version = await api.environmentVersion(environmentVersionId)
    const resolvedEnvironment = await api.environment(version.environment_id)
    return { environment: resolvedEnvironment, version }
  }, [environmentVersionId])
  const active = run !== undefined && !isTerminal(run.status)

  useEffect(() => {
    if (!run || projectId === run.project_id) return
    navigate(`/projects/${run.project_id}/runs/${run.id}`, { replace: true })
  }, [navigate, projectId, run])

  useEffect(() => {
    setLogsOpen(location.hash === '#run-logs')
    setArtifactsOpen(location.hash === '#run-artifacts')
  }, [location.hash, runId])

  const syncAndReload = useCallback(
    async (silent = true) => {
      await api.syncRuns().catch(() => undefined)
      await Promise.all([detail.reload({ silent }), logs.reload({ silent })])
    },
    [detail, logs],
  )

  usePolling(() => syncAndReload(true), POLL_INTERVAL_MS, active)

  const refresh = async () => {
    setRefreshing(true)
    setFeedback(null)
    await syncAndReload(false)
    setRefreshing(false)
  }

  const cancel = async () => {
    setCancelling(true)
    setFeedback(null)
    try {
      await api.cancelRun(runId)
      setCancelOpen(false)
      setFeedback({
        variant: 'success',
        title: '已请求取消 Run',
        description: '最终状态以调度系统同步结果为准。',
      })
      await syncAndReload(true)
    } catch (error) {
      const view = toAsyncError(error as Error)
      setFeedback({
        variant: 'critical',
        title: '无法取消这个 Run。',
        description: view?.problems?.join(' ') ?? '请重试。',
      })
    } finally {
      setCancelling(false)
    }
  }

  const rerun = async () => {
    setRerunning(true)
    setFeedback(null)
    try {
      const created = await api.rerun(runId, rerunKey)
      setRerunKey(newIdempotencyKey())
      navigate(`/projects/${created.project_id}/runs/${created.id}`)
    } catch (error) {
      const view = toAsyncError(error as Error)
      setFeedback({
        variant: 'critical',
        title: '无法重新运行这个 Run。',
        description: view?.problems?.join(' ') ?? '请重试。',
      })
    } finally {
      setRerunning(false)
    }
  }

  const shortRunId = run?.id.replace(/^run_/, '').slice(0, 8) ?? ''
  const runTitle = run?.name || '未命名 Run'

  return (
    <AsyncState
      loading={detail.loading}
      loadingText="正在加载 Run…"
      error={contextualError(detail.error, '无法加载这个 Run。')}
      onRetry={detail.reload}
    >
      {detail.data && run ? (
        <div className={styles.page}>
          <header className={styles.projectShell} aria-label="Project shell">
            <div className={styles.projectIdentity}>
              <ProjectIcon size={16} aria-hidden />
              {project.data?.owner.kind === 'user_group' ? (
                <Link as={RouterLink} to={`/user-groups/${project.data.owner.id}`}>
                  {project.data.owner.display_name}
                </Link>
              ) : (
                <span>{project.data?.owner.display_name ?? 'Project'}</span>
              )}
              <span className={styles.projectSeparator}>/</span>
              <Link
                as={RouterLink}
                to={`/projects/${run.project_id}`}
                className={styles.projectName}
              >
                {project.data?.name ?? 'Project'}
              </Link>
            </div>
            <nav className={styles.projectNavigation} aria-label="Project navigation">
              <Link as={RouterLink} to={`/projects/${run.project_id}?tab=files`}>
                项目文件
              </Link>
              <Link as={RouterLink} to={`/projects/${run.project_id}?tab=versions`}>
                版本
              </Link>
              <Link as={RouterLink} to={`/projects/${run.project_id}?tab=configurations`}>
                运行方案
              </Link>
              <Link as={RouterLink} to={`/projects/${run.project_id}?tab=runs`} aria-current="page">
                Runs
              </Link>
            </nav>
          </header>

          <div className={styles.runSurface}>
            <header className={styles.runHeader} aria-label="Run header">
              <Link
                as={RouterLink}
                to={`/projects/${run.project_id}?tab=runs`}
                className={styles.backLink}
              >
                <ArrowLeftIcon size={16} aria-hidden />
                Runs
              </Link>
              <div className={styles.titleRow}>
                <div className={styles.titleGroup}>
                  <div className={styles.titleHeading}>
                    <RunStatusTag status={run.status} compact />
                    <h1 className={styles.pageTitle}>{runTitle}</h1>
                    <span className={styles.runIdentifier} title={run.id}>{`#${shortRunId}`}</span>
                  </div>
                </div>
                <div className={styles.headerActions}>
                  {active ? (
                    <>
                      <Button
                        leadingVisual={SyncIcon}
                        loading={refreshing}
                        onClick={() => void refresh()}
                      >
                        刷新
                      </Button>
                      {can(detail.data.run, 'run.cancel') ? (
                        <Button
                          variant="danger"
                          leadingVisual={StopIcon}
                          disabled={cancelling}
                          onClick={() => setCancelOpen(true)}
                        >
                          取消 Run
                        </Button>
                      ) : null}
                    </>
                  ) : (
                    <>
                      {can(detail.data.run, 'run.submit') ? (
                        <>
                          <Button
                            variant="default"
                            leadingVisual={SyncIcon}
                            onClick={() => setAdjustedRerunOpen(true)}
                          >
                            调整后重跑
                          </Button>
                          <Button
                            variant="default"
                            leadingVisual={SyncIcon}
                            loading={rerunning}
                            onClick={() => void rerun()}
                          >
                            重新运行
                          </Button>
                        </>
                      ) : null}
                      <ActionMenu>
                        <ActionMenu.Anchor>
                          <IconButton
                            icon={KebabHorizontalIcon}
                            aria-label="更多 Run 操作"
                            variant="invisible"
                          />
                        </ActionMenu.Anchor>
                        <ActionMenu.Overlay align="end" width="auto">
                          <ActionList>
                            <ActionList.Item disabled={refreshing} onSelect={() => void refresh()}>
                              刷新
                            </ActionList.Item>
                          </ActionList>
                        </ActionMenu.Overlay>
                      </ActionMenu>
                    </>
                  )}
                </div>
              </div>
            </header>

            {feedback ? (
              <Banner variant={feedback.variant}>
                <Banner.Title>{feedback.title}</Banner.Title>
                {feedback.description ? (
                  <Banner.Description>{feedback.description}</Banner.Description>
                ) : null}
              </Banner>
            ) : null}

            {run.failure_reason ? (
              <Banner variant="critical">
                <Banner.Title>Run 执行失败</Banner.Title>
                <Banner.Description>
                  <div className={styles.failureDescription}>
                    <span>{run.failure_reason}</span>
                    <Link href="#run-logs" onClick={() => setLogsOpen(true)}>
                      查看日志
                    </Link>
                  </div>
                </Banner.Description>
              </Banner>
            ) : null}

            <section className={styles.runDetailFlow} aria-label="Run detail">
              <RunSummary
                key={run.id}
                detail={detail.data}
                projectName={project.data?.name}
                computePlan={computePlan}
                computePlanLoading={plans.loading}
                computePlanError={plans.error !== undefined}
                sourceConfiguration={sourceConfiguration}
                configurationLoading={configurations.loading}
                configurationError={configurations.error !== undefined}
                environmentView={environment.data}
                environmentLoading={environment.loading}
                environmentError={environment.error !== undefined}
              />

              <details
                id="run-logs"
                className={`${styles.diagnosticDisclosure} ${styles.logDisclosure}`}
                open={logsOpen}
                onToggle={(event) => setLogsOpen(event.currentTarget.open)}
              >
                <summary>
                  <ChevronRightIcon className={styles.disclosureChevron} size={16} aria-hidden />
                  <span>日志</span>
                </summary>
                <div className={styles.disclosureBody}>
                  <AsyncState
                    loading={logs.loading}
                    loadingText="正在读取 Run 日志…"
                    error={contextualError(logs.error, '无法加载 Run 日志。')}
                    onRetry={logs.reload}
                  >
                    <RunLogPanel
                      key={run.id}
                      runId={run.id}
                      chunks={logs.data ?? []}
                      failed={run.status === 'failed'}
                    />
                  </AsyncState>
                </div>
              </details>

              <details
                id="run-artifacts"
                className={`${styles.diagnosticDisclosure} ${styles.artifactDisclosure}`}
                open={artifactsOpen}
                onToggle={(event) => setArtifactsOpen(event.currentTarget.open)}
              >
                <summary>
                  <ChevronRightIcon className={styles.disclosureChevron} size={16} aria-hidden />
                  <span>运行产物</span>
                </summary>
                <div className={styles.disclosureBody}>
                  {artifactsOpen ? (
                    <ArtifactPanel
                      artifacts={detail.data.artifacts}
                      projectId={run.project_id}
                      runId={run.id}
                    />
                  ) : null}
                </div>
              </details>

              <RunDiagnostics detail={detail.data} />
            </section>
          </div>

          {cancelOpen ? (
            <ConfirmationDialog
              title={`取消 Run“${runTitle}”？`}
              confirmButtonContent="取消 Run"
              confirmButtonType="danger"
              confirmButtonLoading={cancelling}
              cancelButtonContent="返回"
              onClose={(gesture) => {
                if (cancelling) return
                if (gesture === 'confirm') void cancel()
                else setCancelOpen(false)
              }}
            >
              取消会终止这次逻辑执行，但会保留 Run、运行快照以及已经产生的日志和运行产物。
            </ConfirmationDialog>
          ) : null}
          {adjustedRerunOpen && detail.data ? (
            <AdjustedRerunModal
              open
              projectId={run.project_id}
              detail={detail.data}
              onClose={() => setAdjustedRerunOpen(false)}
              onSubmitted={(created) => {
                setAdjustedRerunOpen(false)
                navigate(`/projects/${created.project_id}/runs/${created.id}`)
              }}
            />
          ) : null}
        </div>
      ) : null}
    </AsyncState>
  )
}
