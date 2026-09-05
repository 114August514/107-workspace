import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, toApiError } from '../../../src/api/client'
import { toAsyncError } from '../../../src/api/errors'

/**
 * 错误信封的解析。
 *
 * **字段名对不对不用测**——`toApiError` 读的是契约里的 `ErrorOut`，
 * 后端改字段名会在 `pnpm run typecheck` 时报错。
 *
 * 这里守的是另一半：**响应体不是我们的信封时会怎样**。
 * 网关超时、nginx 直接返回 HTML、代理吞掉响应体，这些线上都会遇到，
 * 而且恰恰是出问题的时候——那时候更不能让前端自己也炸掉。
 */

function response(status: number, headers: Record<string, string> = {}): Response {
  return new Response(null, { status, headers })
}

describe('toApiError', () => {
  it('按信封字段还原错误', () => {
    const error = toApiError(
      {
        code: 'permission_denied',
        message: '需要「创建 Project」权限',
        problems: [],
        request_id: 'req_abc',
      },
      response(403),
    )

    expect(error.status).toBe(403)
    expect(error.code).toBe('permission_denied')
    expect(error.message).toBe('需要「创建 Project」权限')
    expect(error.requestId).toBe('req_abc')
  })

  it('提交前检查的多条问题逐条保留', () => {
    const error = toApiError(
      {
        code: 'preflight_rejected',
        message: '这次提交没通过检查',
        problems: ['没有可运行的版本', '算力超出方案上限'],
        request_id: '',
      },
      response(422),
    )

    expect(error.problems).toEqual(['没有可运行的版本', '算力超出方案上限'])
    // 只显示第一条会让用户来回试，detail 把它们一次说完
    expect(error.detail).toContain('算力超出方案上限')
  })

  it('信封里没有请求标识时退回响应头', () => {
    const error = toApiError(
      { code: 'x', message: 'y' },
      response(500, { 'X-Request-Id': 'req_h' }),
    )

    expect(error.requestId).toBe('req_h')
  })

  it('响应体不是信封时不当掉，仍然给出可读信息', () => {
    // nginx 的 502 页面：没有 code / message / request_id
    const error = toApiError(
      '<html>502 Bad Gateway</html>',
      response(502, { 'X-Request-Id': 'req_h' }),
    )

    expect(error.status).toBe(502)
    expect(error.code).toBe('http_error')
    expect(error.message).toContain('502')
    // 请求标识仍然要拿到——用户报问题时全靠它去查日志
    expect(error.requestId).toBe('req_h')
  })

  it('完全没有响应体也不抛异常', () => {
    const error = toApiError(undefined, response(500))

    expect(error.code).toBe('http_error')
    expect(error.problems).toEqual([])
    expect(error.requestId).toBe('')
  })

  it('信封字段类型不对时按缺失处理', () => {
    // 真遇到过：中间层把 problems 改成了字符串
    const error = toApiError(
      { code: 'x', message: 'y', problems: '不是数组', request_id: 123 },
      response(400),
    )

    expect(error.problems).toEqual([])
    expect(error.requestId).toBe('')
  })
})

describe('toAsyncError', () => {
  it('保留结构化 ApiError 的 message、problems 和 requestId', () => {
    const error = new ApiError(
      403,
      'permission_denied',
      '需要「创建 Project」权限',
      ['你不是这个 Workspace 的成员'],
      'req_abc',
    )

    expect(toAsyncError(error)).toEqual({
      message: '需要「创建 Project」权限',
      problems: ['你不是这个 Workspace 的成员'],
      requestId: 'req_abc',
    })
  })
})

describe('fetch transport wrapper', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('把 fetch 网络失败归一化为 NetworkError 并保留 cause', async () => {
    const cause = new TypeError('Failed to fetch')
    const OriginalRequest = globalThis.Request
    vi.stubGlobal(
      'Request',
      class extends OriginalRequest {
        constructor(input: RequestInfo | URL, init?: RequestInit) {
          if (typeof input === 'string' && input.startsWith('/') && !input.startsWith('//')) {
            super(new URL(input, 'http://localhost:5173'), init)
          } else {
            super(input, init)
          }
        }
      },
    )
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(cause))

    // 清除模块缓存，使 client.ts 在 Request stub 生效后重新实例化 openapi-fetch。
    vi.resetModules()
    const { api, NetworkError } = await import('../../../src/api/client')

    await expect(api.home()).rejects.toSatisfy((error: unknown) => {
      if (!(error instanceof NetworkError)) return false
      expect(error.code).toBe('network_unavailable')
      expect(error.cause).toBe(cause)
      return true
    })
  })

  it('将删除端点的 404 解析为目标不存在结果', async () => {
    const OriginalRequest = globalThis.Request
    vi.stubGlobal(
      'Request',
      class extends OriginalRequest {
        constructor(input: RequestInfo | URL, init?: RequestInit) {
          if (typeof input === 'string' && input.startsWith('/') && !input.startsWith('//')) {
            super(new URL(input, 'http://localhost:5173'), init)
          } else {
            super(input, init)
          }
        }
      },
    )
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: 'not_found', message: '不存在', problems: [] }), {
          status: 404,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    vi.resetModules()
    const { api } = await import('../../../src/api/client')
    await expect(api.deleteProject('project_missing')).resolves.toBe('absent')
  })

  it('删除端点的权限错误不会被当作已删除', async () => {
    const OriginalRequest = globalThis.Request
    vi.stubGlobal(
      'Request',
      class extends OriginalRequest {
        constructor(input: RequestInfo | URL, init?: RequestInit) {
          if (typeof input === 'string' && input.startsWith('/') && !input.startsWith('//')) {
            super(new URL(input, 'http://localhost:5173'), init)
          } else {
            super(input, init)
          }
        }
      },
    )
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ code: 'permission_denied', message: '无权限', problems: [] }),
            { status: 403, headers: { 'Content-Type': 'application/json' } },
          ),
        ),
    )

    vi.resetModules()
    const { api, ApiError } = await import('../../../src/api/client')
    await expect(api.deleteUserGroup('group_forbidden')).rejects.toSatisfy((error: unknown) => {
      return error instanceof ApiError && error.status === 403
    })
  })
})
