import { PlusIcon } from '@primer/octicons-react'
import { Button, UnderlineNav } from '@primer/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { LegacyWorkspaceContext, OwnerReference, SharedResource } from '../../api/types'
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
  const owner = {
    kind: workspace.kind === 'personal' ? 'user' : 'user_group',
    id: workspace.kind === 'personal' ? workspace.owner_id : workspace.id,
  } satisfies OwnerReference
  const resources = useAsync<SharedResource[]>(() => api.listSharedResources(), [])
  const ownerResources = (resources.data ?? []).filter(
    (resource) => resource.owner.kind === owner.kind && resource.owner.id === owner.id,
  )
  const [creating, setCreating] = useState(false)
  const [tab, setTab] = useState('owner')

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
            aria-current={tab === 'owner' ? 'page' : undefined}
            onSelect={() => setTab('owner')}
          >
            此归属
          </UnderlineNav.Item>
          <UnderlineNav.Item
            aria-current={tab === 'all' ? 'page' : undefined}
            onSelect={() => setTab('all')}
          >
            全部可发现
          </UnderlineNav.Item>
        </UnderlineNav>

        {tab === 'owner' && (
          <PrimerListCard>
            <AsyncState
              loading={resources.loading}
              error={normalizeError(resources.error)}
              empty={ownerResources.length === 0}
              emptyText="此归属下还没有共享资源。"
              emptyDescription={
                canManage
                  ? '创建共享资源后，可以在多个 Project 中复用同一份版本化内容。'
                  : undefined
              }
              emptyAction={canManage ? '创建共享资源' : null}
              onEmptyAction={canManage ? () => setCreating(true) : undefined}
            >
              <SharedResourceTable resources={ownerResources} />
            </AsyncState>
          </PrimerListCard>
        )}

        {tab === 'all' && (
          <PrimerListCard>
            <AsyncState
              loading={resources.loading}
              error={normalizeError(resources.error)}
              empty={(resources.data ?? []).length === 0}
              emptyText="还没有可发现的共享资源。"
            >
              <SharedResourceTable resources={resources.data ?? []} />
            </AsyncState>
          </PrimerListCard>
        )}

        <CreateSharedResourceModal
          open={creating}
          owner={owner}
          onClose={() => setCreating(false)}
          onCreated={(resource) => {
            resources.reload()
            navigate(`/shared-resources/${resource.id}`)
          }}
        />
      </PrimerStack>
    </PrimerRoot>
  )
}
