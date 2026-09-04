import { ChevronRightIcon } from '@primer/octicons-react'
import { Label } from '@primer/react'

import type { RunDetail } from '../../api/types'
import { formatTime } from '../../utils/format'
import styles from './run.module.css'

function DefinitionRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.definitionRow}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** Exact execution identities and scheduler facts for troubleshooting. */
export function RunDiagnostics({ detail }: { detail: RunDetail }) {
  const { run, snapshot } = detail
  const variables = Object.entries(snapshot.environment_variables)
  const secrets = Object.entries(snapshot.secret_references)
  const scheduler = snapshot.scheduler

  return (
    <details className={styles.diagnosticDisclosure}>
      <summary>
        <ChevronRightIcon className={styles.disclosureChevron} size={16} aria-hidden />
        <span>诊断信息</span>
      </summary>
      <dl className={styles.diagnosticList}>
        <DefinitionRow label="Run ID">
          <code className={styles.inlineCode}>{run.id}</code>
        </DefinitionRow>
        <DefinitionRow label="Snapshot ID">
          <code className={styles.inlineCode}>{snapshot.id}</code>
        </DefinitionRow>
        <DefinitionRow label="Project ID">
          <code className={styles.inlineCode}>{snapshot.project_id}</code>
        </DefinitionRow>
        <DefinitionRow label="发起用户 ID">
          <code className={styles.inlineCode}>{snapshot.initiated_by_user_id}</code>
        </DefinitionRow>
        <DefinitionRow label="Project Version ID">
          <code className={styles.inlineCode}>{snapshot.project_version_id}</code>
        </DefinitionRow>
        <DefinitionRow label="Run Configuration ID">
          {snapshot.source_run_configuration_id ? (
            <code className={styles.inlineCode}>{snapshot.source_run_configuration_id}</code>
          ) : (
            '—'
          )}
        </DefinitionRow>
        <DefinitionRow label="Environment Version ID">
          <code className={styles.inlineCode}>{snapshot.environment_version_id}</code>
        </DefinitionRow>
        <DefinitionRow label="Environment Definition hash">
          <code className={styles.inlineCode}>{snapshot.environment_definition_hash}</code>
        </DefinitionRow>
        <DefinitionRow label="环境执行规格">
          <pre className={styles.command}>
            {JSON.stringify(snapshot.environment_execution_spec, null, 2)}
          </pre>
        </DefinitionRow>
        <DefinitionRow label="Compute Plan ID">
          <code className={styles.inlineCode}>{snapshot.compute_plan_id}</code>
        </DefinitionRow>
        <DefinitionRow label="调度配置">
          <div className={styles.labelGroup}>
            <Label>集群 {scheduler.cluster || '—'}</Label>
            <Label>Account {scheduler.account || '—'}</Label>
            <Label>Partition {scheduler.partition || '—'}</Label>
            <Label>QoS {scheduler.qos || '—'}</Label>
          </div>
        </DefinitionRow>
        <DefinitionRow label="调度任务">
          {run.scheduler_job_id ? (
            <code className={styles.inlineCode}>{run.scheduler_job_id}</code>
          ) : (
            '—'
          )}
        </DefinitionRow>
        <DefinitionRow label="运行状态">
          <code className={styles.inlineCode}>{run.status}</code>
        </DefinitionRow>
        <DefinitionRow label="退出码">
          <span className={run.exit_code && run.exit_code !== 0 ? styles.exitFailure : undefined}>
            {run.exit_code ?? '—'}
          </span>
        </DefinitionRow>
        <DefinitionRow label="环境变量与 Secret">
          {variables.length + secrets.length === 0 ? (
            '—'
          ) : (
            <div className={styles.valueStack}>
              {variables.map(([name, value]) => (
                <code key={name} className={styles.inlineCode}>{`${name}=${value}`}</code>
              ))}
              {secrets.map(([name, reference]) => (
                <div key={name} className={styles.secretReference}>
                  <code className={styles.inlineCode}>{name}</code>
                  <Label variant="done">Secret {reference}，值不写入快照</Label>
                </div>
              ))}
            </div>
          )}
        </DefinitionRow>
        <DefinitionRow label="Snapshot 固定时间">
          <time dateTime={snapshot.created_at}>{formatTime(snapshot.created_at)}</time>
        </DefinitionRow>
        <DefinitionRow label="创建时间">{formatTime(run.created_at)}</DefinitionRow>
        <DefinitionRow label="提交时间">{formatTime(run.submitted_at)}</DefinitionRow>
        <DefinitionRow label="开始时间">{formatTime(run.started_at)}</DefinitionRow>
        <DefinitionRow label="结束时间">{formatTime(run.finished_at)}</DefinitionRow>
      </dl>
    </details>
  )
}
