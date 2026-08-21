import { PlusIcon } from '@primer/octicons-react'
import { Button, UnderlineNav } from '@primer/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { LegacyWorkspaceContext, SharedResource } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { normalizeError } from '../common/asyncStateError'
import { PrimerListCard } from '../primer/PrimerListCard'
import { PrimerStack } from '../primer/PrimerStack'
import { PrimerRoot } from '../../primer/setup'
import { CreateSharedResourceModal } from './CreateSharedResourceModal'
import { SharedResourceTable } from './SharedResourceTable'

interface Props {
  workspace: LegacyWorkspaceContext
}

/**
 * 嵌在 WorkspacePage 的 antd Tab 里的共享资源面板。
 *
 * 它返回的 JSX 自己只用 Primer，但需要 Primer token 才能正确渲染——
 * 按 #28 的约定，每个 Primer surface 在自己根部套 <PrimerRoot>，
 * 不依赖外层 antd 页面提供主题。
 */
export function SharedResourcePanel({ workspace }: Props) {
  const navigate = useNavigate()
  const canManage = can(workspace, 'shared_resource.manage')

  const ownResources = useAsync<SharedResource[]>(
    () => api.listWorkspaceSharedResources(workspace.id),
    [workspace.id],
  )
  const platformResources = useAsync<SharedResource[]>(() => api.listPlatformSharedResources(), [])
  const [creating, setCreating] = useState(false)
  const [tab, setTab] = useState('own')

  return (
    <PrimerRoot>
      <PrimerStack gap="middle">
        {canManage && (
          <div>
            <Button variant="primary" leadingVisual={PlusIcon} onClick={() => setCreating(true)}>
              创建共享资源
            </Button>
          </div>
        )}

        <UnderlineNav aria-label="共享资源">
          <UnderlineNav.Item
            aria-current={tab === 'own' ? 'page' : undefined}
            onSelect={() => setTab('own')}
          >
            本空间
          </UnderlineNav.Item>
          <UnderlineNav.Item
            aria-current={tab === 'platform' ? 'page' : undefined}
            onSelect={() => setTab('platform')}
          >
            平台公共
          </UnderlineNav.Item>
        </UnderlineNav>

        {tab === 'own' && (
          <PrimerListCard>
            <AsyncState
              loading={ownResources.loading}
              loadingText="正在加载共享资源…"
              error={normalizeError(ownResources.error)}
              empty={(ownResources.data ?? []).length === 0}
              emptyText="这里还没有共享资源。"
              emptyDescription={
                canManage
                  ? '创建共享资源后，可以在多个 Project 中复用同一份版本化内容。'
                  : undefined
              }
              emptyAction={canManage ? '创建共享资源' : null}
              onEmptyAction={canManage ? () => setCreating(true) : undefined}
            >
              <SharedResourceTable resources={ownResources.data ?? []} />
            </AsyncState>
          </PrimerListCard>
        )}

        {tab === 'platform' && (
          <PrimerListCard>
            <AsyncState
              loading={platformResources.loading}
              loadingText="正在加载共享资源…"
              error={normalizeError(platformResources.error)}
              empty={(platformResources.data ?? []).length === 0}
              emptyText="平台还没有公共共享资源。"
            >
              <SharedResourceTable resources={platformResources.data ?? []} />
            </AsyncState>
          </PrimerListCard>
        )}

        <CreateSharedResourceModal
          open={creating}
          workspaceId={workspace.id}
          onClose={() => setCreating(false)}
          onCreated={(resource) => {
            ownResources.reload()
            navigate(`/shared-resources/${resource.id}`)
          }}
        />
      </PrimerStack>
    </PrimerRoot>
  )
}
