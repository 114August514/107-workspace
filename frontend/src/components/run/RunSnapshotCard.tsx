import { Label, Link, Text } from '@primer/react'
import { Link as RouterLink } from 'react-router-dom'

import type { RunSnapshot } from '../../api/types'
import { describeComputeRequest, formatTime } from '../../utils/format'
import styles from './run.module.css'

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.snapshotRow}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** 不可变运行事实；只展示 Snapshot 已固定的精确身份和配置。 */
export function RunSnapshotCard({ snapshot }: { snapshot: RunSnapshot }) {
  const scheduler = snapshot.scheduler
  const variables = Object.entries(snapshot.environment_variables)
  const secrets = Object.entries(snapshot.secret_references)

  return (
    <dl className={styles.snapshotGrid}>
      <MetaRow label="发起用户">
        <code className={styles.inlineCode}>{snapshot.initiated_by_user_id}</code>
      </MetaRow>
      <MetaRow label="Project 版本">
        <Link as={RouterLink} to={`/versions/${snapshot.project_version_id}`}>
          {snapshot.project_version_id}
        </Link>
      </MetaRow>
      <MetaRow label="来源运行方案">
        {snapshot.source_run_configuration_id ? (
          <code className={styles.inlineCode}>{snapshot.source_run_configuration_id}</code>
        ) : (
          '—'
        )}
      </MetaRow>
      <MetaRow label="执行命令">
        <pre className={styles.command}>{snapshot.command}</pre>
      </MetaRow>
      <MetaRow label="工作目录">
        <code className={styles.inlineCode}>{snapshot.working_directory || '.'}</code>
      </MetaRow>
      <MetaRow label="运行环境">
        <div className={styles.valueStack}>
          <code className={styles.inlineCode}>{snapshot.environment_image}</code>
          <Text size="small" className={styles.muted}>
            精确版本 {snapshot.environment_version_id}
          </Text>
          {snapshot.environment_setup_command ? (
            <code className={styles.inlineCode}>{snapshot.environment_setup_command}</code>
          ) : null}
        </div>
      </MetaRow>
      <MetaRow label="算力请求">
        <div className={styles.valueStack}>
          <span>{describeComputeRequest(snapshot.compute_request)}</span>
          <Text size="small" className={styles.muted}>
            Compute Plan {snapshot.compute_plan_id}
          </Text>
        </div>
      </MetaRow>
      <MetaRow label="调度配置">
        <div className={styles.labelGroup}>
          <Label>集群 {scheduler.cluster || '—'}</Label>
          <Label>Account {scheduler.account || '—'}</Label>
          <Label>Partition {scheduler.partition || '—'}</Label>
          <Label>QoS {scheduler.qos || '—'}</Label>
        </div>
      </MetaRow>
      <MetaRow label="环境变量与 Secret">
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
      </MetaRow>
      <MetaRow label="运行输入">
        {snapshot.input_bindings.length === 0 ? (
          '—'
        ) : (
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
        )}
      </MetaRow>
      <MetaRow label="运行产物规则">
        {snapshot.artifact_rules.length === 0 ? (
          '—'
        ) : (
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
        )}
      </MetaRow>
      <MetaRow label="固定时间">
        <time dateTime={snapshot.created_at}>{formatTime(snapshot.created_at)}</time>
      </MetaRow>
    </dl>
  )
}
