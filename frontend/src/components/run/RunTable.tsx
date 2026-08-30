import { ChevronLeftIcon, ChevronRightIcon } from '@primer/octicons-react'
import { Button, Link, Text } from '@primer/react'
import { Link as RouterLink } from 'react-router-dom'

import type { Run } from '../../api/types'
import { formatDuration, formatRelative, formatTime } from '../../utils/format'
import { RunStatusTag } from '../common/RunStatusTag'
import styles from './run.module.css'

interface RunPagination {
  current?: number
  pageSize?: number
  total?: number
  onChange?: (page: number, pageSize: number) => void
}

interface Props {
  runs: Run[]
  /** 不传表示这是一个不分页的短列表（比如首页的最近 Run）。 */
  pagination?: RunPagination | false
  projectName?: string
}

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <td className={styles.tableCell} data-label={label}>
      {children}
    </td>
  )
}

/** Project 的 Run 历史；桌面为高密度表格，窄屏折叠为逐条执行摘要。 */
export function RunTable({ runs, pagination = false, projectName }: Props) {
  const current = pagination ? (pagination.current ?? 1) : 1
  const pageSize = pagination ? (pagination.pageSize ?? Math.max(runs.length, 1)) : 1
  const total = pagination ? (pagination.total ?? runs.length) : runs.length
  const pageCount = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div>
      <div className={styles.tableScroller}>
        <table className={styles.runTable} aria-label="Run 历史">
          <thead>
            <tr>
              <th scope="col">状态</th>
              <th scope="col">Run</th>
              <th scope="col">执行时间</th>
              <th scope="col">创建时间</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => {
              const automaticName = projectName
                ? `${projectName} · ${run.project_version_label}`
                : null
              const displayName =
                automaticName && run.name === automaticName
                  ? `Run #${run.id.replace(/^run_/, '').slice(0, 8)}`
                  : run.name
              const queued = formatDuration(run.queued_seconds)
              const execution =
                run.status === 'queued'
                  ? `排队 ${queued}`
                  : run.running_seconds === null || run.running_seconds === undefined
                    ? '未记录运行时间'
                    : `运行 ${formatDuration(run.running_seconds)}`

              return (
                <tr key={run.id}>
                  <Cell label="状态">
                    <RunStatusTag status={run.status} />
                  </Cell>
                  <Cell label="Run">
                    <Link
                      as={RouterLink}
                      to={`/projects/${run.project_id}/runs/${run.id}`}
                      className={styles.primaryLink}
                    >
                      {displayName}
                    </Link>
                    <div className={styles.runContextLine}>
                      <Link as={RouterLink} to={`/versions/${run.project_version_id}`}>
                        {run.project_version_label}
                      </Link>
                      <span aria-hidden>·</span>
                      <span>{run.initiated_by_username ?? '未知用户'}</span>
                    </div>
                  </Cell>
                  <Cell label="执行时间">
                    <span className={styles.executionPrimary}>{execution}</span>
                    {run.status !== 'queued' &&
                    run.queued_seconds !== null &&
                    run.queued_seconds !== undefined ? (
                      <Text as="span" size="small" className={styles.secondaryLine}>
                        排队 {queued}
                      </Text>
                    ) : null}
                  </Cell>
                  <Cell label="创建时间">
                    <time dateTime={run.created_at ?? undefined} title={formatTime(run.created_at)}>
                      {formatRelative(run.created_at)}
                    </time>
                  </Cell>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {pagination && pageCount > 1 ? (
        <nav className={styles.pagination} aria-label="Run 历史分页">
          <Text size="small" className={styles.muted}>
            共 {total} 条，第 {current} / {pageCount} 页
          </Text>
          <div className={styles.paginationActions}>
            <Button
              size="small"
              leadingVisual={ChevronLeftIcon}
              disabled={current <= 1}
              onClick={() => pagination.onChange?.(current - 1, pageSize)}
            >
              上一页
            </Button>
            <Button
              size="small"
              trailingVisual={ChevronRightIcon}
              disabled={current >= pageCount}
              onClick={() => pagination.onChange?.(current + 1, pageSize)}
            >
              下一页
            </Button>
          </div>
        </nav>
      ) : null}
    </div>
  )
}
