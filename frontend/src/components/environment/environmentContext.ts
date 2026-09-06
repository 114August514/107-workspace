import { createContext, useContext } from 'react'
import type { Environment, EnvironmentVersion } from '../../api/types'
import type { AsyncState } from '../../api/useAsync'

export interface EnvironmentDetail {
  environment: Environment
  version?: EnvironmentVersion
}
export const EnvironmentContext = createContext<AsyncState<EnvironmentDetail | null> | null>(null)
export function useCurrentEnvironment() {
  const context = useContext(EnvironmentContext)
  if (!context) throw new Error('EnvironmentProvider is required')
  return context
}
