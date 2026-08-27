import { ChevronLeftIcon, ChevronRightIcon } from '@primer/octicons-react'
import { Button, Link, Text } from '@primer/react'
import { Link as RouterLink } from 'react-router-dom'

import type { Run } from '../../api/types'
import { formatDuration, formatTime } from '../../utils/format'
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
}

function Cell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <td className={styles.tableCell} data-label={label}>
      {children}
    </td>
  )
}

/** Project 的 Run 历史；桌面为高密度表格，窄屏折叠为逐条执行摘要。 */
export function RunTable({ runs, pagination = false }: Props) {
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
              <th scope="col">Project 版本</th>
              <th scope="col">发起用户</th>
              <th scope="col">排队</th>
              <th scope="col">运行</th>
              <th scope="col">退出码</th>
              <th scope="col">创建时间</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
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
                    {run.name}
                  </Link>
                  {run.scheduler_job_id ? (
                    <Text as="span" size="small" className={styles.secondaryLine}>
                      调度任务 {run.scheduler_job_id}
                    </Text>
                  ) : null}
                </Cell>
                <Cell label="Project 版本">
                  <Link as={RouterLink} to={`/versions/${run.project_version_id}`}>
                    {run.project_version_label}
                  </Link>
                </Cell>
                <Cell label="发起用户">
                  <code className={styles.inlineCode}>{run.initiated_by_user_id}</code>
                </Cell>
                <Cell label="排队">{formatDuration(run.queued_seconds)}</Cell>
                <Cell label="运行">{formatDuration(run.running_seconds)}</Cell>
                <Cell label="退出码">
                  <span
                    className={
                      run.exit_code && run.exit_code !== 0 ? styles.exitFailure : undefined
                    }
                  >
                    {run.exit_code ?? '—'}
                  </span>
                </Cell>
                <Cell label="创建时间">
                  <time dateTime={run.created_at ?? undefined}>{formatTime(run.created_at)}</time>
                </Cell>
              </tr>
            ))}
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
