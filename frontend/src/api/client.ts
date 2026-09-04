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
  EnvironmentPublicationAttempt,
  EnvironmentVersion,
  FileContent,
  Home,
  Invitation,
  LogChunk,
  Member,
  MembershipRole,
  NotificationPage,
  PreflightResult,
  PageQuery,
  ForkSource,
  OwnerReference,
  Project,
  ProjectPage,
  ProjectFile,
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
  SharedResourcePublicationAttempt,
  SharedResourceUpdate,
  SharedResourceVersionDetail,
  VersionDiff,
  WorkingChange,
  WorkingChangeDetail,
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
  environment: async (id: string): Promise<Environment> =>
    unwrap(
      await http.GET('/api/v1/catalog/environments/{environment_id}', {
        params: { path: { environment_id: id } },
      }),
    ),
  environmentVersion: async (id: string): Promise<EnvironmentVersion> =>
    unwrap(
      await http.GET('/api/v1/catalog/environment-versions/{version_id}', {
        params: { path: { version_id: id } },
      }),
    ),
  publishModulesEnvironment: async (
    id: string,
    body: { version: string; description: string; modules: string[] },
  ): Promise<EnvironmentPublicationAttempt> =>
    unwrap(
      await http.POST(
        '/api/v1/catalog/environments/{environment_id}/publication-attempts/modules',
        { params: { path: { environment_id: id } }, body },
      ),
    ),
  publishSifEnvironment: async (
    id: string,
    payload: {
      version: string
      sif: File
      source_uri: string
      source_digest: string
      architecture: 'x86_64'
    },
  ): Promise<EnvironmentPublicationAttempt> => {
    const form = new FormData()
    form.append('version', payload.version)
    form.append('sif', payload.sif)
    form.append('source_uri', payload.source_uri)
    form.append('source_digest', payload.source_digest)
    form.append('architecture', payload.architecture)
    form.append('description', '')
    return unwrap(
      await http.POST(
        '/api/v1/catalog/environments/{environment_id}/publication-attempts/apptainer-sif',
        {
          params: { path: { environment_id: id } },
          body: form as unknown as {
            version: string
            sif: string
            source_uri: string
            source_digest: string
            architecture: string
            description: string
          },
        },
      ),
    )
  },
  environmentPublicationAttempts: async (id: string): Promise<EnvironmentPublicationAttempt[]> =>
    unwrap(
      await http.GET('/api/v1/catalog/environments/{environment_id}/publication-attempts', {
        params: { path: { environment_id: id } },
      }),
    ),
  environmentPublicationAttempt: async (id: string): Promise<EnvironmentPublicationAttempt> =>
    unwrap(
      await http.GET('/api/v1/catalog/environment-publication-attempts/{attempt_id}', {
        params: { path: { attempt_id: id } },
      }),
    ),
  refreshEnvironmentAvailability: async (id: string): Promise<EnvironmentVersion> =>
    unwrap(
      await http.POST('/api/v1/catalog/environment-versions/{version_id}/availability/refresh', {
        params: { path: { version_id: id } },
      }),
    ),
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
    payload: {
      name?: string
      description?: string
    },
  ): Promise<UserGroup> =>
    unwrap(
      await http.PATCH('/api/v1/user-groups/{user_group_id}', {
        params: { path: { user_group_id: id } },
        body: payload,
      }),
    ),

  listMembers: async (id: string): Promise<Member[]> =>
    unwrap(
      await http.GET('/api/v1/user-groups/{user_group_id}/members', {
        params: { path: { user_group_id: id } },
      }),
    ),

  inviteMember: async (id: string, username: string): Promise<Member> =>
    unwrap(
      await http.POST('/api/v1/user-groups/{user_group_id}/members', {
        params: { path: { user_group_id: id } },
        body: { username },
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

  transferUserGroupOwnership: async (id: string, userId: string): Promise<void> => {
    unwrap(
      await http.POST('/api/v1/user-groups/{user_group_id}/transfer-ownership/{target_user_id}', {
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

  listEntitlements: async (): Promise<Entitlement[]> =>
    unwrap(await http.GET('/api/v1/me/entitlements')),

  // -- Project -----------------------------------------------------------
  listOwnerProjects: async (
    owner: OwnerReference,
    options: PageQuery & { query?: string } = {},
  ): Promise<ProjectPage> =>
    unwrap(
      await http.GET('/api/v1/projects', {
        params: {
          query: {
            ...options,
            owner_kind: owner.kind,
            owner_id: owner.id,
          },
        },
      }),
    ),

  createProject: async (
    payload: { owner: OwnerReference; name: string; description: string },
  ): Promise<Project> =>
    unwrap(
      await http.POST('/api/v1/projects', {
        body: { ...payload, visibility: 'owner_scope' },
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
      default_run_configuration_id?: string
    },
  ): Promise<Project> =>
    unwrap(
      await http.PATCH('/api/v1/projects/{project_id}', {
        params: { path: { project_id: id } },
        body: payload,
      }),
    ),

  environmentsForProject: async (id: string): Promise<Environment[]> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/environments', {
        params: { path: { project_id: id } },
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

  /**
   * multipart 上传。多选时调用方逐个文件调一次而不是一次打包全部：
   * 一个请求一个文件的成败，失败的用户才分得清是哪个文件出了问题。
   */
  uploadFiles: async (id: string, files: File[]): Promise<ProjectFile[]> => {
    const form = new FormData()
    for (const file of files) {
      form.append('files', file)
    }
    return unwrap(
      await http.POST('/api/v1/projects/{project_id}/files/upload', {
        params: { path: { project_id: id } },
        // 契约把 files 标成 string[]，实际是 File；理由同 publishSharedResourceVersion。
        body: form as unknown as { files: string[] },
      }),
    )
  },

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

  copyPath: async (id: string, source: string, destination: string): Promise<ProjectFile[]> =>
    unwrap(
      await http.POST('/api/v1/projects/{project_id}/files/copy', {
        params: { path: { project_id: id } },
        body: { source, destination },
      }),
    ),

  createDirectory: async (id: string, path: string): Promise<ProjectFile> =>
    unwrap(
      await http.POST('/api/v1/projects/{project_id}/files/mkdir', {
        params: { path: { project_id: id } },
        body: { path },
      }),
    ),

  /**
   * 上传 zip 压缩包并展开到工作区。
   *
   * 与 `publishSharedResourceVersion` 同理：契约类型把文件标成 string，
   * 这里实际是 File，FormData 由浏览器补 Content-Type 和 boundary。
   */
  uploadArchive: async (id: string, file: File, prefix = ''): Promise<ProjectFile[]> => {
    const form = new FormData()
    form.append('file', file)
    return unwrap(
      await http.POST('/api/v1/projects/{project_id}/files/archive', {
        params: {
          path: { project_id: id },
          query: prefix ? { prefix } : undefined,
        },
        body: form as unknown as { file: string },
      }),
    )
  },

  /**
   * 下载 Project 文件。
   *
   * 走 fetch 拿 blob 再触发浏览器下载，而不是直接给 `<a href>`——
   * 请求要带身份头，理由同 `downloadArtifactFile`。
   */
  downloadFile: async (id: string, path: string): Promise<void> => {
    const blob = unwrap(
      await http.GET('/api/v1/projects/{project_id}/files/download', {
        params: { path: { project_id: id }, query: { path } },
        parseAs: 'blob',
      }),
    )
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = path.split('/').pop() ?? 'file'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },

  // -- 版本 --------------------------------------------------------------
  workingChanges: async (id: string): Promise<WorkingChange[]> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/changes', {
        params: { path: { project_id: id } },
      }),
    ),

  workingChangeDetail: async (id: string, path: string): Promise<WorkingChangeDetail> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/changes/detail', {
        params: { path: { project_id: id }, query: { path } },
      }),
    ),

  /** 放弃指定未保存变更，返回剩余的未保存变更。 */
  discardChanges: async (id: string, paths: string[]): Promise<WorkingChange[]> =>
    unwrap(
      await http.POST('/api/v1/projects/{project_id}/changes/discard', {
        params: { path: { project_id: id } },
        body: { paths },
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

  listProjectVariables: async (projectId: string): Promise<{ name: string; value: string }[]> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/variables', {
        params: { path: { project_id: projectId } },
      }),
    ),

  listProjectSecrets: async (projectId: string): Promise<string[]> =>
    unwrap(
      await http.GET('/api/v1/projects/{project_id}/secrets', {
        params: { path: { project_id: projectId } },
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

  readArtifactFile: async (id: string, path: string): Promise<Blob> =>
    unwrap(
      await http.GET('/api/v1/artifacts/{artifact_id}/download', {
        params: { path: { artifact_id: id }, query: { path } },
        parseAs: 'blob',
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
   * Upload a Shared Resource publication candidate.
   *
   * The 202 response is a durable attempt, not a Version. Callers must read the attempt
   * until it succeeds or fails before treating any version as published.
   */
  createSharedResourcePublicationAttempt: async (
    resourceId: string,
    payload: { files: File[]; description: string; prefix?: string },
  ): Promise<SharedResourcePublicationAttempt> => {
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

  getSharedResourcePublicationAttempt: async (
    attemptId: string,
    signal?: AbortSignal,
  ): Promise<SharedResourcePublicationAttempt> =>
    unwrap(
      await http.GET('/api/v1/shared-resource-publication-attempts/{attempt_id}', {
        params: { path: { attempt_id: attemptId } },
        signal,
      }),
    ),

  getSharedResourceVersion: async (
    versionId: string,
    signal?: AbortSignal,
  ): Promise<SharedResourceVersionDetail> =>
    unwrap(
      await http.GET('/api/v1/shared-resource-versions/{version_id}', {
        params: { path: { version_id: versionId } },
        signal,
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
    payload: {
      target_owner: { kind: 'user' | 'user_group'; id: string }
      name?: string
      description?: string
    },
  ): Promise<Project> =>
    unwrap(
      await http.POST('/api/v1/versions/{version_id}/fork', {
        params: { path: { version_id: versionId } },
        body: {
          target_owner: payload.target_owner,
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
  listUserGroupActivities: async (id: string, query: PageQuery = {}): Promise<ActivityPage> =>
    unwrap(
      await http.GET('/api/v1/user-groups/{user_group_id}/activities', {
        params: { path: { user_group_id: id }, query },
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
