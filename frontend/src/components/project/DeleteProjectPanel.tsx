import { Banner, Button, Dialog } from '@primer/react'
import { useState } from 'react'
import { api, type DeleteResult } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import type { Project, DeletionImpact } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import styles from './projectSettingsPanel.module.css'

export function DeleteProjectPanel({
  project,
  onDeleted,
}: {
  project: Project
  onDeleted: () => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <div className={styles.danger}>
        <div>
          <strong>删除 Project</strong>
          <p className={styles.sectionDescription}>删除项目及其版本、运行等从属数据。</p>
        </div>
        <Button variant="danger" onClick={() => setOpen(true)}>
          删除 Project
        </Button>
      </div>
      {open && (
        <DeleteProjectDialog
          project={project}
          onClose={() => setOpen(false)}
          onDeleted={onDeleted}
        />
      )}
    </>
  )
}

const PROJECT_DELETION_LABELS: Record<string, string> = {
  working_state_files: 'Working State 文件',
  versions: 'Project Version',
  branches: 'Project Branch',
  configurations: 'Run Configuration',
  variables: 'Project Variable',
  secrets: 'Project Secret',
  runs: 'Run',
  snapshots: 'Run Snapshot',
  run_events: 'Run Event',
  artifacts: 'Artifact',
  activities: 'Activity',
  notifications: 'Notification',
  fork_relation: '当前 Fork 来源记录',
  fork_dependents_preserved: '保留的派生目标来源记录',
}

function DeleteProjectDialog({
  project,
  onClose,
  onDeleted,
}: {
  project: Project
  onClose: () => void
  onDeleted: () => void
}) {
  const impact = useAsync<DeletionImpact>(
    () => api.getProjectDeletionImpact(project.id),
    [project.id],
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<Error>()
  const [result, setResult] = useState<DeleteResult>()
  const failure = toAsyncError(error ?? impact.error)
  const submit = async () => {
    if (busy || !impact.data?.can_delete) return
    setBusy(true)
    setError(undefined)
    try {
      setResult(await api.deleteProject(project.id))
    } catch (cause) {
      setError(cause instanceof Error ? cause : new Error('删除失败，请重试。'))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog
      title={
        result
          ? result === 'deleted'
            ? 'Project 已删除'
            : 'Project 不存在'
          : `删除 Project“${project.name}”？`
      }
      onClose={() => {
        if (result) onDeleted()
        else if (!busy) onClose()
      }}
      footerButtons={
        result
          ? [{ content: '返回首页', onClick: onDeleted, buttonType: 'primary' }]
          : [
              { content: '取消', onClick: onClose, disabled: busy },
              {
                content: busy ? '删除中…' : '删除 Project',
                onClick: () => void submit(),
                buttonType: 'danger',
                disabled: busy || !impact.data?.can_delete,
              },
            ]
      }
    >
      {result ? (
        <p>
          {result === 'deleted'
            ? 'Project 已删除。'
            : 'Project 当前不存在；它可能已被删除，但此结果不能说明由谁删除。'}
        </p>
      ) : (
        <>
          <p>
            删除后，其 Working State、Version、Run Configuration、Run 和从属记录将结束生命周期。
          </p>
          {impact.loading && <p role="status">正在读取删除影响…</p>}
          {impact.data && (
            <>
              <ul>
                {(impact.data.items ?? [])
                  .filter((item) => item.count > 0)
                  .map((item) => (
                    <li key={item.kind}>
                      {PROJECT_DELETION_LABELS[item.kind] ?? item.kind}：{item.count}
                    </li>
                  ))}
              </ul>
              {(impact.data.problems ?? []).length > 0 && (
                <Banner variant="warning">
                  <Banner.Title>当前不能删除</Banner.Title>
                  <Banner.Description>{(impact.data.problems ?? []).join('；')}</Banner.Description>
                </Banner>
              )}
            </>
          )}
          {failure && (
            <Banner variant="critical">
              <Banner.Title>{failure.message}</Banner.Title>
            </Banner>
          )}
          {(impact.error || (impact.data && !impact.data.can_delete)) && (
            <Button onClick={() => void impact.reload()}>重新读取删除影响</Button>
          )}
        </>
      )}
    </Dialog>
  )
}
