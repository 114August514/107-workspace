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
    breadcrumbLabel: '面包屑',
    headerLabel: 'User Group 身份',
    home: '首页',
    navLabel: 'User Group 分区导航',
  },
  nav: {
    overview: '概览',
    projects: 'Project',
    sharedResources: '共享资源',
    environments: '运行环境',
    members: '成员',
    settings: '设置',
  },
  sections: {
    overview: {
      title: '概览',
      description: 'User Group 的基本信息、近期活动与组拥有的资源。',
    },
    projects: {
      title: 'Project',
      description: '这个 User Group 拥有的 Project；详情与管理在 Project 页面打开。',
    },
    sharedResources: {
      title: '共享资源',
      description: '这个 User Group 拥有的共享资源；详情与版本在各自页面打开。',
    },
    environments: {
      title: '运行环境',
      description: '这个 User Group 拥有的运行环境；详情与版本在各自页面打开。',
    },
    members: {
      title: '成员',
    },
    settings: {
      title: '设置',
      description: '修改 User Group 的名称与说明。',
    },
  },
} as const
