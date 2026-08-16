import { ApiError, NetworkError } from './client'

/**
 * 供展示组件消费的归一化错误数据。
 *
 * 不暴露原始异常类型、HTTP 状态或底层 transport message；
 * 只保留「用户可见主要提示」、「可执行下一步」和「次级诊断信息」。
 */
export interface AsyncErrorView {
  message: string
  problems?: string[]
  requestId?: string
}

/**
 * 把 API client 抛出的错误转成展示层可理解的形状。
 *
 * - 结构化 ApiError：保留后端已经写好的用户文案、问题列表和请求标识；
 * - NetworkError：给出稳定的「加载失败 + 检查网络后重试」文案；
 * - code === 'http_error' 的非结构化响应：给出中性的「请求失败 + 重试」文案，
 *   不暴露 HTTP 状态或原始 message，仅保留 requestId；
 * - 其它未知错误：不伪造原因，只给通用可重试提示。
 */
export function toAsyncError(error: Error | undefined): AsyncErrorView | undefined {
  if (!error) return undefined

  if (error instanceof NetworkError) {
    return {
      message: '无法加载内容。',
      problems: ['请检查网络连接后重试。'],
    }
  }

  if (error instanceof ApiError) {
    if (error.code === 'http_error') {
      return {
        message: '请求失败。',
        problems: ['请重试。'],
        requestId: error.requestId || undefined,
      }
    }
    return {
      message: error.message,
      problems: error.problems.length > 0 ? error.problems : undefined,
      requestId: error.requestId || undefined,
    }
  }

  return {
    message: '请求失败。',
    problems: ['请重试。'],
  }
}
