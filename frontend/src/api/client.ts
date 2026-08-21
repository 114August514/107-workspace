/**
 * 后端 API 客户端。
 *
 * 底层是 openapi-fetch，泛型参数来自生成的 `paths`。这意味着：
 * 路径写错、路径参数漏传、query 参数名拼错、请求体字段不对，
 * 全都是**编译期错误**，不用等到运行时才发现。
 *
 * 上层保留一组按领域命名的函数，组件不必关心 HTTP 细节；
 * 但每个函数内部都走类型检查过的调用，不存在「手写字符串路径」这种东西。
 *
 * 开发模式下用 X-User 请求头识别身份（后端 auth_mode=dev）。
 * 接入学校统一身份认证之后，改这里的中间件即可，调用方不用动。
 */

import createClient, { type Middleware } from 'openapi-fetch'

import type { paths } from './schema'
import type {
  ActivityPage,
  ApiErrorBody,
  ArtifactEntry,
  ComputePlan,
  Entitlement,
  Environment,
  FileContent,
  Home,
  Invitation,
  LegacyWorkspaceContext,
  LogChunk,
  Member,
  MembershipRole,
  NotificationPage,
  PreflightResult,
  PageQuery,
  ForkSource,
  Project,
  ProjectFile,
  ProjectPage,
  ProjectVersion,
  ProjectVersionPage,
  ProjectVersionDetail,
  Run,
  RunConfiguration,
  RunConfigurationInput,
  RunDetail,
  RunDraft,
  RunPage,
  SharedResource,
  SharedResourceCreate,
  SharedResourceDetail,
  SharedResourceUpdate,
  SharedResourceVersion,
  SharedResourceVersionDetail,
  Variable,
  VersionDiff,
  WorkingChange,
  UserGroup,
} from './types'

/** 后端统一的错误响应结构。 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly problems: string[]
  /** 服务端这次请求的标识。报问题时带上它，运维能直接查到对应日志。 */
  readonly requestId: string

  constructor(status: number, code: string, message: string, problems: string[], requestId = '') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.problems = problems
    this.requestId = requestId
  }

  /** 提交前检查失败时会带回多条问题，展示时应当逐条列出。 */
  get detail(): string {
    return this.problems.length > 0 ? this.problems.join('\n') : this.message
  }
}

/**
 * 底层 fetch 无法建立连接时（后端未启动、代理失败、DNS/网络中断）
 * 抛出的类型化错误。message 仅供内部调试，UI copy 由 toAsyncError 按上下文决定。
 */
export class NetworkError extends Error {
  readonly code = 'network_unavailable'

  constructor(cause: unknown) {
    super('Network request failed', { cause })
    this.name = 'NetworkError'
  }
}

/**
 * 为一次提交意图生成幂等键。
 *
 * 重试同一次意图时要复用同一个键；用户真的想再跑一次时才换新键。
 * 换句话说：键标识的是「意图」，不是「点击」。
 */
