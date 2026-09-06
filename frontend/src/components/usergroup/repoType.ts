import { useSearchParams } from 'react-router-dom'

export const REPO_TYPE_FILTERS = [
  'all',
  'contributed',
  'admin',
  'public',
  'sources',
  'forks',
  'archived',
  'templates',
] as const

export type RepoTypeFilter = (typeof REPO_TYPE_FILTERS)[number]

export const PROJECT_TYPE_FILTERS = REPO_TYPE_FILTERS

/** Project 以外的组资产：没有 fork / archive / template 语义。 */
export const GROUP_ASSET_TYPE_FILTERS = [
  'all',
  'contributed',
  'admin',
  'public',
] as const satisfies readonly RepoTypeFilter[]

export const SHARED_RESOURCE_TYPE_FILTERS = GROUP_ASSET_TYPE_FILTERS

export const ENVIRONMENT_TYPE_FILTERS = GROUP_ASSET_TYPE_FILTERS

export interface RepoTypeFlags {
  contributed: boolean
  admin: boolean
  isPublic: boolean
  source: boolean
  fork: boolean
  archived: boolean
  template: boolean
}

export const DEFAULT_REPO_TYPE_FLAGS: RepoTypeFlags = {
  contributed: false,
  admin: false,
  isPublic: false,
  source: true,
  fork: false,
  archived: false,
  template: false,
}

export function parseRepoTypeFilter(value: string | null): RepoTypeFilter {
  if (value && (REPO_TYPE_FILTERS as readonly string[]).includes(value)) {
    return value as RepoTypeFilter
  }
  return 'all'
}

export function matchesRepoType(flags: RepoTypeFlags, type: RepoTypeFilter): boolean {
  switch (type) {
    case 'all':
      return true
    case 'contributed':
      return flags.contributed
    case 'admin':
      return flags.admin
    case 'public':
      return flags.isPublic
    case 'sources':
      return flags.source
    case 'forks':
      return flags.fork
    case 'archived':
      return flags.archived
    case 'templates':
      return flags.template
  }
}

export function useRepoTypeFilter(
  allowed: readonly RepoTypeFilter[] = REPO_TYPE_FILTERS,
): RepoTypeFilter {
  const [params] = useSearchParams()
  const parsed = parseRepoTypeFilter(params.get('type'))
  if (parsed === 'all' || allowed.some((type) => type === parsed)) return parsed
  return 'all'
}
