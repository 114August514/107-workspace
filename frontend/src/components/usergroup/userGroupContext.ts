/**
 * 当前 User Group 的共享数据 context。
 *
 * 与组件分文件存放：本文件只导出类型/常量/hook，避免
 * react-refresh/only-export-components 告警（先例见 common/asyncStateError.ts）。
 */
import { createContext, useContext } from 'react'

import type { ApiError } from '../../api/client'
import type { UserGroup } from '../../api/types'

export interface CurrentUserGroup {
  userGroupId: string | undefined
  userGroup: UserGroup | undefined
  loading: boolean
  error: ApiError | Error | undefined
  reload: () => void
}

export const UserGroupContext = createContext<CurrentUserGroup | undefined>(undefined)

export function useCurrentUserGroup(): CurrentUserGroup {
  const context = useContext(UserGroupContext)
  if (!context) {
    throw new Error('useCurrentUserGroup 必须在 UserGroupProvider 内使用')
  }
  return context
}