export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID()
  }
  // 非安全上下文下没有 randomUUID，退化成时间戳加随机数，够用。
  return `key-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

let currentUser = 'student'

export function setCurrentUser(username: string): void {
  currentUser = username
}

export function getCurrentUser(): string {
  return currentUser
}

const identity: Middleware = {
  onRequest({ request }) {
    request.headers.set('X-User', currentUser)
    return request
  },
}

/**
 * 包装全局 fetch，把 fetch 层 reject 的异常统一转成 NetworkError。
 * 收到响应（包括 4xx/5xx）时不进入 catch，交给 openapi-fetch 正常解析；
 * 任何导致 fetch Promise reject 的底层错误（连接失败、DNS、CORS、中断等）
 * 都会被捕获并带上原始 cause。
 */
const safeFetch: typeof fetch = async (input, init) => {
  try {
    return await globalThis.fetch(input, init)
  } catch (cause) {
    throw new NetworkError(cause)
  }
}

const http = createClient<paths>({ baseUrl: '', fetch: safeFetch })
http.use(identity)

/** 把 openapi-fetch 的 `{ data, error }` 转成「成功返回值 / 抛 ApiError」。 */
function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined) {
    throw toApiError(result.error, result.response)
  }
  return result.data as T
}

export function toApiError(body: unknown, response: Response): ApiError {
  const fallback = `请求失败（HTTP ${response.status}）`
  // 响应头一定有；响应体在极端情况下（网关直接返回）可能没有。
  const headerId = response.headers.get('X-Request-Id') ?? ''

  if (body && typeof body === 'object') {
    // 字段名来自契约里的 ErrorOut，不是照着后端代码抄的。
    // 后端给字段改名，这里会在 typecheck 时报错；手写字符串键的话
    // 只会静默读出 undefined，然后错误信息就一直是那句兜底文案。
    //
    // 运行时判断仍然保留：网关或代理返回的响应体不一定是我们的信封。
    const envelope = body as Partial<ApiErrorBody>
    return new ApiError(
      response.status,
      typeof envelope.code === 'string' ? envelope.code : 'http_error',
      typeof envelope.message === 'string' ? envelope.message : fallback,
      Array.isArray(envelope.problems) ? envelope.problems : [],
      typeof envelope.request_id === 'string' && envelope.request_id
        ? envelope.request_id
        : headerId,
    )
  }
  return new ApiError(response.status, 'http_error', fallback, [], headerId)
}

export const api = {
  // -- 首页与目录 --------------------------------------------------------
  home: async (): Promise<Home> => unwrap(await http.GET('/api/v1/me')),
  environments: async (): Promise<Environment[]> =>
    unwrap(await http.GET('/api/v1/catalog/environments')),
  computePlans: async (): Promise<ComputePlan[]> =>
    unwrap(await http.GET('/api/v1/catalog/compute-plans')),

  // -- User Group governance -------------------------------------------
  listUserGroups: async (): Promise<UserGroup[]> => unwrap(await http.GET('/api/v1/user-groups')),

  getUserGroup: async (id: string): Promise<UserGroup> =>
    unwrap(
      await http.GET('/api/v1/user-groups/{user_group_id}', {
        params: { path: { user_group_id: id } },
      }),
    ),

  createUserGroup: async (name: string, description: string): Promise<UserGroup> =>
    unwrap(await http.POST('/api/v1/user-groups', { body: { name, description } })),

  updateUserGroup: async (
    id: string,
    payload: { name?: string; description?: string },
  ): Promise<UserGroup> =>
    unwrap(
      await http.PATCH('/api/v1/user-groups/{user_group_id}', {
        params: { path: { user_group_id: id } },
        body: payload,
      }),
    ),

  getLegacyWorkspaceContext: async (id: string): Promise<LegacyWorkspaceContext> =>
    unwrap(
      await http.GET('/api/v1/workspaces/{workspace_id}', {
        params: { path: { workspace_id: id } },
      }),
    ),

  setLegacyDefaultEnvironment: async (
    id: string,
    defaultEnvironmentVersionId: string | null,
  ): Promise<LegacyWorkspaceContext> =>
    unwrap(
      await http.PATCH('/api/v1/workspaces/{workspace_id}', {
        params: { path: { workspace_id: id } },
        body: { default_environment_version_id: defaultEnvironmentVersionId },
      }),
    ),

  listMembers: async (id: string): Promise<Member[]> =>
    unwrap(
      await http.GET('/api/v1/user-groups/{user_group_id}/members', {
        params: { path: { user_group_id: id } },
      }),
    ),

  inviteMember: async (id: string, username: string, role: MembershipRole): Promise<Member> =>
    unwrap(
      await http.POST('/api/v1/user-groups/{user_group_id}/members', {
        params: { path: { user_group_id: id } },
        body: { username, role },
      }),
    ),

  changeMemberRole: async (id: string, userId: string, role: MembershipRole): Promise<Member> =>
    unwrap(
      await http.PATCH('/api/v1/user-groups/{user_group_id}/members/{target_user_id}', {
        params: { path: { user_group_id: id, target_user_id: userId } },
        body: { role },
      }),
    ),

  removeMember: async (id: string, userId: string): Promise<void> => {
    unwrap(
      await http.DELETE('/api/v1/user-groups/{user_group_id}/members/{target_user_id}', {
        params: { path: { user_group_id: id, target_user_id: userId } },
      }),
    )
  },

  /** 我收到的、还没处理的邀请。 */
  listInvitations: async (): Promise<Invitation[]> => unwrap(await http.GET('/api/v1/invitations')),

  respondToInvitation: async (id: string, accept: boolean): Promise<void> => {
    unwrap(
      await http.POST('/api/v1/user-groups/{user_group_id}/invitation', {
        params: { path: { user_group_id: id } },
        body: { accept },
      }),
    )
  },

  listEntitlements: async (id: string): Promise<Entitlement[]> =>
    unwrap(
      await http.GET('/api/v1/workspaces/{workspace_id}/entitlements', {
        params: { path: { workspace_id: id } },
      }),
    ),

  listVariables: async (id: string): Promise<Variable[]> =>
    unwrap(
      await http.GET('/api/v1/workspaces/{workspace_id}/variables', {
        params: { path: { workspace_id: id } },
      }),
    ),

  setVariable: async (id: string, name: string, value: string): Promise<Variable> =>
    unwrap(
      await http.PUT('/api/v1/workspaces/{workspace_id}/variables', {
        params: { path: { workspace_id: id } },
        body: { name, value },
      }),
    ),

  deleteVariable: async (id: string, name: string): Promise<void> => {
    unwrap(
      await http.DELETE('/api/v1/workspaces/{workspace_id}/variables/{name}', {
        params: { path: { workspace_id: id, name } },
      }),
    )
  },

  /** 只返回名称。Secret 的值没有任何读取接口（docs/product/design.md 第 3.1.4 节）。 */
  listSecretNames: async (id: string): Promise<string[]> =>
    unwrap(
      await http.GET('/api/v1/workspaces/{workspace_id}/secrets', {
        params: { path: { workspace_id: id } },
      }),
    ),

  setSecret: async (id: string, name: string, value: string): Promise<void> => {
    unwrap(
      await http.PUT('/api/v1/workspaces/{workspace_id}/secrets', {
        params: { path: { workspace_id: id } },
        body: { name, value },
      }),
    )
  },

  deleteSecret: async (id: string, name: string): Promise<void> => {
    unwrap(
      await http.DELETE('/api/v1/workspaces/{workspace_id}/secrets/{name}', {
        params: { path: { workspace_id: id, name } },
      }),
    )
  },

  // -- Project -----------------------------------------------------------
  listProjects: async (workspaceId: string, query: PageQuery = {}): Promise<ProjectPage> =>
    unwrap(
      await http.GET('/api/v1/workspaces/{workspace_id}/projects', {
        params: { path: { workspace_id: workspaceId }, query },
      }),
    ),

  createProject: async (workspaceId: string, name: string, description: string): Promise<Project> =>
    unwrap(
      await http.POST('/api/v1/workspaces/{workspace_id}/projects', {
        params: { path: { workspace_id: workspaceId } },
        body: { name, description },
      }),
    ),

  getProject: async (id: string): Promise<Project> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}', { params: { path: { project_id: id } } }),
    ),

  updateProject: async (
    id: string,
    payload: {
      name?: string
      description?: string
      environment_version_id?: string | null
      inherit_workspace_environment?: boolean
      default_run_configuration_id?: string
    },
  ): Promise<Project> =>
    unwrap(
      await http.PATCH('/api/v1/projects/{project_id}', {
        params: { path: { project_id: id } },
        body: payload,
      }),
    ),

  // -- 文件 --------------------------------------------------------------
  listFiles: async (id: string): Promise<ProjectFile[]> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/files', {
        params: { path: { project_id: id } },
      }),
    ),

  readFile: async (id: string, path: string): Promise<FileContent> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/files/content', {
        params: { path: { project_id: id }, query: { path } },
      }),
    ),

  writeFile: async (id: string, path: string, content: string): Promise<ProjectFile> =>
    unwrap(
      await http.PUT('/api/v1/projects/{project_id}/files', {
        params: { path: { project_id: id } },
        body: { path, content },
      }),
    ),

  deletePath: async (id: string, path: string): Promise<void> => {
    unwrap(
      await http.DELETE('/api/v1/projects/{project_id}/files', {
        params: { path: { project_id: id }, query: { path } },
      }),
    )
  },

  movePath: async (id: string, source: string, destination: string): Promise<ProjectFile[]> =>
    unwrap(
      await http.POST('/api/v1/projects/{project_id}/files/move', {
        params: { path: { project_id: id } },
        body: { source, destination },
      }),
    ),

  // -- 版本 --------------------------------------------------------------
  workingChanges: async (id: string): Promise<WorkingChange[]> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/changes', {
        params: { path: { project_id: id } },
      }),
    ),

  listVersions: async (id: string, query: PageQuery = {}): Promise<ProjectVersionPage> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/versions', {
        params: { path: { project_id: id }, query },
      }),
    ),

  getVersion: async (versionId: string): Promise<ProjectVersionDetail> =>
    unwrap(
      await http.GET('/api/v1/versions/{version_id}', {
        params: { path: { version_id: versionId } },
      }),
    ),

  diffVersions: async (versionId: string, base: string): Promise<VersionDiff[]> =>
    unwrap(
      await http.GET('/api/v1/versions/{version_id}/diff', {
        params: { path: { version_id: versionId }, query: { base } },
      }),
    ),
  readVersionFile: async (versionId: string, path: string): Promise<FileContent> =>
    unwrap(
      await http.GET('/api/v1/versions/{version_id}/files/content', {
        params: { path: { version_id: versionId }, query: { path } },
      }),
    ),

  saveVersion: async (id: string, message: string): Promise<ProjectVersion> =>
    unwrap(
      await http.POST('/api/v1/projects/{project_id}/versions', {
        params: { path: { project_id: id } },
        body: { message },
      }),
    ),

  restoreVersion: async (versionId: string): Promise<ProjectFile[]> =>
    unwrap(
      await http.POST('/api/v1/versions/{version_id}/restore', {
        params: { path: { version_id: versionId } },
      }),
    ),

  // -- 运行方案 ----------------------------------------------------------
  listRunConfigurations: async (projectId: string): Promise<RunConfiguration[]> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/run-configurations', {
        params: { path: { project_id: projectId } },
      }),
    ),

  createRunConfiguration: async (
    projectId: string,
    payload: RunConfigurationInput,
  ): Promise<RunConfiguration> =>
    unwrap(
      await http.POST('/api/v1/projects/{project_id}/run-configurations', {
        params: { path: { project_id: projectId } },
        body: payload,
      }),
    ),

  updateRunConfiguration: async (
    id: string,
    payload: RunConfigurationInput,
  ): Promise<RunConfiguration> =>
    unwrap(
      await http.PUT('/api/v1/run-configurations/{configuration_id}', {
        params: { path: { configuration_id: id } },
        body: payload,
      }),
    ),

  deleteRunConfiguration: async (id: string): Promise<void> => {
    unwrap(
      await http.DELETE('/api/v1/run-configurations/{configuration_id}', {
        params: { path: { configuration_id: id } },
      }),
    )
  },

  // -- Run ---------------------------------------------------------------
  preflight: async (projectId: string, draft: RunDraft): Promise<PreflightResult> =>
    unwrap(
      await http.POST('/api/v1/projects/{project_id}/runs/preflight', {
        params: { path: { project_id: projectId } },
        body: draft,
      }),
    ),

  /**
   * 提交 Run。
   *
   * `idempotencyKey` 用于把「同一次提交意图的重试」和「用户真的想再跑一次」
   * 区分开：同一个键重复提交返回上一次的结果，不会真的再跑一遍。
   * 调用方应当为一次提交意图生成一个键，并在重试时复用它。
   */
  createRun: async (projectId: string, draft: RunDraft, idempotencyKey?: string): Promise<Run> =>
    unwrap(
      await http.POST('/api/v1/projects/{project_id}/runs', {
        params: {
          path: { project_id: projectId },
          header: { 'Idempotency-Key': idempotencyKey ?? null },
        },
        body: draft,
      }),
    ),

  listRuns: async (projectId: string, query: PageQuery = {}): Promise<RunPage> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/runs', {
        params: { path: { project_id: projectId }, query },
      }),
    ),

  getRun: async (id: string): Promise<RunDetail> =>
    unwrap(await http.GET('/api/v1/runs/{run_id}', { params: { path: { run_id: id } } })),

  readLogs: async (id: string): Promise<LogChunk[]> =>
    unwrap(await http.GET('/api/v1/runs/{run_id}/logs', { params: { path: { run_id: id } } })),

  cancelRun: async (id: string): Promise<Run> =>
    unwrap(await http.POST('/api/v1/runs/{run_id}/cancel', { params: { path: { run_id: id } } })),

  rerun: async (id: string, idempotencyKey?: string): Promise<Run> =>
    unwrap(
      await http.POST('/api/v1/runs/{run_id}/rerun', {
        params: {
          path: { run_id: id },
          header: { 'Idempotency-Key': idempotencyKey ?? null },
        },
      }),
    ),

  syncRuns: async (): Promise<{ changed: number }> => unwrap(await http.POST('/api/v1/runs/sync')),

  // -- Artifact ----------------------------------------------------------
  listArtifactFiles: async (id: string): Promise<ArtifactEntry[]> =>
    unwrap(
      await http.GET('/api/v1/artifacts/{artifact_id}/files', {
        params: { path: { artifact_id: id } },
      }),
    ),

  /**
   * 下载 Artifact 文件。
   *
   * 走 fetch 而不是直接给 `<a href>`，因为下载同样需要带上身份请求头——
   * 否则浏览器会用默认身份去取，拿到 404。
   */
  downloadArtifactFile: async (id: string, path: string): Promise<void> => {
    const blob = unwrap(
      await http.GET('/api/v1/artifacts/{artifact_id}/download', {
        params: { path: { artifact_id: id }, query: { path } },
        parseAs: 'blob',
      }),
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = path.split('/').pop() ?? 'artifact'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },

  // -- 共享资源 ----------------------------------------------------------
  listSharedResources: async (): Promise<SharedResource[]> =>
    unwrap(await http.GET('/api/v1/shared-resources')),

  getSharedResource: async (id: string): Promise<SharedResourceDetail> =>
    unwrap(
      await http.GET('/api/v1/shared-resources/{resource_id}', {
        params: { path: { resource_id: id } },
      }),
    ),

  createSharedResource: async (payload: SharedResourceCreate): Promise<SharedResource> =>
    unwrap(
      await http.POST('/api/v1/shared-resources', {
        body: payload,
      }),
    ),

  updateSharedResource: async (
    id: string,
    payload: SharedResourceUpdate,
  ): Promise<SharedResource> =>
    unwrap(
      await http.PATCH('/api/v1/shared-resources/{resource_id}', {
        params: { path: { resource_id: id } },
        body: payload,
      }),
    ),

  /**
   * 发布 Shared Resource 新版本。
   *
   * 后端是 multipart/form-data：每个文件挂在 `files` 下，`description` 是普通
   * 字段，`prefix` 走 query。openapi-fetch 的默认序列化器会把 FormData 原样
   * 透传，浏览器自动补 Content-Type 和 boundary——所以这里手动构造 FormData。
   *
   * 契约里 `files` 的类型是 `string[]`（openapi-typescript 对 UploadFile 的
   * 近似），但运行时放的是 File 对象，所以这一处要 cast。
   */
  publishSharedResourceVersion: async (
    resourceId: string,
    payload: { files: File[]; description: string; prefix?: string },
  ): Promise<SharedResourceVersion> => {
    const form = new FormData()
    for (const file of payload.files) {
      form.append('files', file)
    }
    form.append('description', payload.description)
    return unwrap(
      await http.POST('/api/v1/shared-resources/{resource_id}/versions', {
        params: {
          path: { resource_id: resourceId },
          query: payload.prefix ? { prefix: payload.prefix } : undefined,
        },
        // 见上面注释：契约类型把 files 标成 string[]，这里实际是 File。
        body: form as unknown as {
          description: string
          files: string[]
        },
      }),
    )
  },

  getSharedResourceVersion: async (versionId: string): Promise<SharedResourceVersionDetail> =>
    unwrap(
      await http.GET('/api/v1/shared-resource-versions/{version_id}', {
        params: { path: { version_id: versionId } },
      }),
    ),

  /**
   * 读版本内单个文件的文本内容（后端以 text/plain 直返）。
   *
   * 必须显式 `parseAs: 'text'`：openapi-fetch 默认按 JSON 解析响应体，
   * 而这里后端返回的是纯文本——不写的话普通文本会被 `JSON.parse` 直接抛
   * SyntaxError，恰好长得像 JSON 的文件（`123`、`true`、`[1,2]`）则会被
   * 解析成数字/数组，静默返回错误类型。和 `downloadArtifactFile` 用
   * `parseAs: 'blob'` 是同一个道理。
   */
  readSharedResourceVersionFile: async (versionId: string, path: string): Promise<string> =>
    unwrap(
      await http.GET('/api/v1/shared-resource-versions/{version_id}/files/content', {
        params: { path: { version_id: versionId }, query: { path } },
        parseAs: 'text',
      }),
    ),

  /**
   * 按原始字节取版本内单个文件（图片预览走它）。
   *
   * `files/content` 以 text/plain 直出，二进制经它会被损坏；这里用
   * `parseAs: 'blob'` 拿原始字节，调用方再建 object URL 渲染或下载。
   */
  downloadSharedResourceVersionFile: async (versionId: string, path: string): Promise<Blob> =>
    unwrap(
      await http.GET('/api/v1/shared-resource-versions/{version_id}/files/download', {
        params: { path: { version_id: versionId }, query: { path } },
        parseAs: 'blob',
      }),
    ),

  // -- Fork --------------------------------------------------------------
  forkVersion: async (
    versionId: string,
    payload: { target_workspace_id: string; name?: string; description?: string },
  ): Promise<Project> =>
    unwrap(
      await http.POST('/api/v1/versions/{version_id}/fork', {
        params: { path: { version_id: versionId } },
        // 契约里这两项带默认值所以是必填。调用方省略时补空串，
        // 后端会沿用源 Project 的名称和说明。
        body: {
          target_workspace_id: payload.target_workspace_id,
          name: payload.name ?? '',
          description: payload.description ?? '',
        },
      }),
    ),

  /** 不是 Fork 出来的 Project 返回 null。 */
  forkSource: async (projectId: string): Promise<ForkSource | null> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/fork-source', {
        params: { path: { project_id: projectId } },
      }),
    ) ?? null,

  // -- 活动流 ------------------------------------------------------------
  listWorkspaceActivities: async (id: string, query: PageQuery = {}): Promise<ActivityPage> =>
    unwrap(
      await http.GET('/api/v1/workspaces/{workspace_id}/activities', {
        params: { path: { workspace_id: id }, query },
      }),
    ),

  listProjectActivities: async (id: string, query: PageQuery = {}): Promise<ActivityPage> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/activities', {
        params: { path: { project_id: id }, query },
      }),
    ),

  // -- 通知 ---------------------------------------------------------------
  listNotifications: async (
    query: PageQuery & { unread_only?: boolean } = {},
  ): Promise<NotificationPage> =>
    unwrap(await http.GET('/api/v1/notifications', { params: { query } })),

  unreadCount: async (): Promise<number> =>
    unwrap(await http.GET('/api/v1/notifications/unread-count')).unread,

  markNotificationRead: async (id: string): Promise<void> => {
    unwrap(
      await http.POST('/api/v1/notifications/{notification_id}/read', {
        params: { path: { notification_id: id } },
      }),
    )
  },

  markAllNotificationsRead: async (): Promise<void> => {
    unwrap(await http.POST('/api/v1/notifications/read-all'))
  },
}
