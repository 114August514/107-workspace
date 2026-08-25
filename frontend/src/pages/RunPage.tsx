import { PulseIcon, StopIcon, SyncIcon } from '@primer/octicons-react'
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
import { useCallback, useState } from 'react'
import { Link as RouterLink, useNavigate, useParams } from 'react-router-dom'

import { api, newIdempotencyKey } from '../api/client'
import { toAsyncError, type AsyncErrorView } from '../api/errors'
import type { LogChunk, RunDetail } from '../api/types'
import { can, isTerminal } from '../api/types'
import { useAsync, usePolling } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { RunStatusTag } from '../components/common/RunStatusTag'
import { PrimerStack } from '../components/primer/PrimerStack'
import { ArtifactPanel } from '../components/run/ArtifactPanel'
import { RunLogPanel } from '../components/run/RunLogPanel'
import { RunSnapshotCard } from '../components/run/RunSnapshotCard'
import { RunTimeline } from '../components/run/RunTimeline'
import styles from '../components/run/run.module.css'
import { formatDuration, formatTime } from '../utils/format'

const POLL_INTERVAL_MS = 2000

type RunTab = 'logs' | 'events' | 'artifacts' | 'snapshot'

interface Feedback {
  variant: 'success' | 'critical'
  title: string
  description?: string
}

function contextualError(error: Error | undefined, message: string): AsyncErrorView | undefined {
  const view = toAsyncError(error)
  return view ? { ...view, message } : undefined
}

function SummaryItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.summaryItem}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

export function RunPage() {
  const { runId = '' } = useParams()
  const navigate = useNavigate()
  const [tab, setTab] = useState<RunTab>('logs')
  const [rerunKey, setRerunKey] = useState(newIdempotencyKey)
  const [rerunning, setRerunning] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [cancelOpen, setCancelOpen] = useState(false)
  const [feedback, setFeedback] = useState<Feedback | null>(null)

  const detail = useAsync<RunDetail>(() => api.getRun(runId), [runId])
  const logs = useAsync<LogChunk[]>(() => api.readLogs(runId), [runId])
  const run = detail.data?.run
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
    <PrimerStack gap="large">
      <AsyncState
        loading={detail.loading}
        loadingText="正在加载 Run…"
        error={contextualError(detail.error, '无法加载这个 Run。')}
        onRetry={detail.reload}
      >
        {detail.data && run ? (
          <>
            <header className={styles.runHeader}>
              <Breadcrumbs>
                <Breadcrumbs.Item as={RouterLink} to="/">
                  首页
                </Breadcrumbs.Item>
                <Breadcrumbs.Item as={RouterLink} to={`/projects/${run.project_id}`}>
                  Project
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
                      variant="primary"
                      leadingVisual={SyncIcon}
                      loading={rerunning}
                      onClick={() => void rerun()}
                    >
                      重新运行
                    </Button>
                  ) : null}
                </div>
              </div>
              <Text as="p" className={styles.headerDescription}>
                由用户 <code className={styles.inlineCode}>{run.initiated_by_user_id}</code> 发起，
                使用 Project 版本{' '}
                <Link as={RouterLink} to={`/versions/${run.project_version_id}`}>
                  {run.project_version_label}
                </Link>
                。
              </Text>
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

            <Card
              as="section"
              padding="normal"
              className={styles.summaryCard}
              aria-label="Run 摘要"
            >
              <dl className={styles.summaryGrid}>
                <SummaryItem label="调度任务">
                  {run.scheduler_job_id ? (
                    <code className={styles.inlineCode}>{run.scheduler_job_id}</code>
                  ) : (
                    '—'
                  )}
                </SummaryItem>
                <SummaryItem label="退出码">
                  <span
                    className={
                      run.exit_code && run.exit_code !== 0 ? styles.exitFailure : undefined
                    }
                  >
                    {run.exit_code ?? '—'}
                  </span>
                </SummaryItem>
                <SummaryItem label="排队时长">{formatDuration(run.queued_seconds)}</SummaryItem>
                <SummaryItem label="运行时长">{formatDuration(run.running_seconds)}</SummaryItem>
                <SummaryItem label="创建时间">{formatTime(run.created_at)}</SummaryItem>
                <SummaryItem label="提交时间">{formatTime(run.submitted_at)}</SummaryItem>
                <SummaryItem label="开始时间">{formatTime(run.started_at)}</SummaryItem>
                <SummaryItem label="结束时间">{formatTime(run.finished_at)}</SummaryItem>
              </dl>
              {run.source_run_id ? (
                <div className={styles.sourceRun}>
                  来源 Run：
                  <Link as={RouterLink} to={`/runs/${run.source_run_id}`}>
                    {run.source_run_id}
                  </Link>
                </div>
              ) : null}
            </Card>

            <section aria-label="Run 信息">
              <UnderlineNav aria-label="Run 信息分类">
                <UnderlineNav.Item
                  aria-current={tab === 'logs' ? 'page' : undefined}
                  onSelect={() => setTab('logs')}
                >
                  日志
                </UnderlineNav.Item>
                <UnderlineNav.Item
                  aria-current={tab === 'events' ? 'page' : undefined}
                  counter={detail.data.events.length}
                  onSelect={() => setTab('events')}
                >
                  执行事件
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
                  {tab === 'logs' ? (
                    <AsyncState
                      loading={logs.loading}
                      loadingText="正在读取 Run 日志…"
                      error={contextualError(logs.error, '无法加载 Run 日志。')}
                      onRetry={logs.reload}
                    >
                      <RunLogPanel chunks={logs.data ?? []} failed={run.status === 'failed'} />
                    </AsyncState>
                  ) : null}
                  {tab === 'events' ? <RunTimeline events={detail.data.events} /> : null}
                  {tab === 'artifacts' ? <ArtifactPanel artifacts={detail.data.artifacts} /> : null}
                  {tab === 'snapshot' ? (
                    <div className={styles.snapshotPanel}>
                      <Banner variant="info">
                        <Banner.Title>运行快照创建后不可修改</Banner.Title>
                        <Banner.Description>
                          后续修改运行方案、运行环境或算力权益，不会改变这里记录的执行事实。
                        </Banner.Description>
                      </Banner>
                      <RunSnapshotCard snapshot={detail.data.snapshot} />
                    </div>
                  ) : null}
                </div>
              </Card>
            </section>
          </>
        ) : null}
      </AsyncState>

      {cancelOpen && run ? (
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
  )
}
