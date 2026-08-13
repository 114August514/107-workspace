import { ReloadOutlined, RedoOutlined, StopOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Descriptions, Tabs, message } from 'antd'
import { useCallback, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api, newIdempotencyKey } from '../api/client'
import type { LogChunk, RunDetail, Workspace } from '../api/types'
import { can, isTerminal } from '../api/types'
import { useAsync, usePolling } from '../api/useAsync'
import { AsyncSection } from '../components/common/AsyncSection'
import { Mono } from '../components/common/Mono'
import { RunStatusTag } from '../components/common/RunStatusTag'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { ArtifactPanel } from '../components/run/ArtifactPanel'
import { RunLogPanel } from '../components/run/RunLogPanel'
import { RunSnapshotCard } from '../components/run/RunSnapshotCard'
import { RunTimeline } from '../components/run/RunTimeline'
import { formatDuration, formatTime } from '../utils/format'

const POLL_INTERVAL_MS = 2000

export function RunPage() {
  const { runId = '' } = useParams()
  const navigate = useNavigate()

  // 一个 Run 页面上的「重新运行」按钮 = 一次意图。
  // 双击、网络重试都复用这个键；真的想再跑一次时（上一次已经成功创建），
  // 才换新键。光靠禁用按钮挡不住网络层的重试。
  const [rerunKey, setRerunKey] = useState(newIdempotencyKey)
  const [rerunning, setRerunning] = useState(false)
  const [cancelling, setCancelling] = useState(false)

  const detail = useAsync<RunDetail>(() => api.getRun(runId), [runId])
  // 取消和重跑都是写操作。不按能力收敛的话，Viewer 看得到按钮、
  // 点了必然 403——后端拦得住，但让用户点一个注定失败的按钮不是好体验
  // 前端能力只管「显不显示入口」，真正的授权仍由后端逐请求校验。
  const workspace = useAsync<Workspace | undefined>(
    async () => (detail.data ? api.getWorkspace(detail.data.run.workspace_id) : undefined),
    [detail.data?.run.workspace_id],
  )
  const logs = useAsync<LogChunk[]>(() => api.readLogs(runId), [runId])

  const run = detail.data?.run
  const active = run !== undefined && !isTerminal(run.status)

  /**
   * 未结束时定时刷新。
   *
   * 先触发一次后端同步，再读 Run——状态只能来自调度系统的轮询结果，
   * 平台不会自己编一个状态出来。
   */
  const refresh = useCallback(
    async (silent = true) => {
      await api.syncRuns().catch(() => undefined)
      await Promise.all([detail.reload({ silent }), logs.reload({ silent })])
    },
    [detail, logs],
  )

  usePolling(() => refresh(true), POLL_INTERVAL_MS, active)

  const cancel = async () => {
    setCancelling(true)
    try {
      await api.cancelRun(runId)
      message.success('已请求取消，最终状态以调度系统为准')
      await refresh(true)
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setCancelling(false)
    }
  }

  const rerun = async () => {
    setRerunning(true)
    try {
      const created = await api.rerun(runId, rerunKey)
      // 这次意图已经落地，下一次点击算新的意图。
      setRerunKey(newIdempotencyKey())
      message.success('已用相同快照创建新的 Run')
      navigate(`/runs/${created.id}`)
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setRerunning(false)
    }
  }

  return (
    <Stack gap="large">
      <AsyncSection loading={detail.loading} error={detail.error}>
        {detail.data && run && (
          <>
            <PageHeader
              breadcrumb={[
                { title: <Link to="/">首页</Link> },
                {
                  title: <Link to={`/projects/${run.project_id}`}>Project</Link>,
                },
                { title: run.name },
              ]}
              title={run.name}
              tags={<RunStatusTag status={run.status} />}
              actions={
                <>
                  <Button icon={<ReloadOutlined />} onClick={() => void refresh(false)}>
                    刷新
                  </Button>
                  {active
                    ? can(workspace.data, 'run.cancel') && (
                        <Button
                          icon={<StopOutlined />}
                          onClick={cancel}
                          danger
                          loading={cancelling}
                        >
                          取消
                        </Button>
                      )
                    : can(workspace.data, 'run.submit') && (
                        <Button icon={<RedoOutlined />} onClick={rerun} loading={rerunning}>
                          重新运行
                        </Button>
                      )}
                </>
              }
            />

            {run.failure_reason && (
              <Alert
                type="error"
                showIcon
                style={{ marginTop: 12 }}
                message="失败原因"
                description={run.failure_reason}
              />
            )}

            <Descriptions
              size="small"
              column={4}
              style={{ marginTop: 16 }}
              items={[
                {
                  key: 'job',
                  label: '调度任务',
                  children: run.scheduler_job_id ? (
                    <Mono copyable>{run.scheduler_job_id}</Mono>
                  ) : (
                    '—'
                  ),
                },
                { key: 'exit', label: '退出码', children: run.exit_code ?? '—' },
                {
                  key: 'queued',
                  label: '排队时长',
                  children: formatDuration(run.queued_seconds),
                },
                {
                  key: 'running',
                  label: '运行时长',
                  children: formatDuration(run.running_seconds),
                },
                { key: 'created', label: '创建', children: formatTime(run.created_at) },
                { key: 'submitted', label: '提交', children: formatTime(run.submitted_at) },
                { key: 'started', label: '开始', children: formatTime(run.started_at) },
                { key: 'finished', label: '结束', children: formatTime(run.finished_at) },
              ]}
            />

            <Tabs
              style={{ marginTop: 16 }}
              defaultActiveKey="logs"
              items={[
                {
                  key: 'logs',
                  label: '日志',
                  children: (
                    <Card>
                      <AsyncSection loading={logs.loading} error={logs.error}>
                        <RunLogPanel chunks={logs.data ?? []} failed={run.status === 'failed'} />
                      </AsyncSection>
                    </Card>
                  ),
                },
                {
                  key: 'events',
                  label: '执行事件',
                  children: (
                    <Card>
                      <RunTimeline events={detail.data.events} />
                    </Card>
                  ),
                },
                {
                  key: 'artifacts',
                  label: `Artifact（${detail.data.artifacts.length}）`,
                  children: (
                    <Card>
                      <ArtifactPanel artifacts={detail.data.artifacts} />
                    </Card>
                  ),
                },
                {
                  key: 'snapshot',
                  label: '复现信息',
                  children: (
                    <Card>
                      <Alert
                        type="info"
                        showIcon
                        style={{ marginBottom: 16 }}
                        message="运行快照创建后不可修改"
                        description="后来修改运行方案、更换环境或调整权益，都不会改变这里的内容。要改任何一项，都需要创建新的 Run。"
                      />
                      <RunSnapshotCard snapshot={detail.data.snapshot} />
                    </Card>
                  ),
                },
              ]}
            />
          </>
        )}
      </AsyncSection>
    </Stack>
  )
}
