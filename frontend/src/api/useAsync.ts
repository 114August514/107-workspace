/** 极简数据加载钩子。够用就好，不引入额外的数据层依赖。 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from './client'

export interface AsyncState<T> {
  data: T | undefined
  loading: boolean
  error: ApiError | Error | undefined
  reload: (options?: { silent?: boolean }) => Promise<void>
}

/**
 * 加载一次数据，并提供 reload。
 *
 * `deps` 变化时自动重新加载。组件卸载后不再 setState，避免 React 警告。
 */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | Error>()
  const alive = useRef(true)
  const dataRef = useRef<T | undefined>(undefined)
  const loaderRef = useRef(loader)
  const requestId = useRef(0)
  loaderRef.current = loader

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  const reload = useCallback(async (options: { silent?: boolean } = {}) => {
    const currentRequest = ++requestId.current
    const silent = options.silent === true && dataRef.current !== undefined
    if (!silent) {
      setLoading(true)
      setError(undefined)
    }

    try {
      const result = await loaderRef.current()
      if (alive.current && currentRequest === requestId.current) {
        dataRef.current = result
        setData(result)
        setError(undefined)
      }
    } catch (exc) {
      // 后台轮询失败不应把仍然可用的页面替换成错误状态。
      if (alive.current && currentRequest === requestId.current && !silent) {
        setError(exc as Error)
      }
    } finally {
      if (alive.current && currentRequest === requestId.current) {
        setLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    void reload()
    // loader 通过 ref 传递，依赖只看调用方声明的 deps。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, reload])

  return { data, loading, error, reload }
}

/**
 * 按固定间隔轮询，直到 `stop` 返回 true。
 *
 * Run 状态来自调度系统，前端只能轮询——这也是为什么每次轮询前会先触发一次
 * 后端的状态同步。
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number,
  active: boolean,
): void {
  const saved = useRef(callback)
  saved.current = callback

  useEffect(() => {
    if (!active) return
    let cancelled = false
    let timer: number | undefined

    const poll = async () => {
      await saved.current()
      if (!cancelled) timer = window.setTimeout(poll, intervalMs)
    }

    timer = window.setTimeout(poll, intervalMs)
    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [intervalMs, active])
}
