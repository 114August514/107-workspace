export const appShellCopy = {
  brand: '107 Workspace',
  openNavigation: '打开导航',
  createUserGroup: '创建 User Group',
  sidebarLabel: '首页工作入口',
} as const

export const globalNavigationCopy = {
  title: '107 Workspace',
  ariaLabel: '全局导航',
  heading: '全局导航',
  close: '关闭导航',
  home: '首页',
  environments: '运行环境',
  userGroupsGroup: '你的 User Group',
  userGroupsEmpty: '还没有可进入的 User Group',
  recentProjectsGroup: '最近使用的 Project',
  recentProjectsEmpty: '还没有最近使用的 Project',
  showRemaining: (count: number) => `显示其余 ${count} 个`,
  showRemainingUserGroups: (count: number) => `显示其余 ${count} 个 User Group`,
  showRemainingProjects: (count: number) => `显示其余 ${count} 个 Project`,
  loading: '正在加载全局导航…',
  error: '全局导航加载失败。',
  errorNextStep: '请检查网络连接后重试。',
} as const

export const contextGuideCopy = {
  ariaLabel: '页面引导',
  home: '从最近的 Project 或 User Group 开始；进入 Project 后可选择版本发起 Run。',
  userGroup: '这里管理 User Group 的成员与协作关系。Project、资源和运行配置在各自页面中管理。',
  environment: '运行环境是独立的版本化资产；Run Configuration 保存后固定引用一个确定版本。',
  project: '当前工作区文件是 Working State；创建 Project 版本后形成不可变快照，并可据此发起 Run。',
  version: '这是不可变的 Project 版本；可以比较、派生 Project，或基于它发起 Run。',
  run: '当前 Run 属于具体 Project；可以返回 Runs 查看同一 Project 的其他执行记录。',
} as const

export const workNavigationCopy = {
  ariaLabel: '工作入口',
  heading: '工作入口',
  home: '首页',
  userGroupGroup: 'User Group',
  userGroupEmpty: '还没有可进入的 User Group',
  recentProjectsGroup: '最近使用的 Project',
  recentProjectsEmpty: '还没有最近使用的 Project',
} as const
