export const homeCopy = {
  fallbackTitle: '首页',
  subtitle: '从这里进入 Project，配置运行方案，提交计算作业——不需要自己写 sbatch。',
  loading: '正在加载首页内容…',
  recentRuns: {
    title: '最近提交的 Run',
    empty: '还没有提交过 Run',
  },
  invitations: {
    title: '待处理邀请',
    loading: '正在加载邀请…',
    kind: '协作空间',
    accept: '接受邀请',
    reject: '拒绝',
    fallbackError: '请求失败。',
    fallbackNextStep: '请稍后重试。',
  },
  compute: {
    title: '算力方案目录',
    description: '提交 Run 时从中选择；实际可用以平台授权为准。',
    loading: '正在加载算力方案…',
    empty: '暂无算力方案',
    realtimeUnavailable: '当前暂不提供节点、分区和队列的实时状态。',
  },
} as const

export function homeTitle(displayName: string | undefined) {
  return displayName ? `${displayName}，欢迎回来` : homeCopy.fallbackTitle
}

export function invitationKind(role: string) {
  return `${homeCopy.invitations.kind} · ${role}`
}

export function invitationFailureTitle(name: string, message: string) {
  return `处理「${name}」的邀请失败：${message}`
}
