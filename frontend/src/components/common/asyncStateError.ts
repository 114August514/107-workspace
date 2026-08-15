/**
 * 把 useAsync 返回的 `ApiError | Error | undefined` 拆成 AsyncState 要的归一化形状。
 *
 * ApiError 带 problems / requestId（提交前检查与服务端日志标识），
 * 普通异常只有 message——两者都能喂给同一个展示组件，调用方不用各自判一次类型。
 *
 * 没有错误时返回 undefined：AsyncState 用真值判断是否进入错误分支，
 * 返回 `{message:''}` 会被当成「有错误」而渲染空 Banner。
 *
 * 与 AsyncState 组件分文件存放：组件文件只导出组件，避免
 * react-refresh/only-export-components 告警。
 */
export function normalizeError(
  error: unknown,
): { message: string; problems?: string[]; requestId?: string } | undefined {
  if (!error) return undefined
  const err = error as Error & { problems?: string[]; requestId?: string }
  return {
    message: err.message || '请求失败',
    problems: err.problems,
    requestId: err.requestId,
  }
}
