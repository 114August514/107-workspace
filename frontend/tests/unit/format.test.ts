import { describe, expect, it } from 'vitest'

import { formatDuration, formatTimelineTime } from '../../src/utils/format'

describe('formatDuration', () => {
  it('does not append zero-valued lower units', () => {
    expect(formatDuration(60)).toBe('1 分钟')
    expect(formatDuration(1_080)).toBe('18 分钟')
    expect(formatDuration(3_600)).toBe('1 小时')
  })

  it('keeps meaningful mixed units', () => {
    expect(formatDuration(61)).toBe('1 分 1 秒')
    expect(formatDuration(3_660)).toBe('1 小时 1 分')
  })
})

describe('formatTimelineTime', () => {
  it('shows a second-precision clock time', () => {
    expect(formatTimelineTime('2026-08-15T08:09:10')).toBe('08:09:10')
    expect(formatTimelineTime(null)).toBe('—')
  })
})
