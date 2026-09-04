import { Label, Link, Text } from '@primer/react'
import { Link as RouterLink } from 'react-router-dom'

import type {
  ComputePlan,
  Environment,
  EnvironmentVersion,
  RunConfiguration,
  RunDetail,
} from '../../api/types'
import { formatDuration, formatMemory, formatMinutes, formatTime } from '../../utils/format'
import styles from './run.module.css'

function SnapshotFact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.snapshotFact}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** User-readable immutable execution facts; raw identities stay in Diagnostics. */
export function RunSnapshotSummary({
  section,
  detail,
  projectName,
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
  section: 'basic' | 'environment' | 'execution'
  detail: RunDetail
  projectName?: string
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
  const request = snapshot.compute_request
  const resources = [`${request.nodes} 节点`, `${request.cpus} 核`, formatMemory(request.memory_mb)]
  if (request.gpus > 0) resources.push(`${request.gpus} 张 GPU`)

  const configurationName = sourceConfiguration
    ? sourceConfiguration.name
    : configurationLoading
      ? '正在读取运行方案…'
      : configurationError
        ? '运行方案信息暂不可用'
        : '已删除的运行方案'
  const computePlanName = computePlan
    ? computePlan.name
    : computePlanLoading
      ? '正在读取算力方案…'
      : computePlanError
        ? '算力方案信息暂不可用'
        : '已删除的算力方案'

  return (
    <dl className={styles.snapshotFacts}>
      {section === 'basic' ? (
        <>
          <SnapshotFact label="发起用户">
            <span>{run.initiated_by_username ?? '未知用户'}</span>
          </SnapshotFact>
          <SnapshotFact label="创建时间">
            <time dateTime={run.created_at ?? undefined}>{formatTime(run.created_at)}</time>
          </SnapshotFact>
          <SnapshotFact label="运行时长">
            <span>{formatDuration(run.running_seconds)}</span>
          </SnapshotFact>
          {run.queued_seconds !== null && run.queued_seconds !== undefined ? (
            <SnapshotFact label="排队时长">
              <span>{formatDuration(run.queued_seconds)}</span>
            </SnapshotFact>
          ) : null}
          <SnapshotFact label="Project 版本">
            <Link as={RouterLink} to={`/versions/${run.project_version_id}`}>
              {projectName ? `${projectName} · ` : ''}
              {run.project_version_label}
            </Link>
          </SnapshotFact>
          <SnapshotFact label="运行方案">
            <span>{configurationName}</span>
          </SnapshotFact>
          {run.source_run_id ? (
            <SnapshotFact label="来源 Run">
              <Link as={RouterLink} to={`/projects/${run.project_id}/runs/${run.source_run_id}`}>
                Run #{run.source_run_id.replace(/^run_/, '').slice(0, 8)}
              </Link>
            </SnapshotFact>
          ) : null}
        </>
      ) : null}

      {section === 'environment' ? (
        <>
          <SnapshotFact label="运行环境">
            {environmentView ? (
              <Link as={RouterLink} to={`/environment-versions/${environmentView.version.id}`}>
                {environmentView.environment.name} · {environmentView.version.version}
              </Link>
            ) : environmentLoading ? (
              '正在读取运行环境…'
            ) : environmentError ? (
              '运行环境信息暂不可用'
            ) : (
              '已删除的运行环境'
            )}
          </SnapshotFact>
          <SnapshotFact label="算力">
            <div className={styles.snapshotValueStack}>
              <strong>{computePlanName}</strong>
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
          </SnapshotFact>
        </>
      ) : null}

      {section === 'execution' ? (
        <>
          <SnapshotFact label="命令">
            <pre className={styles.command}>{snapshot.command}</pre>
          </SnapshotFact>
          <SnapshotFact label="工作目录">
            <code className={styles.inlineCode}>{snapshot.working_directory || '.'}</code>
          </SnapshotFact>
          {snapshot.input_bindings.length > 0 ? (
            <SnapshotFact label="运行输入">
              <ul className={styles.compactList}>
                {snapshot.input_bindings.map((binding) => (
                  <li key={`${binding.source_type}:${binding.source_id}:${binding.access_path}`}>
                    <code className={styles.inlineCode}>
                      {binding.source_type}:{binding.source_id}
                      {binding.source_subpath ? `/${binding.source_subpath}` : ''} →{' '}
                      {binding.access_path}
                    </code>
                  </li>
                ))}
              </ul>
            </SnapshotFact>
          ) : null}
          {snapshot.artifact_rules.length > 0 ? (
            <SnapshotFact label="运行产物规则">
              <div className={styles.labelGroup}>
                {snapshot.artifact_rules.map((rule) => (
                  <Label
                    key={`${rule.name}:${rule.path}`}
                    variant={rule.optional ? 'secondary' : 'accent'}
                  >
                    {rule.path} · {rule.optional ? '可选' : '必需'}
                  </Label>
                ))}
              </div>
            </SnapshotFact>
          ) : null}
        </>
      ) : null}
    </dl>
  )
}
