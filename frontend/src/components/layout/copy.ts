export const appShellCopy = {
  brand: '107 Workspace',
  homeMarkLabel: '107 Workspace 首页',
  openNavigation: '打开导航',
  createUserGroup: '创建 User Group',
  sidebarLabel: '首页工作入口',
  projectContextLabel: '当前 Project',
  userGroupContextLabel: '当前 User Group',
  projectNavigationLabel: 'Project navigation',
  projectLoading: '正在加载 Project context…',
  projectError: 'Project context 加载失败，重试',
  files: 'Files',
  runs: 'Runs',
  settings: 'Settings',
} as const

export const globalNavigationCopy = {
  title: '107 Workspace',
  ariaLabel: '全局导航',
  heading: '全局导航',
  close: '关闭导航',
  home: '首页',
  environments: '运行环境',
  executionContext: '个人执行上下文',
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
  profile: '这里查看自己的身份信息、所属 User Group，并进入个人执行上下文。',
  executionContext:
    '这里管理发起 Run 的个人身份、算力权益与 User 配置；已有 Run Snapshot 不会被后续修改回写。',
  userGroup:
    '这里管理 User Group 的成员、设置和组拥有的 Project、共享资源与运行环境；资源详情在各自页面打开。',
  environment: '运行环境是独立的版本化资产；Run Configuration 保存后固定引用一个确定版本。',
  project: '当前工作区文件是 Working State；创建 Project 版本后形成不可变快照，并可据此发起 Run。',
  version: '这是不可变的 Project 版本；可以比较、派生 Project，或基于它发起 Run。',
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
