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
import { membershipRoleLabel } from '../components/workspace/memberCopy'
import { describeComputeRequest, formatRelative, formatTime } from '../utils/format'
import { runStatusLabel } from '../utils/runStatus'
import { homeCopy, homeTitle, invitationFailureTitle, invitationKind } from './homeCopy'
import styles from './HomePage.module.css'

interface Props {
  username: string
  home: AsyncResource<Home>
}

/** 个人首页：待处理邀请、当前 User 执行上下文、最近 Run 和算力方案目录。 */
export function HomePage({ username, home }: Props) {
  const user = home.data?.user
  const runs = home.data?.recent_runs ?? []

  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>{homeTitle(user?.display_name)}</h1>
        <p className={styles.subtitle}>{homeCopy.subtitle}</p>
      </header>

      <AsyncState
        loading={home.loading}
        loadingText={homeCopy.loading}
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
                aria-label={homeCopy.recentRuns.title}
              >
                <h2 className={styles.cardTitle}>{homeCopy.recentRuns.title}</h2>
                <AsyncState
                  loading={false}
                  loadingText={homeCopy.loading}
                  empty={runs.length === 0}
                  emptyText={homeCopy.recentRuns.empty}
                >
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
              <Card
                as="section"
                padding="normal"
                className={styles.card}
                aria-label="个人执行上下文"
              >
                <h2 className={styles.cardTitle}>个人执行上下文</h2>
                <p className={styles.cardDescription}>
                  Owner：{home.data.personal_execution_context.owner.display_name}
                </p>
                {home.data.personal_execution_context.entitlements.length === 0 ? (
                  <p className={styles.cardDescription}>当前没有可用的 Resource Entitlement。</p>
                ) : (
                  <ul className={styles.list}>
                    {home.data.personal_execution_context.entitlements.map((entitlement) => (
                      <li key={entitlement.id} className={styles.item}>
                        <span className={styles.itemTitle}>{entitlement.compute_plan_name}</span>
                        <span className={styles.itemDesc}>
                          最多 {entitlement.max_concurrent_runs} 个并发 Run
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
              <ComputePlanCatalog />
              <p className={styles.clusterNote}>{homeCopy.compute.realtimeUnavailable}</p>
            </aside>
          </div>
        ) : null}
      </AsyncState>
    </div>
  )
}

/**
 * 待处理的 User Group 邀请。
 *
 * 被邀请的人尚未形成有效 Membership；主次操作并排，拒绝不是危险操作。
 */
function Invitations({ username, onResponded }: { username: string; onResponded: () => void }) {
  const invitations = useAsync<Invitation[]>(() => api.listInvitations(), [username])
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [respondError, setRespondError] = useState<{ name: string; view: AsyncErrorView } | null>(
    null,
  )

  const respond = async (invitation: Invitation, accept: boolean) => {
    setPendingId(invitation.user_group_id)
    setRespondError(null)
    try {
      await api.respondToInvitation(invitation.user_group_id, accept)
      invitations.reload()
      onResponded()
    } catch (error) {
      setRespondError({
        name: invitation.user_group_name,
        view: toAsyncError(error as Error) ?? { message: homeCopy.invitations.fallbackError },
      })
    } finally {
      setPendingId(null)
    }
  }

  const items = invitations.data ?? []
  if (!invitations.loading && !invitations.error && items.length === 0) return null

  return (
    <Card
      as="section"
      padding="normal"
      className={styles.card}
      aria-label={homeCopy.invitations.title}
    >
      <h2 className={styles.cardTitle}>{homeCopy.invitations.title}</h2>
      <AsyncState
        loading={invitations.loading}
        loadingText={homeCopy.invitations.loading}
        error={toAsyncError(invitations.error)}
        onRetry={invitations.reload}
      >
        <ul className={styles.list}>
          {items.map((invitation) => (
            <li key={invitation.user_group_id} className={styles.invitationItem}>
              <div className={styles.invitationMain}>
                <div className={styles.invitationTitle}>{invitation.user_group_name}</div>
                <div className={styles.invitationMeta}>
                  {invitationKind(membershipRoleLabel(invitation.role))}
                </div>
                {invitation.user_group_description ? (
                  <div className={styles.invitationMeta}>{invitation.user_group_description}</div>
                ) : null}
              </div>
              <div className={styles.invitationActions}>
                <Button
                  variant="primary"
                  disabled={pendingId !== null}
                  loading={pendingId === invitation.user_group_id}
                  onClick={() => void respond(invitation, true)}
                >
                  {homeCopy.invitations.accept}
                </Button>
                <Button
                  disabled={pendingId !== null}
                  onClick={() => void respond(invitation, false)}
                >
                  {homeCopy.invitations.reject}
                </Button>
              </div>
            </li>
          ))}
        </ul>
        {respondError && (
          <div className={styles.invitationError}>
            <Banner variant="critical">
              <Banner.Title>
                {invitationFailureTitle(respondError.name, respondError.view.message)}
              </Banner.Title>
              <Banner.Description>
                {respondError.view.problems?.join(' ') ?? homeCopy.invitations.fallbackNextStep}
              </Banner.Description>
            </Banner>
          </div>
        )}
      </AsyncState>
    </Card>
  )
}

/** 算力方案目录只展示平台真实返回的预设，不代表当前用户已获得对应权益。 */
function ComputePlanCatalog() {
  const plans = useAsync<ComputePlan[]>(() => api.computePlans(), [])

  return (
    <Card as="section" padding="normal" className={styles.card} aria-label={homeCopy.compute.title}>
      <h2 className={styles.cardTitle}>{homeCopy.compute.title}</h2>
      <p className={styles.cardDescription}>{homeCopy.compute.description}</p>
      <AsyncState
        loading={plans.loading}
        loadingText={homeCopy.compute.loading}
        error={toAsyncError(plans.error)}
        onRetry={plans.reload}
        empty={(plans.data ?? []).length === 0}
        emptyText={homeCopy.compute.empty}
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
