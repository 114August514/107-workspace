/**
 * 后端接口类型。
 *
 * **这里没有一行是手写的类型定义**——全部从 `schema.d.ts` 派生，
 * 而 `schema.d.ts` 由 `contracts/openapi.json` 生成，`openapi.json` 又由后端导出。
 *
 *     后端 DTO/路由 → openapi.json → schema.d.ts → 这里 → 组件
 *
 * 所以后端改一个字段，跑一次根目录的 `make contract`，
 * 前端所有受影响的地方会在 `pnpm run typecheck` 时全部报出来，
 * 而不是等到运行时才发现某个字段是 undefined。
 *
 * 这个文件只做两件事：给生成的类型起个符合领域语言的短名字
 * （见 docs/product/design.md 第 3.1 节），以及放几个纯前端的判断函数。
 * 想加新类型请先改后端，不要在这里手写。
 */

import type { components } from './schema'

type Schemas = components['schemas']

// -- 枚举 -------------------------------------------------------------------
// 这些在契约里带取值列表，所以派生出来是联合类型而不是 string。
// switch / Record 少写一个分支，TypeScript 会直接报错。

export type MembershipRole = Schemas['MembershipRole']
export type Capability = Schemas['Capability']
export type UserGroupCapability = Schemas['UserGroupCapability']
export type MembershipStatus = Schemas['MembershipStatus']
export type ProjectStatus = Schemas['ProjectStatus']
export type RunStatus = Schemas['RunStatus']
export type RunEventType = Schemas['RunEventType']
export type ArtifactStatus = Schemas['ArtifactStatus']
export type LogStream = Schemas['LogStream']
export type InputSourceType = Schemas['InputSourceType']
export type ChangeKind = Schemas['ChangeKind']

// -- Identity and User Group -------------------------------------------------

export type User = Schemas['UserOut']
export type UserGroup = Schemas['UserGroupOut']
export type Member = Schemas['MemberOut']
export type Invitation = Schemas['InvitationOut']
export type DeletionImpact = Schemas['DeletionImpactOut']
export type Variable = Schemas['VariableOut']
export type Secret = Schemas['SecretOut']
export type Entitlement = Schemas['EntitlementOut']

// -- Project ----------------------------------------------------------------

export type Project = Schemas['ProjectOut']
export type ProjectPage = Schemas['PageOut_ProjectOut_']
export type ProjectFile = Schemas['ProjectFileOut']
export type FileContent = Schemas['FileContentOut']
export type WorkingChange = Schemas['WorkingChangeOut']
export type WorkingChangeDetail = Schemas['WorkingChangeDetailOut']
export type ProjectVersion = Schemas['ProjectVersionOut']
export type ProjectVersionPage = Schemas['PageOut_ProjectVersionOut_']
export type ProjectVersionDetail = Schemas['ProjectVersionDetailOut']
export type ProjectVersionFile = Schemas['ProjectVersionFileOut']
export type VersionDiff = Schemas['VersionDiffOut']

// -- 运行环境与算力 ---------------------------------------------------------

export type Environment = Schemas['EnvironmentOut']
export type EnvironmentVersion = Schemas['EnvironmentVersionOut']
export type EnvironmentPublicationAttempt = Schemas['EnvironmentPublicationAttemptOut']
export type ComputePlan = Schemas['ComputePlanOut']
export type ComputeRequest = Schemas['ComputeRequestModel']
export type ResolvedScheduler = Schemas['ResolvedSchedulerOut']

// -- 共享资源 ---------------------------------------------------------------

