import { ChevronRightIcon } from '@primer/octicons-react'
import { Label, SegmentedControl } from '@primer/react'
import { useState } from 'react'

import type {
  ComputePlan,
  Environment,
  EnvironmentVersion,
  RunConfiguration,
  RunDetail,
} from '../../api/types'
import { formatTime } from '../../utils/format'
import { RunSnapshotSummary } from './RunSnapshotSummary'
import { RunTimeline } from './RunTimeline'
import styles from './run.module.css'

const SNAPSHOT_SECTIONS = [
  { id: 'basic', label: '基本信息' },
  { id: 'environment', label: '环境与算力' },
  { id: 'execution', label: '执行配置' },
] as const

type SnapshotSection = (typeof SNAPSHOT_SECTIONS)[number]['id']

function DefinitionRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.definitionRow}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** User outcome and immutable execution facts first; exact identities remain folded. */
export function RunSummary({
  detail,
  computePlan,
  computePlanLoading,
  computePlanError,
  sourceConfiguration,
  configurationLoading,
  configurationError,
  environmentView,
  environmentLoading,
  environmentError,
}: {
  detail: RunDetail
  computePlan?: ComputePlan
  computePlanLoading: boolean
  computePlanError: boolean
  sourceConfiguration?: RunConfiguration
  configurationLoading: boolean
  configurationError: boolean
  environmentView?: { environment: Environment; version: EnvironmentVersion }
  environmentLoading: boolean
  environmentError: boolean
}) {
  const { run, snapshot } = detail
  const variables = Object.entries(snapshot.environment_variables)
  const secrets = Object.entries(snapshot.secret_references)
  const scheduler = snapshot.scheduler
  const [snapshotSection, setSnapshotSection] = useState<SnapshotSection>('basic')

  const selectSnapshotSection = (index: number) => {
    const section = SNAPSHOT_SECTIONS[index]
    if (section) setSnapshotSection(section.id)
  }

  return (
    <div className={styles.summarySurface} aria-label="Run Summary">
      <div className={styles.summaryOverviewGrid}>
        <section className={styles.summaryExecution} aria-labelledby="run-events-title">
          <h2 id="run-events-title" className={styles.sectionTitle}>
            执行过程
          </h2>
          <RunTimeline detail={detail} />
        </section>

        <section className={styles.snapshotSummary} aria-labelledby="run-snapshot-title">
          <header className={styles.snapshotHeading}>
            <h2 id="run-snapshot-title" className={styles.sectionTitle}>
              运行快照
            </h2>
            <p>本次 Run 的不可变执行配置</p>
          </header>
          <SegmentedControl
            aria-label="运行快照分类"
            fullWidth
            className={styles.snapshotSegments}
            onChange={selectSnapshotSection}
          >
            {SNAPSHOT_SECTIONS.map((section) => (
              <SegmentedControl.Button
                key={section.id}
                selected={snapshotSection === section.id}
                aria-controls="run-snapshot-section"
              >
                {section.label}
              </SegmentedControl.Button>
            ))}
          </SegmentedControl>
          <div
            id="run-snapshot-section"
            className={styles.snapshotSectionPanel}
            role="region"
            aria-label={`${SNAPSHOT_SECTIONS.find((section) => section.id === snapshotSection)?.label}运行快照`}
          >
            <RunSnapshotSummary
              section={snapshotSection}
              detail={detail}
              computePlan={computePlan}
              computePlanLoading={computePlanLoading}
              computePlanError={computePlanError}
              sourceConfiguration={sourceConfiguration}
              configurationLoading={configurationLoading}
              configurationError={configurationError}
              environmentView={environmentView}
              environmentLoading={environmentLoading}
              environmentError={environmentError}
            />
          </div>
        </section>
      </div>

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
    </div>
  )
}
