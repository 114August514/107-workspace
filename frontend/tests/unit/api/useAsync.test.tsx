// @vitest-environment jsdom

import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { useAsync } from '../../../src/api/useAsync'

describe('useAsync latest-wins', () => {
  it('ignores an older request resolving after reload', async () => {
    let resolveA!: (value: string) => void
    let resolveB!: (value: string) => void
    const loader = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<string>((resolve) => {
            resolveA = resolve
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<string>((resolve) => {
            resolveB = resolve
          }),
      )
    const { result } = renderHook(() => useAsync(loader, []))
    await waitFor(() => expect(loader).toHaveBeenCalledTimes(1))
    act(() => result.current.reload())
    await waitFor(() => expect(loader).toHaveBeenCalledTimes(2))
    act(() => resolveB('new'))
    await waitFor(() => expect(result.current.data).toBe('new'))
    act(() => resolveA('old'))
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(result.current.data).toBe('new')
    expect(result.current.loading).toBe(false)
  })

  it('ignores an older request rejecting after the latest succeeds', async () => {
    let rejectA!: (error: Error) => void
    let resolveB!: (value: string) => void
    const loader = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<string>((_, reject) => {
            rejectA = reject
          }),
      )
      .mockImplementationOnce(
        () =>
          new Promise<string>((resolve) => {
            resolveB = resolve
          }),
      )
    const { result } = renderHook(() => useAsync(loader, []))
    await waitFor(() => expect(loader).toHaveBeenCalledTimes(1))
    act(() => result.current.reload())
    await waitFor(() => expect(loader).toHaveBeenCalledTimes(2))
    act(() => resolveB('new'))
    await waitFor(() => expect(result.current.data).toBe('new'))
    act(() => rejectA(new Error('old failure')))
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(result.current.data).toBe('new')
    expect(result.current.error).toBeUndefined()
    expect(result.current.loading).toBe(false)
  })
})
