import { Banner, Button, Link, Text } from '@primer/react'
import { Card } from '@primer/react/experimental'
import { useState } from 'react'
import { Link as RouterLink } from 'react-router-dom'

import { api } from '../api/client'
import type { AsyncErrorView } from '../api/errors'
import { toAsyncError } from '../api/errors'
import type { ComputePlan, Home, Invitation } from '../api/types'
import type { AsyncState as AsyncResource } from '../api/useAsync'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { describeComputeRequest, formatRelative, formatTime } from '../utils/format'
import { roleLabel } from '../utils/roles'
import { runStatusLabel } from '../utils/runStatus'
import styles from './HomePage.module.css'

interface Props {
  username: string
  home: AsyncResource<Home>
}

/** 个人首页：待处理邀请、最近 Run 和算力方案目录。 */
export function HomePage({ username, home }: Props) {
  const user = home.data?.user
  const runs = home.data?.recent_runs ?? []

  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>{user ? `${user.display_name}，欢迎回来` : '首页'}</h1>
        <p className={styles.subtitle}>
          从这里进入 Project，配置运行方案，提交计算作业——不需要自己写 sbatch。
        </p>
      </header>

      <AsyncState
        loading={home.loading}
        loadingText="正在加载首页内容…"
        error={toAsyncError(home.error)}
        onRetry={home.reload}
      >
        {home.data ? (
          <div className={styles.dashboard}>
            <div className={styles.main}>
              <Invitations username={username} onResponded={home.reload} />
              <Card
                as="section"
                padding="normal"
                className={styles.card}
                aria-label="最近提交的 Run"
              >
                <h2 className={styles.cardTitle}>最近提交的 Run</h2>
                <AsyncState loading={false} empty={runs.length === 0} emptyText="还没有提交过 Run">
                  <ul className={styles.list}>
                    {runs.map((run) => (
                      <li key={run.id} className={styles.item}>
                        <div className={styles.itemMain}>
                          <Link as={RouterLink} to={`/runs/${run.id}`} className={styles.itemTitle}>
                            {run.name}
                          </Link>
                          <span className={styles.itemDesc}>{runStatusLabel(run.status)}</span>
                        </div>
                        <time
                          className={styles.itemTime}
                          dateTime={run.created_at ?? undefined}
                          title={formatTime(run.created_at)}
                        >
                          {formatRelative(run.created_at)}
                        </time>
                      </li>
                    ))}
                  </ul>
                </AsyncState>
              </Card>
            </div>
            <aside className={styles.side}>
              <ComputePlanCatalog />
              <p className={styles.clusterNote}>当前暂不提供节点、分区和队列的实时状态。</p>
            </aside>
          </div>
        ) : null}
      </AsyncState>
    </div>
  )
}

/**
 * 待处理的邀请。
 *
 * 放在首页而不是空间里：被邀请的人还进不去那个空间。
 * 主次操作并排（接受 primary、拒绝 default）；拒绝不是危险操作，不标红。
 */
function Invitations({ username, onResponded }: { username: string; onResponded: () => void }) {
  const invitations = useAsync<Invitation[]>(() => api.listInvitations(), [username])
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [respondError, setRespondError] = useState<{ name: string; view: AsyncErrorView } | null>(
    null,
  )

  const respond = async (invitation: Invitation, accept: boolean) => {
    setPendingId(invitation.workspace_id)
    setRespondError(null)
    try {
      await api.respondToInvitation(invitation.workspace_id, accept)
      invitations.reload()
      onResponded()
    } catch (error) {
      setRespondError({
        name: invitation.workspace_name,
        view: toAsyncError(error as Error) ?? { message: '请求失败。' },
      })
    } finally {
      setPendingId(null)
    }
  }

  const items = invitations.data ?? []
  if (!invitations.loading && !invitations.error && items.length === 0) return null

  return (
    <Card as="section" padding="normal" className={styles.card} aria-label="待处理邀请">
      <h2 className={styles.cardTitle}>待处理邀请</h2>
      <AsyncState
        loading={invitations.loading}
        loadingText="正在加载邀请…"
        error={toAsyncError(invitations.error)}
        onRetry={invitations.reload}
      >
        <ul className={styles.list}>
          {items.map((invitation) => (
            <li key={invitation.workspace_id} className={styles.invitationItem}>
              <div className={styles.invitationMain}>
                <div className={styles.invitationTitle}>{invitation.workspace_name}</div>
                <div className={styles.invitationMeta}>协作空间 · {roleLabel(invitation.role)}</div>
                {invitation.workspace_description ? (
                  <div className={styles.invitationMeta}>{invitation.workspace_description}</div>
                ) : null}
              </div>
              <div className={styles.invitationActions}>
                <Button
                  variant="primary"
                  disabled={pendingId !== null}
                  loading={pendingId === invitation.workspace_id}
                  onClick={() => void respond(invitation, true)}
                >
                  接受邀请
                </Button>
                <Button
                  disabled={pendingId !== null}
                  onClick={() => void respond(invitation, false)}
                >
                  拒绝
                </Button>
              </div>
            </li>
          ))}
        </ul>
        {respondError && (
          <div className={styles.invitationError}>
            <Banner variant="critical">
              <Banner.Title>
                处理「{respondError.name}」的邀请失败：{respondError.view.message}
              </Banner.Title>
              <Banner.Description>
                {respondError.view.problems?.join(' ') ?? '请稍后重试。'}
              </Banner.Description>
            </Banner>
          </div>
        )}
      </AsyncState>
    </Card>
  )
}

/** 算力方案目录只展示平台真实返回的预设，不代表当前空间已获得对应权益。 */
function ComputePlanCatalog() {
  const plans = useAsync<ComputePlan[]>(() => api.computePlans(), [])

  return (
    <Card as="section" padding="normal" className={styles.card} aria-label="算力方案目录">
      <h2 className={styles.cardTitle}>算力方案目录</h2>
      <p className={styles.cardDescription}>提交 Run 时从中选择；实际可用以平台授权为准。</p>
      <AsyncState
        loading={plans.loading}
        loadingText="正在加载算力方案…"
        error={toAsyncError(plans.error)}
        onRetry={plans.reload}
        empty={(plans.data ?? []).length === 0}
        emptyText="暂无算力方案"
      >
        <ul className={styles.planList}>
          {(plans.data ?? []).map((plan) => (
            <li key={plan.id}>
              <div className={styles.planName}>{plan.code}</div>
              {plan.description && <div className={styles.planDesc}>{plan.description}</div>}
              <div className={styles.planSpec}>
                <Text size="small">
                  {describeComputeRequest({
                    nodes: plan.default_nodes,
                    cpus: plan.default_cpus,
                    memory_mb: plan.default_memory_mb,
                    gpus: plan.default_gpus,
                    time_limit_minutes: plan.default_time_limit_minutes,
                  })}
                </Text>
              </div>
            </li>
          ))}
        </ul>
      </AsyncState>
    </Card>
  )
}
