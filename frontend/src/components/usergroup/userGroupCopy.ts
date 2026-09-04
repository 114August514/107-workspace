/**
 * User Group 页面壳层与分区导航 copy。
 *
 * 只持有稳定的用户可见文案；capability 判断仍来自服务端投影，
 * 动态名称留在调用点。成员治理文案见 memberCopy.ts。
 */
import type { MembershipRole } from '../../api/types'

const ROLE_LABEL: Record<MembershipRole, string> = {
  owner: '所有者',
  admin: '管理员',
  member: '成员',
}

export function userGroupRoleLabel(role: MembershipRole): string {
  return ROLE_LABEL[role]
}

export const userGroupPageCopy = {
  page: {
    loading: '正在加载 User Group…',
    fallbackDescription: '这个 User Group 还没有填写说明。',
    kind: 'User Group',
    headerLabel: 'User Group 身份',
    navLabel: 'User Group 分区导航',
  },
  overview: {
    viewAll: '查看全部',
    loading: '正在加载 Project…',
    emptyProjects: '这个 User Group 还没有 Project。',
    emptyDescription: '这个 Project 还没有填写说明。',
    truncated: 'Project 较多，仅展示前一部分；完整列表请查看全部。',
  },
  nav: {
    overview: 'Overview',
    projects: 'Project',
    sharedResources: 'Shared Resource',
    environments: 'Environment',
    members: 'Members',
    settings: 'Settings',
  },
  sections: {
    projects: {
      title: 'Project',
    },
    members: {
      title: '成员',
    },
    settings: {
      title: '设置',
      description: '修改 User Group 的名称与说明。',
    },
  },
  list: {
    searchProjects: '查找 Project…',
    searchSharedResources: '查找共享资源…',
    searchEnvironments: '查找运行环境…',
    countProjects: (count: number) => `${count} 个 Project`,
    countSharedResources: (count: number) => `${count} 个共享资源`,
    countEnvironments: (count: number) => `${count} 个运行环境`,
    noMatches: '没有匹配的条目。',
    loadingProjects: '正在加载 Project…',
    loadingSharedResources: '正在加载共享资源…',
    loadingEnvironments: '正在加载运行环境…',
    emptyProjects: '这个 User Group 还没有 Project。',
    emptyProjectsHint: '组拥有的 Project 会出现在这里。',
    emptySharedResources: '这个 User Group 还没有共享资源。',
    emptySharedResourcesHint: '组拥有的共享资源会出现在这里。',
    emptyEnvironments: '这个 User Group 还没有运行环境。',
    emptyEnvironmentsHint: '组拥有的运行环境会出现在这里。',
    truncatedProjects: '列表过长，仅显示前一部分 Project。',
    visibilityPublic: 'Public',
    visibilityOwnerScope: '仅成员可见',
    archived: '已归档',
    createdAt: (relative: string) => `创建于 ${relative}`,
    availableVersions: (available: number, total: number) => `${available}/${total} 个版本可用`,
    typeNavLabel: 'Type',
    types: {
      all: 'All',
      contributed: 'Contributed by me',
      admin: 'Admin access',
      public: 'Public',
      sources: 'Sources',
      forks: 'Forks',
      archived: 'Archived',
      templates: 'Templates',
    },
  },
} as const
