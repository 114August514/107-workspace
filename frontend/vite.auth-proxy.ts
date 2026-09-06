import http from 'node:http'
import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'

export const UNAUTHORIZED_API_BODY =
  '{"code":"authentication_required","message":"需要登录。","problems":[],"request_id":""}'
export const FORBIDDEN_API_BODY =
  '{"code":"permission_denied","message":"请求来源不被允许。","problems":[],"request_id":""}'

const IDENTITY_HEADERS = ['x-user', 'x-user-id', 'x-user-provider', 'x-user-name', 'x-user-email']

export function requestPath(url: string | undefined): string {
  return (url ?? '/').split('?')[0] ?? '/'
}

export function isAuthRoute(url: string | undefined): boolean {
  const path = requestPath(url)
  return path === '/login' || path === '/login/password' || path === '/logout'
}

export function isBackendApiRoute(url: string | undefined): boolean {
  const path = requestPath(url)
  return path === '/api' || path.startsWith('/api/')
}

function jsonResponse(res: ServerResponse, status: number, body: string): void {
  res.writeHead(status, {
    'content-type': 'application/json',
    'cache-control': 'no-store',
  })
  res.end(body)
}

function authOrigin(): string {
  return process.env.WORKSPACE107_AUTH_ORIGIN ?? 'http://127.0.0.1:8108'
}

function backendOrigin(): string {
  return process.env.WORKSPACE107_BACKEND_ORIGIN ?? 'http://127.0.0.1:8000'
}

function stripIdentityHeaders(headers: http.OutgoingHttpHeaders): http.OutgoingHttpHeaders {
  const next: http.OutgoingHttpHeaders = { ...headers }
  for (const name of IDENTITY_HEADERS) {
    delete next[name]
  }
  return next
}

function pipeProxy(
  req: IncomingMessage,
  res: ServerResponse,
  targetOrigin: string,
  extraHeaders: http.OutgoingHttpHeaders = {},
): void {
  const target = new URL(req.url ?? '/', targetOrigin)
  // Strip client identity first, then apply proxy-injected headers.
  const headers = {
    ...stripIdentityHeaders({ ...req.headers, host: target.host }),
    ...extraHeaders,
  }
  const upstream = http.request(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port,
      path: `${target.pathname}${target.search}`,
      method: req.method,
      headers,
    },
    (response) => {
      res.writeHead(response.statusCode ?? 502, response.headers)
      response.pipe(res)
    },
  )
  upstream.on('error', () => {
    if (!res.headersSent) {
      res.writeHead(502, { 'content-type': 'text/plain', 'cache-control': 'no-store' })
    }
    res.end('bad gateway')
  })
  req.pipe(upstream)
}

function authSubrequest(
  req: IncomingMessage,
  origin: string,
): Promise<{ status: number; headers: http.IncomingHttpHeaders }> {
  return new Promise((resolve, reject) => {
    const target = new URL('/auth', origin)
    const upstream = http.request(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port,
        path: target.pathname,
        method: 'GET',
        headers: {
          host: target.host,
          cookie: req.headers.cookie ?? '',
          'x-original-method': req.method,
          origin: req.headers.origin ?? '',
          referer: req.headers.referer ?? '',
        },
      },
      (response) => {
        response.resume()
        resolve({ status: response.statusCode ?? 502, headers: response.headers })
      },
    )
    upstream.on('error', reject)
    upstream.end()
  })
}

async function handleDevAuthProxy(
  req: IncomingMessage,
  res: ServerResponse,
  next: () => void,
): Promise<void> {
  if (isAuthRoute(req.url)) {
    pipeProxy(req, res, authOrigin())
    return
  }
  if (!isBackendApiRoute(req.url)) {
    next()
    return
  }
  let auth: { status: number; headers: http.IncomingHttpHeaders }
  try {
    auth = await authSubrequest(req, authOrigin())
  } catch {
    if (!res.headersSent) {
      res.writeHead(502, { 'content-type': 'text/plain', 'cache-control': 'no-store' })
    }
    res.end('auth gateway unavailable')
    return
  }
  if (auth.status === 401) {
    jsonResponse(res, 401, UNAUTHORIZED_API_BODY)
    return
  }
  if (auth.status === 403) {
    jsonResponse(res, 403, FORBIDDEN_API_BODY)
    return
  }
  if (auth.status >= 400) {
    jsonResponse(
      res,
      502,
      '{"code":"bad_gateway","message":"认证服务不可用。","problems":[],"request_id":""}',
    )
    return
  }
  pipeProxy(req, res, backendOrigin(), {
    'x-user': '',
    'x-user-id': headerValue(auth.headers['x-user-id']),
    'x-user-provider': headerValue(auth.headers['x-user-provider']),
    'x-user-name': headerValue(auth.headers['x-user-name']),
    'x-user-email': '',
  })
}

function headerValue(value: string | string[] | undefined): string {
  if (Array.isArray(value)) {
    return value[0] ?? ''
  }
  return value ?? ''
}

export function authRequestProxy(): Plugin {
  return {
    name: 'workspace107-auth-request-proxy',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        void handleDevAuthProxy(req, res, next).catch(next)
      })
    },
  }
}
