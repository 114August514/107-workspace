/** 极简数据加载钩子。够用就好，不引入额外的数据层依赖。 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from './client'

export interface AsyncState<T> {
  data: T | undefined
  loading: boolean
  error: ApiError | Error | undefined
  reload: () => void
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
  const [tick, setTick] = useState(0)
  const alive = useRef(true)
  const loaderRef = useRef(loader)
  loaderRef.current = loader

  useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    setError(undefined)
    loaderRef
      .current()
      .then((result) => {
        if (alive.current) setData(result)
      })
      .catch((exc: Error) => {
        if (alive.current) setError(exc)
      })
      .finally(() => {
        if (alive.current) setLoading(false)
      })
    // loader 通过 ref 传递，依赖只看调用方声明的 deps。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((n) => n + 1), [])
  return { data, loading, error, reload }
}

/**
 * 按固定间隔轮询，直到 `stop` 返回 true。
 *
 * Run 状态来自调度系统，前端只能轮询——这也是为什么每次轮询前会先触发一次
 * 后端的状态同步。
 */
export function usePolling(callback: () => void, intervalMs: number, active: boolean): void {
  const saved = useRef(callback)
  saved.current = callback

  useEffect(() => {
    if (!active) return
    const timer = window.setInterval(() => saved.current(), intervalMs)
    return () => window.clearInterval(timer)
  }, [intervalMs, active])
}
