import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * Shared Resource 客户端函数的边界行为。
 *
 * 字段名、路径、参数对不对**不用在这里测**——它们由 `schema.d.ts` 在
 * typecheck 时把关，后端改了契约前端立刻编译失败。这里只守契约管不到的
 * 那一半：运行时怎么把前端的数据结构翻译成 HTTP 请求。
 *
 * 其中最值得守的是 `createSharedResourcePublicationAttempt`：它是前端唯一一处
 * multipart 上传。后端 `File(...)` 期待每个文件挂在 `files` 下、
 * `description` 是普通字段、`prefix` 走 query。openapi-fetch 把 FormData
 * 原样透传，浏览器补 boundary——所以只要 FormData 拼错了，文件就静默丢一个，
 * 而且只在用户真的点「发布」时才暴露。
 *
 * 测试在 Node 里跑，没有 document base URL，而 client 用 `baseUrl: ''`
 * 生成相对路径——这在浏览器里是对的，但 `new Request('/api/...')` 在 Node
 * 里会抛。openapi-fetch 在 `createClient()` 时就把 `globalThis.Request` /
 * `globalThis.fetch` 作为默认值抄走了，所以必须在导入 client **之前**替换
 * 全局量，再动态 import，让单例 client 用到替换后的版本。生产代码不动。
 */

const DUMMY_ORIGIN = 'http://test.local'
const requests: Request[] = []

const originalRequest = globalThis.Request

// 相对 URL 补一个 origin，让 Node 下的 `new Request('/api/...')` 不抛。
globalThis.Request = class extends originalRequest {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    const url =
      typeof input === 'string' && input.startsWith('/') ? `${DUMMY_ORIGIN}${input}` : input
    super(url as RequestInfo, init)
  }
} as typeof globalThis.Request

globalThis.fetch = vi.fn(async (input: RequestInfo | URL) => {
  const request = input instanceof Request ? input : new Request(input)
  requests.push(request.clone())
  // 文件内容端点后端以 text/plain 直返（见 schema.d.ts），其余端点返回 JSON。
  // 按路径分流，让 text/plain 的解析路径也能被测到——否则只 mock JSON 的话，
  // 缺 parseAs:'text' 这种运行时会炸的回归能在 CI 里悄悄通过。
  const pathname = new URL(request.url).pathname
  if (pathname.endsWith('/files/content')) {
    return new Response('import os\nprint(1)\n', {
      status: 200,
      headers: { 'Content-Type': 'text/plain', 'X-Request-Id': 'req_test' },
    })
  }
  // 空的成功响应：openapi-fetch 拿到 200 + 空 JSON body 即可，
  // 这里测的是请求侧的拼装，不关心返回值。
  return new Response('{}', {
    status: 200,
    headers: { 'Content-Type': 'application/json', 'X-Request-Id': 'req_test' },
  })
}) as typeof globalThis.fetch

// 必须在替换全局量之后再 import，这样 createClient() 抄走的是替换后的版本。
const { api } = await import('../../../src/api/client')

function lastRequest(): Request {
  const request = requests.at(-1)
  if (!request) throw new Error('没有捕获到请求——fetch 没被调用')
  return request
}

beforeEach(() => {
  requests.length = 0
})

describe('createSharedResourcePublicationAttempt', () => {
  it('每个文件挂在 files 下，description 作为普通字段', async () => {
    const files = [new File(['aaa'], 'a.txt'), new File(['bbb'], 'b.txt')]
    await api.createSharedResourcePublicationAttempt('res_1', {
      files,
      description: '首个版本',
    })

    expect(requests).toHaveLength(1)
    const request = lastRequest()
    expect(request.method).toBe('POST')
    const url = new URL(request.url)
    // 路径参数替换对了
    expect(url.pathname).toBe('/api/v1/shared-resources/res_1/versions')
    // 没有 prefix 时 query 不带 prefix
    expect(url.searchParams.has('prefix')).toBe(false)

    const form = await request.formData()
    expect(form.getAll('files')).toHaveLength(2)
    expect((form.get('files') as File).name).toBe('a.txt')
    expect(form.get('description')).toBe('首个版本')
  })

  it('prefix 走 query 而不是塞进 body', async () => {
    await api.createSharedResourcePublicationAttempt('res_1', {
      files: [new File(['x'], 'x.txt')],
      description: '',
      prefix: 'data/',
    })

    const request = lastRequest()
    const url = new URL(request.url)
    expect(url.searchParams.get('prefix')).toBe('data/')
    // FormData 里不应该出现 prefix 字段
    const form = await request.formData()
    expect(form.get('prefix')).toBeNull()
  })

  it('Content-Type 让浏览器带 multipart boundary，不写成 JSON', async () => {
    await api.createSharedResourcePublicationAttempt('res_1', {
      files: [new File(['x'], 'x.txt')],
      description: '',
    })

    const contentType = lastRequest().headers.get('Content-Type') ?? ''
    // openapi-fetch 识别到 FormData 后不设 Content-Type，留给浏览器补
    // multipart/form-data; boundary=...。关键是不能退化成 application/json，
    // 否则后端的 File(...) 解析不到文件。
    expect(contentType).not.toContain('application/json')
  })
})

describe('canonical Shared Resource API / getSharedResourceVersion', () => {
  it('actor discovery uses the canonical owner-scoped path', async () => {
    await api.listSharedResources()
    expect(new URL(lastRequest().url).pathname).toBe('/api/v1/shared-resources')
  })

  it('creation sends the explicit legal owner in the canonical request body', async () => {
    await api.createSharedResource({
      name: '权重',
      description: '',
      owner: { kind: 'user_group', id: 'grp_lab' },
    })

    const request = lastRequest()
    expect(request.method).toBe('POST')
    expect(new URL(request.url).pathname).toBe('/api/v1/shared-resources')
    expect(await request.json()).toEqual({
      name: '权重',
      description: '',
      owner: { kind: 'user_group', id: 'grp_lab' },
    })
  })

  it('版本详情和文件读取用各自的路径参数', async () => {
    await api.getSharedResourceVersion('ver_1')
    expect(new URL(lastRequest().url).pathname).toBe('/api/v1/shared-resource-versions/ver_1')

    await api.getSharedResourcePublicationAttempt('shrpa_1')
    expect(new URL(lastRequest().url).pathname).toBe(
      '/api/v1/shared-resource-publication-attempts/shrpa_1',
    )

    await api.readSharedResourceVersionFile('ver_1', 'data/train.py')
    const fileUrl = new URL(lastRequest().url)
    expect(fileUrl.pathname).toBe('/api/v1/shared-resource-versions/ver_1/files/content')
    // 路径作为 query 传递
    expect(fileUrl.searchParams.get('path')).toBe('data/train.py')
  })

  it('文件内容按 text/plain 解析成字符串，不被 JSON.parse 吞掉', async () => {
    // 后端这个端点直返纯文本（schema 里 200 是 text/plain:string）。
    // 缺 parseAs:'text' 时 openapi-fetch 会默认走 response.json()，
    // 对 `import os\n...` 这种内容直接抛 SyntaxError——所以这里既验证
    // 不抛，也验证拿到的是原始字符串而非被 JSON 解析过的值。
    const content = await api.readSharedResourceVersionFile('ver_1', 'train.py')
    expect(content).toBe('import os\nprint(1)\n')
  })
})