export type OwnerKind = Schemas['OwnerKind']
export type OwnerReference = Schemas['OwnerReferenceIn']
export type OwnerSummary = Schemas['OwnerSummaryOut']
export type SharedResource = Schemas['SharedResourceOut']
export type SharedResourceDetail = Schemas['SharedResourceDetailOut']
export type SharedResourcePublicationAttempt = Schemas['SharedResourcePublicationAttemptOut']
export type SharedResourceVersion = Schemas['SharedResourceVersionOut']
export type SharedResourceVersionDetail = Schemas['SharedResourceVersionDetailOut']
export type SharedResourceVersionFile = Schemas['SharedResourceVersionFileOut']
export type SharedResourceCreate = Schemas['CanonicalSharedResourceCreateIn']
export type SharedResourceUpdate = Schemas['SharedResourceUpdateIn']
export type UseGrantSummary = Schemas['UseGrantSummaryOut']
export type Grant = Schemas['GrantOut']
export type SharedResourceUseQualification = SharedResource['use_qualifications'][number]

// -- 运行方案 ---------------------------------------------------------------

export type InputBinding = Schemas['InputBindingModel']
export type ArtifactRule = Schemas['ArtifactRuleModel']
export type RunConfiguration = Schemas['RunConfigurationOut']
export type RunConfigurationInput = Schemas['RunConfigurationIn']

// -- Run --------------------------------------------------------------------

export type RunDraft = Schemas['RunDraftIn']
export type PreflightResult = Schemas['PreflightOut']
export type Run = Schemas['RunOut']
export type RunPage = Schemas['PageOut_RunOut_']
export type RunEvent = Schemas['RunEventOut']
export type RunSnapshot = Schemas['RunSnapshotOut']
export type RunDetail = Schemas['RunDetailOut']
export type Artifact = Schemas['ArtifactOut']
export type ArtifactEntry = Schemas['ArtifactEntryOut']
export type LogChunk = Schemas['LogChunkOut']

// -- 活动 -------------------------------------------------------------------

export type Activity = Schemas['ActivityOut']
export type ActivityPage = Schemas['PageOut_ActivityOut_']
export type ActivityAction = Schemas['ActivityAction']
export type TargetType = Schemas['TargetType']

// -- 其他 -------------------------------------------------------------------

export type Home = Schemas['HomeOut']

// -- Fork -------------------------------------------------------------------

/** Project 的来源记录。名字是 Fork 那一刻抄下来的，源改名或删除后仍然读得通。 */
export type ForkSource = Schemas['ForkSourceOut']

// -- 通知 -------------------------------------------------------------------

export type Notification = Schemas['NotificationOut']
export type NotificationPage = Schemas['PageOut_NotificationOut_']
export type NotificationType = Schemas['NotificationType']

export type NotificationPreference = Schemas['NotificationPreferenceOut']
export type ApiErrorBody = Schemas['ErrorOut']

// -- 权限 -------------------------------------------------------------------

/** UI capability checks mirror the server-provided list; authorization remains server-side. */
export function can<T extends string>(
  context: { capabilities?: T[] } | undefined,
  capability: T,
): boolean {
  return context?.capabilities?.includes(capability) ?? false
}

// -- 分页 -------------------------------------------------------------------

/** 分页查询参数。省略时后端用默认值。 */
export interface PageQuery {
  page?: number
  page_size?: number
}

/**
 * 分页信封只用于「随时间单调增长」的历史类列表：Run、版本、Project。
 * 文件树、成员、运行方案这些由当前状态决定规模的列表直接返回数组——
 * 给它们套分页只会更难用。
 */
export type PageOf<T> = {
  items: T[]
  page: number
  page_size: number
  total: number
  has_more: boolean
}

// -- 纯前端的判断 -----------------------------------------------------------

export const TERMINAL_STATUSES = [
  'succeeded',
  'failed',
  'cancelled',
  'submit_failed',
] as const satisfies readonly RunStatus[]

export function isTerminal(status: RunStatus): boolean {
  return (TERMINAL_STATUSES as readonly RunStatus[]).includes(status)
}

export type EnvironmentPublicationOptions = Schemas['EnvironmentPublicationOptionsOut']
export type ImportEnvironmentPublicationInput = Schemas['ImportEnvironmentPublicationIn']
