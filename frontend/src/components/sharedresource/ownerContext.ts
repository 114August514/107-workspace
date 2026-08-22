import { api } from '../../api/client'
import type { LegacyWorkspaceContext, SharedResourceDetail } from '../../api/types'

/** Resolve the legacy navigation/capability context for a canonical resource owner. */
export async function loadSharedResourceOwnerContext(
  resource: SharedResourceDetail,
): Promise<LegacyWorkspaceContext | undefined> {
  if (resource.owner.kind === 'user_group') {
    return api.getLegacyWorkspaceContext(resource.owner.id)
  }

  const home = await api.home()
  if (resource.owner.id !== home.user.id || !home.personal_resource_context_id) {
    return undefined
  }
  return api.getLegacyWorkspaceContext(home.personal_resource_context_id)
}
