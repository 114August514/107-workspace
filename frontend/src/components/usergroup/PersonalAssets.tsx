import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import { useAsync } from '../../api/useAsync'
import { formatRelative } from '../../utils/format'
import { RepoList } from './RepoList'
import { DEFAULT_REPO_TYPE_FLAGS } from './repoType'

export function PersonalAssets({
  kind,
  userId,
}: {
  kind: 'environments' | 'shared-resources'
  userId: string
}) {
  const label = kind === 'environments' ? '运行环境' : '共享资源'
  const assets = useAsync(async () => {
    const items =
      kind === 'environments' ? await api.environments() : await api.listSharedResources()
    return items
      .filter((item) => item.owner.kind === 'user' && item.owner.id === userId)
      .sort((a, b) => a.name.localeCompare(b.name, 'zh'))
  }, [kind, userId])
  return (
    <RepoList
      titleId="personal-assets-title"
      title={label}
      listLabel={`${label}列表`}
      searchPlaceholder={`搜索${label}`}
      countLabel={(count) => `${count} 个${label}`}
      noMatches="没有匹配的资源"
      loading={assets.loading}
      loadingText={`正在加载${label}…`}
      error={toAsyncError(assets.error)}
      onRetry={assets.reload}
      emptyText={`你还没有个人${label}`}
      emptyDescription="通过右上角创建菜单创建，并将所属范围选择为自己。"
      typeFilters={['all']}
      items={(assets.data ?? []).map((item) => ({
        id: item.id,
        name: item.name,
        description: item.description,
        to: `/${kind}/${item.id}`,
        types: DEFAULT_REPO_TYPE_FLAGS,
        meta:
          'created_at' in item
            ? `创建于 ${formatRelative(item.created_at)}`
            : `${item.versions.length} 个版本`,
      }))}
    />
  )
}
