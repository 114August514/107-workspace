import { describe, expect, it } from 'vitest'

import {
  describeComputeRequest,
  formatBytes,
  formatDuration,
  formatMemory,
  formatMinutes,
} from './format'

describe('formatBytes', () => {
  it('小于 1 KB 时按字节显示', () => {
    expect(formatBytes(0)).toBe('0 B')
    expect(formatBytes(512)).toBe('512 B')
  })

  it('逐级换算到更大的单位', () => {
    expect(formatBytes(2048)).toBe('2.0 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB')
    expect(formatBytes(3 * 1024 * 1024 * 1024)).toBe('3.0 GB')
  })
})

describe('formatDuration', () => {
  it('没有时长时显示占位符', () => {
    expect(formatDuration(null)).toBe('—')
    expect(formatDuration(undefined)).toBe('—')
  })

  it('按秒、分、小时分级显示', () => {
    expect(formatDuration(0.3)).toBe('< 1 秒')
    expect(formatDuration(45)).toBe('45 秒')
    expect(formatDuration(125)).toBe('2 分 5 秒')
    expect(formatDuration(7325)).toBe('2 小时 2 分')
  })
})

describe('formatMemory', () => {
  it('超过 1 GB 时换算成 GB', () => {
    expect(formatMemory(512)).toBe('512 MB')
    expect(formatMemory(4096)).toBe('4 GB')
  })
})

describe('formatMinutes', () => {
  it('时限用整分钟表达，不退化成「15 分 0 秒」', () => {
    expect(formatMinutes(15)).toBe('15 分钟')
    expect(formatMinutes(240)).toBe('4 小时')
    expect(formatMinutes(150)).toBe('2 小时 30 分钟')
  })
})

describe('describeComputeRequest', () => {
  it('没有 GPU 时不显示 GPU', () => {
    const text = describeComputeRequest({
      nodes: 1,
      cpus: 2,
      memory_mb: 4096,
      gpus: 0,
      time_limit_minutes: 15,
    })
    expect(text).toContain('1 节点')
    expect(text).toContain('2 核')
    expect(text).toContain('4 GB')
    expect(text).toContain('最长 15 分钟')
    expect(text).not.toContain('GPU')
  })

  it('有 GPU 时显示张数', () => {
    const text = describeComputeRequest({
      nodes: 1,
      cpus: 8,
      memory_mb: 32768,
      gpus: 2,
      time_limit_minutes: 240,
    })
    expect(text).toContain('2 张 GPU')
  })
})
