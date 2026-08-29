import { Link, Text } from '@primer/react'
import { Link as RouterLink } from 'react-router-dom'

import type { ComputePlan, RunConfiguration, RunDetail } from '../../api/types'
import { describeComputeRequest, formatTime } from '../../utils/format'
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
  projectId,
  configuration,
  configurationLoading,
  configurationError,
  computePlan,
  computePlanLoading,
  computePlanError,
}: {
  detail: RunDetail
  projectId: string
  configuration?: RunConfiguration
  configurationLoading: boolean
  configurationError: boolean
  computePlan?: ComputePlan
  computePlanLoading: boolean
  computePlanError: boolean
}) {
  const { run, snapshot } = detail

  const configurationName = configuration
    ? configuration.name
    : configurationLoading
      ? '正在读取运行方案…'
      : configurationError
        ? '运行方案信息暂不可用'
        : run.source_run_configuration_id
          ? '已删除的运行方案'
          : '未记录运行方案'

  const computePlanName = computePlan
    ? computePlan.name
    : computePlanLoading
      ? '正在读取算力方案…'
      : computePlanError
        ? '算力方案信息暂不可用'
        : '已删除的算力方案'

  return (
    <div className={styles.summarySurface} aria-label="Run Summary">
      <section className={styles.summarySection} aria-labelledby="run-source-title">
        <h2 id="run-source-title">来源</h2>
        <dl className={styles.definitionList}>
          <DefinitionRow label="Project 版本">
            <Link as={RouterLink} to={`/versions/${run.project_version_id}`}>
              {run.project_version_label}
            </Link>
          </DefinitionRow>
          <DefinitionRow label="运行方案">{configurationName}</DefinitionRow>
        </dl>
      </section>

      <section className={styles.summarySection} aria-labelledby="run-compute-title">
        <h2 id="run-compute-title">算力</h2>
        <dl className={styles.definitionList}>
          <DefinitionRow label="算力方案">
            <span>{computePlanName}</span>
            {computePlan ? (
              <Text as="span" size="small" className={styles.secondaryInline}>
                {computePlan.code}
              </Text>
            ) : null}
          </DefinitionRow>
          <DefinitionRow label="资源请求">
            {describeComputeRequest(snapshot.compute_request)}
          </DefinitionRow>
        </dl>
      </section>

      <section className={styles.summarySection} aria-labelledby="run-provenance-title">
        <h2 id="run-provenance-title">来源关系</h2>
        {run.source_run_id ? (
          <p className={styles.provenanceText}>
            重新运行自{' '}
            <Link as={RouterLink} to={`/projects/${projectId}/runs/${run.source_run_id}`}>
              Run #{run.source_run_id.replace(/^run_/, '').slice(0, 8)}
            </Link>
          </p>
        ) : (
          <p className={styles.provenanceText}>首次运行</p>
        )}
      </section>

      <details className={styles.diagnosticDisclosure}>
        <summary>诊断信息</summary>
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
