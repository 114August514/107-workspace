import { PlusIcon } from '@primer/octicons-react'
import { Banner, Button, Label, Link, Text } from '@primer/react'
import { Card } from '@primer/react/experimental'
import { useState } from 'react'
import { Link as RouterLink, useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import type { AsyncErrorView } from '../api/errors'
import { toAsyncError } from '../api/errors'
import type { ComputePlan, Home, Invitation, Workspace } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { CreateWorkspaceDialog } from '../components/workspace/CreateWorkspaceDialog'
import { describeComputeRequest, formatRelative, formatTime } from '../utils/format'
import { roleLabel } from '../utils/roles'
import { runStatusLabel } from '../utils/runStatus'
import styles from './HomePage.module.css'

/** 个人首页：我的 Workspace、最近的 Project、最近提交的 Run 和算力方案目录。 */
export function HomePage({ username }: { username: string }) {
  const navigate = useNavigate()
  const home = useAsync<Home>(() => api.home(), [username])
  const [creating, setCreating] = useState(false)

  const user = home.data?.user
  const workspaces = home.data?.workspaces ?? []
  const projects = home.data?.recent_projects ?? []
  const runs = home.data?.recent_runs ?? []

  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>{user ? `${user.display_name}，欢迎回来` : '首页'}</h1>
        <p className={styles.subtitle}>
          从这里进入 Project，配置运行方案，提交计算作业——不需要自己写 sbatch。
        </p>
      </header>

      {/* 邀请排在空间列表前面：它是需要用户做决定的事，
          而下面几块只是「已经有什么」。没有邀请时整块不渲染。 */}
      <Invitations username={username} onResponded={() => home.reload()} />

      <div className={styles.columns}>
        <div className={styles.main}>
          {/* Card 一旦带 Card.Heading 这类 slot，@primer/react 38 的 Card 就只渲染 slot、
              丢弃其余子元素（数据列表会整体消失），所以标题用普通子元素自己排。 */}
          <Card as="section" padding="normal" className={styles.card} aria-label="我的 Workspace">
            <h2 className={styles.cardTitle}>我的 Workspace</h2>
            <AsyncState
              loading={home.loading}
              loadingText="正在加载工作区…"
              error={toAsyncError(home.error)}
              onRetry={home.reload}
              empty={workspaces.length === 0}
              emptyText="还没有 Workspace"
              emptyDescription="从个人空间开始，或创建一个协作空间把课题组成员拉进来。"
              emptyAction={
                <Button
                  variant="primary"
                  leadingVisual={PlusIcon}
                  onClick={() => setCreating(true)}
                >
                  创建协作空间
                </Button>
              }
            >
              <ul className={styles.list}>
                {workspaces.map((workspace) => (
                  <WorkspaceItem key={workspace.id} workspace={workspace} />
                ))}
              </ul>
            </AsyncState>
          </Card>

          <Card
            as="section"
            padding="normal"
            className={styles.card}
            aria-label="最近使用的 Project"
          >
            <h2 className={styles.cardTitle}>最近使用的 Project</h2>
            <AsyncState
              loading={home.loading}
              loadingText="正在加载项目…"
              error={toAsyncError(home.error)}
              onRetry={home.reload}
              empty={projects.length === 0}
              emptyText="还没有 Project"
              emptyDescription="进入一个 Workspace 创建第一个吧。"
            >
              <ul className={styles.list}>
                {projects.map((project) => (
                  <li key={project.id} className={styles.item}>
                    <div className={styles.itemMain}>
                      <Link
                        as={RouterLink}
                        to={`/projects/${project.id}`}
                        className={styles.itemTitle}
                      >
                        {project.name}
                      </Link>
                      {project.description && (
                        <span className={styles.itemDesc}>{project.description}</span>
                      )}
                    </div>
                    <time
                      className={styles.itemTime}
                      dateTime={project.created_at ?? undefined}
                      title={formatTime(project.created_at)}
                    >
                      {formatRelative(project.created_at)}
                    </time>
                  </li>
                ))}
              </ul>
            </AsyncState>
          </Card>

          <Card as="section" padding="normal" className={styles.card} aria-label="最近提交的 Run">
            <h2 className={styles.cardTitle}>最近提交的 Run</h2>
            <AsyncState
              loading={home.loading}
              loadingText="正在加载 Run…"
              error={toAsyncError(home.error)}
              onRetry={home.reload}
              empty={runs.length === 0}
              emptyText="还没有提交过 Run"
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
          <ComputePlanCatalog />
          <p className={styles.clusterNote}>当前暂不提供节点、分区和队列的实时状态。</p>
        </aside>
      </div>

      <CreateWorkspaceDialog
        open={creating}
        onClose={() => setCreating(false)}
        onCreated={(workspace) => navigate(`/workspaces/${workspace.id}`)}
      />
    </div>
  )
}

function WorkspaceItem({ workspace }: { workspace: Workspace }) {
  return (
    <li className={styles.item}>
      <div className={styles.itemMain}>
        <Link as={RouterLink} to={`/workspaces/${workspace.id}`} className={styles.itemTitle}>
          {workspace.name}
        </Link>
        {workspace.description && <span className={styles.itemDesc}>{workspace.description}</span>}
      </div>
      <div className={styles.itemAside}>
        <Label size="small" variant={workspace.kind === 'personal' ? 'default' : 'accent'}>
          {workspace.kind === 'personal' ? '个人' : '协作'}
        </Label>
        <time
          className={styles.itemTime}
          dateTime={workspace.created_at ?? undefined}
          title={formatTime(workspace.created_at)}
        >
          {formatRelative(workspace.created_at)}
        </time>
      </div>
    </li>
  )
}

/**
 * 待处理的邀请。
 *
 * 放在首页而不是空间里：**被邀请的人还进不去那个空间**，
 * 空间列表只列已加入的，直接访问会 404，因为邀请尚未形成有效 Membership。
 *
 * 渲染成和其他栏目一致的紧凑行列表，而不是蓝色 Banner：
 * 邀请是等待用户做决定的任务，主次操作并排（接受 primary、拒绝 default），
 * 拒绝不是危险操作，不标红。契约里没有邀请人，文案只说加入哪个空间，
 * 不暗示空间本身在邀请。
 */
function Invitations({ username, onResponded }: { username: string; onResponded: () => void }) {
  const invitations = useAsync<Invitation[]>(() => api.listInvitations(), [username])
  const [pendingId, setPendingId] = useState<string | null>(null)
  // 就地显示哪一步失败——首页操作不再弹全局 toast
  const [respondError, setRespondError] = useState<{ name: string; view: AsyncErrorView } | null>(
    null,
  )

  const respond = async (invitation: Invitation, accept: boolean) => {
    setPendingId(invitation.workspace_id)
    setRespondError(null)
    try {
      await api.respondToInvitation(invitation.workspace_id, accept)
      // 处理成功后这条邀请从列表消失，本身就是结果反馈
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
                {/* 只有协作空间能发邀请（后端 invite_member 拒绝 personal），可以直接写死 */}
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

/**
 * 算力方案目录：提交 Run 时可选的预设。
 *
 * 目录只回答「平台有什么方案」，不代表当前 Workspace 已获得对应权益——
 * 权益以后端授权为准。
 */
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
