import { PlusIcon } from '@primer/octicons-react'
import { Button, UnderlineNav } from '@primer/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { SharedResource, Workspace } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { PrimerAsyncSection } from '../primer/PrimerAsyncSection'
import { PrimerListCard } from '../primer/PrimerListCard'
import { PrimerStack } from '../primer/PrimerStack'
import { CreateSharedResourceModal } from './CreateSharedResourceModal'
import { SharedResourceTable } from './SharedResourceTable'

interface Props {
  workspace: Workspace
}

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
    <PrimerStack gap="middle">
      {canManage && (
        <div>
          <Button variant="primary" leadingVisual={PlusIcon} onClick={() => setCreating(true)}>
            创建 Shared Resource
          </Button>
        </div>
      )}

      <UnderlineNav aria-label="Shared Resources">
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
          <PrimerAsyncSection
            loading={ownResources.loading}
            error={ownResources.error}
            empty={(ownResources.data ?? []).length === 0}
            emptyText="这个 Workspace 还没有 Shared Resource"
          >
            <SharedResourceTable resources={ownResources.data ?? []} />
          </PrimerAsyncSection>
        </PrimerListCard>
      )}

      {tab === 'platform' && (
        <PrimerListCard>
          <PrimerAsyncSection
            loading={platformResources.loading}
            error={platformResources.error}
            empty={(platformResources.data ?? []).length === 0}
            emptyText="平台还没有公共资源"
          >
            <SharedResourceTable resources={platformResources.data ?? []} />
          </PrimerAsyncSection>
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
  )
}
