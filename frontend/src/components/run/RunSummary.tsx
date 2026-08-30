import { ChevronRightIcon } from '@primer/octicons-react'
import { Text } from '@primer/react'

import type { ComputePlan, RunDetail } from '../../api/types'
import { formatMemory, formatMinutes, formatTime } from '../../utils/format'
import { RunSnapshotCard } from './RunSnapshotCard'
import { RunTimeline } from './RunTimeline'
import styles from './run.module.css'

function DefinitionRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.definitionRow}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** User-facing Run outcome first; exact execution identifiers remain in diagnostics. */
export function RunSummary({
  detail,
  computePlan,
  computePlanLoading,
  computePlanError,
}: {
  detail: RunDetail
  computePlan?: ComputePlan
  computePlanLoading: boolean
  computePlanError: boolean
}) {
  const { run, snapshot } = detail
  const computePlanName = computePlan
    ? computePlan.name
    : computePlanLoading
      ? '正在读取算力方案…'
      : computePlanError
        ? '算力方案信息暂不可用'
        : '已删除的算力方案'
  const request = snapshot.compute_request
  const resources = [`${request.nodes} 节点`, `${request.cpus} 核`, formatMemory(request.memory_mb)]
  if (request.gpus > 0) resources.push(`${request.gpus} 张 GPU`)

  return (
    <div className={styles.summarySurface} aria-label="Run Summary">
      <section className={styles.summarySection} aria-labelledby="run-compute-title">
        <h2 id="run-compute-title">算力</h2>
        <div className={styles.summaryValueStack}>
          <strong className={styles.summaryPrimaryValue}>{computePlanName}</strong>
          <span>{resources.join(' · ')}</span>
          <Text as="span" size="small" className={styles.muted}>
            最长运行 {formatMinutes(request.time_limit_minutes)}
          </Text>
          {computePlan ? (
            <Text as="span" size="small" className={styles.muted}>
              {computePlan.code}
            </Text>
          ) : null}
        </div>
      </section>

      <section className={styles.summaryExecution} aria-labelledby="run-events-title">
        <h2 id="run-events-title" className={styles.sectionTitle}>
          执行过程
        </h2>
        <RunTimeline detail={detail} />
      </section>

      <details className={styles.snapshotDisclosure}>
        <summary>
          <ChevronRightIcon className={styles.disclosureChevron} size={16} aria-hidden />
          <span>完整运行快照</span>
        </summary>
        <div className={styles.snapshotDisclosureBody}>
          <RunSnapshotCard snapshot={snapshot} />
        </div>
      </details>

      <details className={styles.diagnosticDisclosure}>
        <summary>
          <ChevronRightIcon className={styles.disclosureChevron} size={16} aria-hidden />
          <span>诊断信息</span>
        </summary>
        <dl className={styles.diagnosticList}>
          <DefinitionRow label="发起用户 ID">
            <code className={styles.inlineCode}>{run.initiated_by_user_id}</code>
          </DefinitionRow>
          <DefinitionRow label="运行方案 ID">
            {run.source_run_configuration_id ? (
              <code className={styles.inlineCode}>{run.source_run_configuration_id}</code>
            ) : (
              '—'
            )}
          </DefinitionRow>
          <DefinitionRow label="Compute Plan ID">
            <code className={styles.inlineCode}>{snapshot.compute_plan_id}</code>
          </DefinitionRow>
          <DefinitionRow label="调度任务">
            {run.scheduler_job_id ? (
              <code className={styles.inlineCode}>{run.scheduler_job_id}</code>
            ) : (
              '—'
            )}
          </DefinitionRow>
          <DefinitionRow label="退出码">
            <span className={run.exit_code && run.exit_code !== 0 ? styles.exitFailure : undefined}>
              {run.exit_code ?? '—'}
            </span>
          </DefinitionRow>
          <DefinitionRow label="创建时间">{formatTime(run.created_at)}</DefinitionRow>
          <DefinitionRow label="提交时间">{formatTime(run.submitted_at)}</DefinitionRow>
          <DefinitionRow label="开始时间">{formatTime(run.started_at)}</DefinitionRow>
          <DefinitionRow label="结束时间">{formatTime(run.finished_at)}</DefinitionRow>
        </dl>
      </details>
    </div>
  )
}
