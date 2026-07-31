import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { LogChunk } from '../../api/types'
import { RunLogPanel } from './RunLogPanel'

function chunk(stream: 'stdout' | 'stderr', content: string): LogChunk {
  return { stream, content, truncated: false }
}

/** 当前选中的标签页。 */
function activeTab(): string {
  return document.querySelector('.ant-tabs-tab-active')?.textContent ?? ''
}

describe('RunLogPanel 默认停在哪一路输出', () => {
  it('失败的 Run 直接显示 stderr', () => {
    // 默认停在 stdout 的话，失败的 Run 打开是一片空白，
    // 报错在旁边那个标签页里——出问题的时候最不该让人多找一步
    render(
      <RunLogPanel
        chunks={[chunk('stdout', ''), chunk('stderr', 'ModuleNotFoundError: numpy')]}
        failed
      />,
    )

    expect(activeTab()).toBe('标准错误')
    expect(screen.getByText(/ModuleNotFoundError/)).toBeInTheDocument()
  })

  it('成功的 Run 停在 stdout', () => {
    render(<RunLogPanel chunks={[chunk('stdout', '训练完成'), chunk('stderr', '')]} />)

    expect(activeTab()).toBe('标准输出')
  })

  it('stdout 是空的就跳到有内容的那一路', () => {
    // 还没失败但 stdout 暂时没输出时，也不该让人看一个空页面
    render(<RunLogPanel chunks={[chunk('stdout', ''), chunk('stderr', '警告：显存不足')]} />)

    expect(activeTab()).toBe('标准错误')
  })

  it('两路都是空的也不报错', () => {
    render(<RunLogPanel chunks={[chunk('stdout', ''), chunk('stderr', '')]} />)

    expect(activeTab()).toBe('标准输出')
    expect(screen.getByText('这一路输出目前是空的')).toBeInTheDocument()
  })

  it('失败但 stderr 没内容时不要跳到空页面', () => {
    // 退出码非零、报错却打在 stdout 上，这种程序是有的
    render(
      <RunLogPanel chunks={[chunk('stdout', 'error: 配置文件缺失'), chunk('stderr', '')]} failed />,
    )

    expect(activeTab()).toBe('标准输出')
  })
})
