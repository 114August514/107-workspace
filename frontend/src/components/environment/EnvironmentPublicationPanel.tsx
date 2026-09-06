import { Button, Label } from '@primer/react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'
import type { EnvironmentPublicationAttempt } from '../../api/types'
import { useAsync, usePolling } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { normalizeError } from '../common/asyncStateError'
import styles from '../../pages/Environment.module.css'
import overview from '../usergroup/overview.module.css'

const statuses = {
  pending: '等待处理',
  processing: '处理中',
  succeeded: '已发布',
  failed: '发布失败',
}
const stages: Record<string, string> = {
  downloading: '正在下载 SIF',
  converting: '正在拉取并转换镜像',
  validating: '正在校验',
  publishing: '正在发布',
}
export function EnvironmentPublicationPanel({
  environmentId,
  onRetry,
  onPublished,
}: {
  environmentId: string
  onRetry: (attempt: EnvironmentPublicationAttempt) => void
  onPublished: () => void
}) {
  const attempts = useAsync(
    () => api.environmentPublicationAttempts(environmentId),
    [environmentId],
  )
  const pending =
    attempts.data?.some((item) => ['pending', 'processing'].includes(item.status)) ?? false
  usePolling(
    async () => {
      const hadPending = pending
      await attempts.reload({ silent: true })
      if (hadPending) onPublished()
    },
    2000,
    pending,
  )
  return (
    <section className={overview.section}>
      <div className={overview.sectionHeader}>
        <h2 className={overview.sectionTitle}>发布记录</h2>
        <Button size="small" onClick={() => void attempts.reload()}>
          刷新
        </Button>
      </div>
      <AsyncState
        loading={attempts.loading}
        loadingText="正在加载发布记录…"
        error={normalizeError(attempts.error)}
        onRetry={attempts.reload}
        empty={attempts.data?.length === 0}
        emptyText="还没有发布记录。"
      >
        <ul className={overview.rowList}>
          {attempts.data?.map((attempt) => (
            <li key={attempt.id} className={`${overview.row} ${styles.attempt}`}>
              <div className={styles.sectionHeading}>
                <strong>{attempt.version}</strong>
                <Label
                  variant={
                    attempt.status === 'failed'
                      ? 'danger'
                      : attempt.status === 'succeeded'
                        ? 'success'
                        : 'secondary'
                  }
                >
                  {stages[attempt.stage] && attempt.status === 'processing'
                    ? stages[attempt.stage]
                    : statuses[attempt.status]}
                </Label>
              </div>
              {attempt.description && <p>{attempt.description}</p>}
              <p className={styles.itemMeta}>
                {new Date(attempt.created_at).toLocaleString()} ·{' '}
                {attempt.runtime_kind === 'modules' ? 'Environment Modules' : 'Apptainer SIF'}
              </p>
              {attempt.source_uri && (
                <details className={styles.disclosure}>
                  <summary>镜像来源</summary>
                  <code className={styles.codeBlock}>{attempt.source_uri}</code>
                </details>
              )}
              <p role={attempt.status === 'processing' ? 'status' : undefined}>
                {attempt.failure_reason || attempt.validation_summary || '已加入发布队列。'}
              </p>
              {attempt.version_id && (
                <Link to={`/environment-versions/${attempt.version_id}`}>查看版本</Link>
              )}
              {attempt.status === 'failed' && (
                <Button size="small" onClick={() => onRetry(attempt)}>
                  重新发布
                </Button>
              )}
            </li>
          ))}
        </ul>
      </AsyncState>
    </section>
  )
}
