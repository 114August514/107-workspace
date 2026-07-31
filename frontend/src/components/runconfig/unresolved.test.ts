import { describe, expect, it } from 'vitest'

import { describeMissing, findMissingReferences } from './unresolved'

const HAS_NOTHING = { secrets: [], variables: [] }

describe('findMissingReferences', () => {
  it('Fork 过来的 Secret 引用在新空间里找不到', () => {
    // GR-407：表达式可以复制，值和访问权限留在源 Workspace
    const missing = findMissingReferences({ TOKEN: '${{ secrets.HF_TOKEN }}' }, HAS_NOTHING)

    expect(missing).toEqual([{ envName: 'TOKEN', kind: 'secret', name: 'HF_TOKEN' }])
  })

  it('本空间有同名 Secret 就不算缺', () => {
    const missing = findMissingReferences(
      { TOKEN: '${{ secrets.HF_TOKEN }}' },
      { secrets: ['HF_TOKEN'], variables: [] },
    )

    expect(missing).toEqual([])
  })

  it('Variable 同样判断', () => {
    const missing = findMissingReferences({ DATASET: '${{ vars.NAME }}' }, HAS_NOTHING)

    expect(missing).toEqual([{ envName: 'DATASET', kind: 'variable', name: 'NAME' }])
  })

  it('字面值不需要解析', () => {
    // 「跑不起来」和「写了个常量」是两回事，别把常量标成未解析
    expect(findMissingReferences({ EPOCHS: '5', MODE: 'train' }, HAS_NOTHING)).toEqual([])
  })

  it('容忍花括号里的空格', () => {
    const missing = findMissingReferences({ T: '${{  secrets.A  }}' }, HAS_NOTHING)
    expect(missing).toHaveLength(1)
  })

  it('长得像但不是引用的字符串按字面值处理', () => {
    // 后端 resolve_env 也只认完整匹配，两边要一致
    const missing = findMissingReferences(
      { A: 'prefix ${{ secrets.X }}', B: '${{ secrets.X }} suffix' },
      HAS_NOTHING,
    )
    expect(missing).toEqual([])
  })

  it('一条方案里缺多个会全部列出来', () => {
    const missing = findMissingReferences(
      { TOKEN: '${{ secrets.A }}', DATASET: '${{ vars.B }}', EPOCHS: '5' },
      HAS_NOTHING,
    )
    expect(missing).toHaveLength(2)
  })
})

describe('describeMissing', () => {
  it('说清楚是哪个环境变量引用了什么', () => {
    const text = describeMissing([{ envName: 'TOKEN', kind: 'secret', name: 'HF_TOKEN' }])
    expect(text).toBe('TOKEN 引用的 Secret HF_TOKEN')
  })
})
