import { ArrowLeftIcon, ProjectIcon, StopIcon, SyncIcon } from '@primer/octicons-react'
import { Banner, Button, ConfirmationDialog, Link, UnderlineNav } from '@primer/react'
import { Card } from '@primer/react/experimental'
import { useCallback, useEffect, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'

import { api, newIdempotencyKey } from '../api/client'
import { toAsyncError, type AsyncErrorView } from '../api/errors'
import type {
  ComputePlan,
  LogChunk,
  Project,
  RunConfiguration,
  RunDetail,
  User,
} from '../api/types'
import { can, isTerminal } from '../api/types'
import { useAsync, usePolling } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { RunStatusTag } from '../components/common/RunStatusTag'
import { ArtifactPanel } from '../components/run/ArtifactPanel'
import { RunLogPanel } from '../components/run/RunLogPanel'
import { RunSummary } from '../components/run/RunSummary'
import styles from '../components/run/run.module.css'
import { formatDuration, formatRelative, formatTime } from '../utils/format'

const POLL_INTERVAL_MS = 2000

type RunTab = 'summary' | 'logs' | 'artifacts'

interface Feedback {
  variant: 'success' | 'critical'
  title: string
  description?: string
}

function contextualError(error: Error | undefined, message: string): AsyncErrorView | undefined {
  const view = toAsyncError(error)
  return view ? { ...view, message } : undefined
}

export function RunPage({ currentUser }: { currentUser?: User }) {
  const { projectId = '', runId = '' } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState<RunTab>('summary')
  const [rerunKey, setRerunKey] = useState(newIdempotencyKey)
  const [rerunning, setRerunning] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [feedback, setFeedback] = useState<Feedback | null>(null)

  useEffect(() => {
    setTab('summary')
  }, [runId])

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
    (configuration) => configuration.id === run?.source_run_configuration_id,
  )
  const computePlan = plans.data?.find((plan) => plan.id === detail.data?.snapshot.compute_plan_id)
  const active = run !== undefined && !isTerminal(run.status)

  useEffect(() => {
    if (!run || projectId === run.project_id) return
    navigate(`/projects/${run.project_id}/runs/${run.id}`, { replace: true })
  }, [navigate, projectId, run])

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
  const automaticName =
    project.data && run ? `${project.data.name} · ${run.project_version_label}` : null
  const runTitle =
    run && automaticName && run.name !== automaticName ? run.name : `Run #${shortRunId}`
  const configurationLabel = sourceConfiguration?.name ?? '运行方案'
  const initiatorLabel =
    currentUser && run && currentUser.id === run.initiated_by_user_id
      ? currentUser.display_name || currentUser.username
      : '其他用户'
  const progressLabel = !run
    ? ''
    : run.status === 'queued'
      ? `已排队 ${formatDuration(run.queued_seconds)}`
      : run.running_seconds === null || run.running_seconds === undefined
        ? '未开始运行'
        : `${isTerminal(run.status) ? '运行' : '已运行'} ${formatDuration(run.running_seconds)}`

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
                  <RunStatusTag status={run.status} />
                  <h1 className={styles.pageTitle}>{runTitle}</h1>
                </div>
                <p className={styles.triggerLine}>
                  <span>{initiatorLabel}</span>
                  <span aria-hidden>·</span>
                  <time dateTime={run.created_at ?? undefined} title={formatTime(run.created_at)}>
                    {formatRelative(run.created_at)}
                  </time>
                  <span aria-hidden>·</span>
                  <span>{progressLabel}</span>
                </p>
              </div>
              <div className={styles.headerActions}>
                <Button
                  leadingVisual={SyncIcon}
                  loading={refreshing}
                  onClick={() => void refresh()}
                >
                  刷新
                </Button>
                {active && can(detail.data.run, 'run.cancel') ? (
                  <Button
                    variant="danger"
                    leadingVisual={StopIcon}
                    disabled={cancelling}
                    onClick={() => setCancelOpen(true)}
                  >
                    取消 Run
                  </Button>
                ) : null}
                {!active && can(detail.data.run, 'run.submit') ? (
                  <Button
                    variant="default"
                    leadingVisual={SyncIcon}
                    loading={rerunning}
                    onClick={() => void rerun()}
                  >
                    重新运行
                  </Button>
                ) : null}
              </div>
            </div>
            <div className={styles.runMeta}>
              <Link as={RouterLink} to={`/versions/${run.project_version_id}`}>
                {run.project_version_label}
              </Link>
              <span aria-hidden>·</span>
              <span>{configurationLabel}</span>
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
              <Banner.Description>{run.failure_reason}</Banner.Description>
            </Banner>
          ) : null}

          <section aria-label="Run detail">
            <UnderlineNav aria-label="Run detail navigation" className={styles.runNavigation}>
              <UnderlineNav.Item
                aria-current={tab === 'summary' ? 'page' : undefined}
                onSelect={() => setTab('summary')}
              >
                概览
              </UnderlineNav.Item>
              <UnderlineNav.Item
                aria-current={tab === 'logs' ? 'page' : undefined}
                onSelect={() => setTab('logs')}
              >
                日志
              </UnderlineNav.Item>
              <UnderlineNav.Item
                aria-current={tab === 'artifacts' ? 'page' : undefined}
                counter={detail.data.artifacts.length}
                onSelect={() => setTab('artifacts')}
              >
                运行产物
              </UnderlineNav.Item>
            </UnderlineNav>
            <Card className={styles.tabCard}>
              <div className={styles.tabPanel} role="tabpanel">
                {tab === 'summary' ? (
                  <RunSummary
                    detail={detail.data}
                    projectId={run.project_id}
                    configuration={sourceConfiguration}
                    configurationLoading={configurations.loading}
                    configurationError={configurations.error !== undefined}
                    computePlan={computePlan}
                    computePlanLoading={plans.loading}
                    computePlanError={plans.error !== undefined}
                  />
                ) : null}
                {tab === 'logs' ? (
                  <section className={styles.executionSection} aria-labelledby="run-logs-title">
                    <h2 id="run-logs-title" className={styles.sectionTitle}>
                      日志
                    </h2>
                    <AsyncState
                      loading={logs.loading}
                      loadingText="正在读取 Run 日志…"
                      error={contextualError(logs.error, '无法加载 Run 日志。')}
                      onRetry={logs.reload}
                    >
                      <RunLogPanel chunks={logs.data ?? []} failed={run.status === 'failed'} />
                    </AsyncState>
                  </section>
                ) : null}
                {tab === 'artifacts' ? <ArtifactPanel artifacts={detail.data.artifacts} /> : null}
              </div>
            </Card>
          </section>

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
        </div>
      ) : null}
    </AsyncState>
  )
}
