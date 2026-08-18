export const appShellCopy = {
  brand: '107 Workspace',
  openNavigation: '打开导航',
  createUserGroup: '创建 User Group',
  drawerTitle: '107 Workspace',
  sidebarLabel: '首页工作入口',
  navigationLoading: '正在加载工作入口…',
  navigationError: '工作入口加载失败。',
  navigationErrorNextStep: '请检查网络连接后重试。',
} as const

export const contextGuideCopy = {
  ariaLabel: '页面引导',
  home: '从最近的 Project 或 User Group 开始；进入 Project 后可选择版本发起 Run。',
  userGroup: '在这里管理成员，并进入关联的 Project 与配置；协作内容保留在各自对象中。',
  personalResource: '这里保留已有个人资源；进入 Project 后可继续查看文件、版本和 Run。',
  project: '当前工作区文件是 Working State；创建 Project 版本后形成不可变快照，并可据此发起 Run。',
  version: '这是不可变的 Project 版本；可以比较、派生 Project，或基于它发起 Run。',
  run: '这里展示当前 Run 的状态、日志和产物；后续修改不会回写其运行快照。',
} as const

export const workNavigationCopy = {
  ariaLabel: '工作入口',
  heading: '工作入口',
  home: '首页',
  userGroupGroup: 'User Group',
  userGroupEmpty: '还没有可进入的 User Group',
  personalResourceGroup: '个人资源',
  recentProjectsGroup: '最近使用的 Project',
  recentProjectsEmpty: '还没有最近使用的 Project',
} as const
