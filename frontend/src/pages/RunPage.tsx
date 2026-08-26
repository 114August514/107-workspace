import { ProjectIcon, PulseIcon, StopIcon, SyncIcon } from '@primer/octicons-react'
import {
  Banner,
  Breadcrumbs,
  Button,
  ConfirmationDialog,
  Link,
  Text,
  UnderlineNav,
} from '@primer/react'
import { Card } from '@primer/react/experimental'
import { useCallback, useEffect, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'

import { api, newIdempotencyKey } from '../api/client'
import { toAsyncError, type AsyncErrorView } from '../api/errors'
import type { LogChunk, Project, RunConfiguration, RunDetail } from '../api/types'
import { can, isTerminal } from '../api/types'
import { useAsync, usePolling } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { RunStatusTag } from '../components/common/RunStatusTag'
import { PrimerStack } from '../components/primer/PrimerStack'
import { ArtifactPanel } from '../components/run/ArtifactPanel'
import { RunLogPanel } from '../components/run/RunLogPanel'
import { RunSnapshotCard } from '../components/run/RunSnapshotCard'
import { RunSummary } from '../components/run/RunSummary'
import { RunTimeline } from '../components/run/RunTimeline'
import styles from '../components/run/run.module.css'

const POLL_INTERVAL_MS = 2000

type RunTab = 'summary' | 'execution' | 'artifacts' | 'snapshot'

interface Feedback {
  variant: 'success' | 'critical'
  title: string
  description?: string
}

function contextualError(error: Error | undefined, message: string): AsyncErrorView | undefined {
  const view = toAsyncError(error)
  return view ? { ...view, message } : undefined
}

export function RunPage() {
  const { runId = '' } = useParams()
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
  const active = run !== undefined && !isTerminal(run.status)

  const syncAndReload = useCallback(async () => {
    await api.syncRuns().catch(() => undefined)
    detail.reload()
    logs.reload()
  }, [detail, logs])

  usePolling(() => void syncAndReload(), POLL_INTERVAL_MS, active)

  const refresh = async () => {
    setRefreshing(true)
    setFeedback(null)
    await syncAndReload()
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
      await syncAndReload()
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
      navigate(`/runs/${created.id}`)
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

  return (
    <AsyncState
      loading={detail.loading}
      loadingText="正在加载 Run…"
      error={contextualError(detail.error, '无法加载这个 Run。')}
      onRetry={detail.reload}
    >
      {detail.data && run ? (
        <PrimerStack gap="large">
          <section className={styles.projectContext} aria-label="Project context">
            <div className={styles.projectIdentity}>
              <ProjectIcon size={20} aria-hidden />
              <div>
                <Text as="span" size="small" className={styles.muted}>
                  Project
                </Text>
                <Link
                  as={RouterLink}
                  to={`/projects/${run.project_id}`}
                  className={styles.projectName}
                >
                  {project.data?.name ?? 'Project'}
                </Link>
              </div>
            </div>
            <UnderlineNav aria-label="Project navigation" className={styles.projectNavigation}>
              <UnderlineNav.Item as={RouterLink} to={`/projects/${run.project_id}`}>
                Project
              </UnderlineNav.Item>
              <UnderlineNav.Item
                as={RouterLink}
                to={`/projects/${run.project_id}?tab=runs`}
                aria-current="page"
              >
                Runs
              </UnderlineNav.Item>
            </UnderlineNav>
          </section>

          <header className={styles.runHeader}>
            <Breadcrumbs>
              <Breadcrumbs.Item as={RouterLink} to="/">
                首页
              </Breadcrumbs.Item>
              <Breadcrumbs.Item as={RouterLink} to={`/projects/${run.project_id}`}>
                {project.data?.name ?? 'Project'}
              </Breadcrumbs.Item>
              <Breadcrumbs.Item as={RouterLink} to={`/projects/${run.project_id}?tab=runs`}>
                Runs
              </Breadcrumbs.Item>
              <Breadcrumbs.Item>{run.name}</Breadcrumbs.Item>
            </Breadcrumbs>
            <div className={styles.titleRow}>
              <PulseIcon size={24} className={styles.titleIcon} aria-hidden />
              <h1 className={styles.pageTitle}>{run.name}</h1>
              <RunStatusTag status={run.status} />
              <div className={styles.headerActions}>
                <Button
                  leadingVisual={SyncIcon}
                  loading={refreshing}
                  onClick={() => void refresh()}
                >
                  刷新
                </Button>
                {active && can(detail.data, 'run.cancel') ? (
                  <Button
                    variant="danger"
                    leadingVisual={StopIcon}
                    disabled={cancelling}
                    onClick={() => setCancelOpen(true)}
                  >
                    取消 Run
                  </Button>
                ) : null}
                {!active && can(detail.data, 'run.submit') ? (
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
            <UnderlineNav aria-label="Run detail navigation">
              <UnderlineNav.Item
                aria-current={tab === 'summary' ? 'page' : undefined}
                onSelect={() => setTab('summary')}
              >
                概览
              </UnderlineNav.Item>
              <UnderlineNav.Item
                aria-current={tab === 'execution' ? 'page' : undefined}
                onSelect={() => setTab('execution')}
              >
                执行
              </UnderlineNav.Item>
              <UnderlineNav.Item
                aria-current={tab === 'artifacts' ? 'page' : undefined}
                counter={detail.data.artifacts.length}
                onSelect={() => setTab('artifacts')}
              >
                运行产物
              </UnderlineNav.Item>
              <UnderlineNav.Item
                aria-current={tab === 'snapshot' ? 'page' : undefined}
                onSelect={() => setTab('snapshot')}
              >
                运行快照
              </UnderlineNav.Item>
            </UnderlineNav>
            <Card className={styles.tabCard}>
              <div className={styles.tabPanel} role="tabpanel">
                {tab === 'summary' ? (
                  <RunSummary
                    detail={detail.data}
                    configuration={sourceConfiguration}
                    configurationLoading={configurations.loading}
                    configurationError={configurations.error !== undefined}
                  />
                ) : null}
                {tab === 'execution' ? (
                  <div className={styles.executionStack}>
                    <section className={styles.executionSection} aria-labelledby="run-events-title">
                      <h2 id="run-events-title" className={styles.sectionTitle}>
                        执行过程
                      </h2>
                      <RunTimeline events={detail.data.events} />
                    </section>
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
                  </div>
                ) : null}
                {tab === 'artifacts' ? <ArtifactPanel artifacts={detail.data.artifacts} /> : null}
                {tab === 'snapshot' ? <RunSnapshotCard snapshot={detail.data.snapshot} /> : null}
              </div>
            </Card>
          </section>

          {cancelOpen ? (
            <ConfirmationDialog
              title={`取消 Run“${run.name}”？`}
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
        </PrimerStack>
      ) : null}
    </AsyncState>
  )
}
