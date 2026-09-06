import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'

import { api, ApiError, onUnauthorized } from '../api/client'
import type { Home, User } from '../api/types'
import type { AsyncState as AsyncResource } from '../api/useAsync'

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated' | 'error'

interface AuthValue {
  status: AuthStatus
  user: User | undefined
  home: AsyncResource<Home>
  error: Error | undefined
  retry: () => Promise<void>
}

const AuthContext = createContext<AuthValue | undefined>(undefined)

function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401
}

let inFlightHome: Promise<Home> | null = null

function fetchHome(): Promise<Home> {
  if (!inFlightHome) {
    inFlightHome = api.home().finally(() => {
      inFlightHome = null
    })
  }
  return inFlightHome
}

/** 测试用：丢弃跨用例泄漏的在途 /me 请求。 */
export function resetAuthFetchForTests(): void {
  inFlightHome = null
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading')
  const [homeData, setHomeData] = useState<Home>()
  const [homeLoading, setHomeLoading] = useState(true)
  const [homeError, setHomeError] = useState<Error>()
  const [sessionError, setSessionError] = useState<Error>()
  const generation = useRef(0)
  const statusRef = useRef(status)
  statusRef.current = status

  const clearSession = useCallback(() => {
    generation.current += 1
    inFlightHome = null
    setHomeData(undefined)
    setHomeError(undefined)
    setHomeLoading(false)
    setSessionError(undefined)
    setStatus('unauthenticated')
  }, [])

  const load = useCallback(
    async (options: { reset?: boolean } = {}) => {
      const request = ++generation.current
      const reset = options.reset === true || statusRef.current !== 'authenticated'
      if (reset) {
        setStatus('loading')
        setHomeData(undefined)
        setHomeError(undefined)
        setSessionError(undefined)
        setHomeLoading(true)
      } else {
        setHomeLoading(true)
        setHomeError(undefined)
      }

      try {
        const data = await fetchHome()
        if (request !== generation.current) return
        setHomeData(data)
        setHomeError(undefined)
        setSessionError(undefined)
        setStatus('authenticated')
      } catch (error) {
        if (request !== generation.current) return
        if (isUnauthorized(error)) {
          clearSession()
          return
        }
        const err = error as Error
        if (reset) {
          setHomeData(undefined)
          setSessionError(err)
          setStatus('error')
        } else {
          setHomeError(err)
        }
      } finally {
        if (request === generation.current) setHomeLoading(false)
      }
    },
    [clearSession],
  )

  useEffect(() => {
    return onUnauthorized(() => {
      clearSession()
    })
  }, [clearSession])

  useEffect(() => {
    void load({ reset: true })
  }, [load])

  useEffect(() => {
    const onPageShow = (event: Event) => {
      const persisted = 'persisted' in event && Boolean((event as PageTransitionEvent).persisted)
      if (persisted) void load({ reset: true })
    }
    window.addEventListener('pageshow', onPageShow)
    return () => window.removeEventListener('pageshow', onPageShow)
  }, [load])

  const reload = useCallback(() => load({ reset: false }), [load])
  const retry = useCallback(() => load({ reset: true }), [load])

  const home = useMemo<AsyncResource<Home>>(
    () => ({
      data: homeData,
      loading: homeLoading,
      error: homeError,
      reload,
    }),
    [homeData, homeLoading, homeError, reload],
  )

  const value = useMemo<AuthValue>(
    () => ({
      status,
      user: homeData?.user,
      home,
      error: sessionError,
      retry,
    }),
    [status, homeData, home, sessionError, retry],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error('useAuth 必须在 AuthProvider 内使用')
  }
  return value
}

export function startLogin(): void {
  window.location.assign('/login')
}

export function submitLogout(form: HTMLFormElement): void {
  form.submit()
}
