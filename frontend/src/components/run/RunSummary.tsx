import { Link } from '@primer/react'
import { Link as RouterLink } from 'react-router-dom'

import type { RunConfiguration, RunDetail } from '../../api/types'
import { formatDuration, formatTime } from '../../utils/format'
import { RunStatusTag } from '../common/RunStatusTag'
import styles from './run.module.css'

function SummaryItem({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.summaryItem}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/**
 * Run 默认视图：先回答谁在什么 Project 版本上用什么配置运行、结果如何。
 * scheduler id、exit code 与精确时间折叠在次级诊断区域。
 */
export function RunSummary({
  detail,
  configuration,
  configurationLoading,
  configurationError,
}: {
  detail: RunDetail
  configuration?: RunConfiguration
  configurationLoading: boolean
  configurationError: boolean
}) {
  const { run, snapshot } = detail

  return (
    <div className={styles.summarySurface}>
      <dl className={styles.summaryGrid} aria-label="Run Summary">
        <SummaryItem label="状态">
          <RunStatusTag status={run.status} />
        </SummaryItem>
        <SummaryItem label="发起用户">
          <code className={styles.inlineCode}>{run.initiated_by_user_id}</code>
        </SummaryItem>
        <SummaryItem label="Project 版本">
          <Link as={RouterLink} to={`/versions/${run.project_version_id}`}>
            {run.project_version_label}
          </Link>
        </SummaryItem>
        <SummaryItem label="运行方案">
          {configuration ? (
            configuration.name
          ) : configurationLoading ? (
            '正在读取运行方案…'
          ) : run.source_run_configuration_id ? (
            <span>
              {configurationError ? '运行方案信息暂不可用' : '已删除的运行方案'}
              <code className={styles.secondaryLine}>{run.source_run_configuration_id}</code>
            </span>
          ) : (
            '—'
          )}
        </SummaryItem>
        <SummaryItem label="运行时长">{formatDuration(run.running_seconds)}</SummaryItem>
        <SummaryItem label="排队时长">{formatDuration(run.queued_seconds)}</SummaryItem>
        <SummaryItem label="Compute Plan">
          <code className={styles.inlineCode}>{snapshot.compute_plan_id}</code>
        </SummaryItem>
        <SummaryItem label="执行来源">
          {run.source_run_id ? (
            <span>
              重新运行自{' '}
              <Link as={RouterLink} to={`/runs/${run.source_run_id}`}>
                Run {run.source_run_id}
              </Link>
            </span>
          ) : (
            '首次运行'
          )}
        </SummaryItem>
      </dl>

      <details className={styles.diagnosticDisclosure}>
        <summary>诊断信息</summary>
        <dl className={styles.diagnosticGrid}>
          <SummaryItem label="调度任务">
            {run.scheduler_job_id ? (
              <code className={styles.inlineCode}>{run.scheduler_job_id}</code>
            ) : (
              '—'
            )}
          </SummaryItem>
          <SummaryItem label="退出码">
            <span className={run.exit_code && run.exit_code !== 0 ? styles.exitFailure : undefined}>
              {run.exit_code ?? '—'}
            </span>
          </SummaryItem>
          <SummaryItem label="创建时间">{formatTime(run.created_at)}</SummaryItem>
          <SummaryItem label="提交时间">{formatTime(run.submitted_at)}</SummaryItem>
          <SummaryItem label="开始时间">{formatTime(run.started_at)}</SummaryItem>
          <SummaryItem label="结束时间">{formatTime(run.finished_at)}</SummaryItem>
        </dl>
      </details>
    </div>
  )
}
