import { describe, expect, it } from 'vitest'

import {
  FORBIDDEN_API_BODY,
  UNAUTHORIZED_API_BODY,
  isAuthRoute,
  isBackendApiRoute,
  requestPath,
} from '../../vite.auth-proxy'

describe('dev auth proxy routes', () => {
  it('classifies login and logout as auth routes', () => {
    expect(isAuthRoute('/login')).toBe(true)
    expect(isAuthRoute('/login?id=abc')).toBe(true)
    expect(isAuthRoute('/login/password')).toBe(true)
    expect(isAuthRoute('/logout')).toBe(true)
    expect(isAuthRoute('/api/v1/me')).toBe(false)
    expect(isAuthRoute('/')).toBe(false)
  })

  it('classifies /api as backend routes that need auth_request', () => {
    expect(isBackendApiRoute('/api/v1/me')).toBe(true)
    expect(isBackendApiRoute('/api/v1/me?x=1')).toBe(true)
    expect(isBackendApiRoute('/login')).toBe(false)
    expect(isBackendApiRoute('/src/main.tsx')).toBe(false)
  })

  it('strips the query string when reading the path', () => {
    expect(requestPath('/login/password?x=1')).toBe('/login/password')
  })

  it('returns the same unauthenticated JSON as nginx auth_request', () => {
    expect(JSON.parse(UNAUTHORIZED_API_BODY)).toMatchObject({
      code: 'authentication_required',
    })
    expect(JSON.parse(FORBIDDEN_API_BODY)).toMatchObject({
      code: 'permission_denied',
    })
  })
})
