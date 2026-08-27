// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AsyncState } from '../../src/components/common/AsyncState'
import { DesignSystemPage } from '../../src/pages/design-system/DesignSystemPage'
import { EMPTY_RECIPE } from '../../src/pages/design-system/model'
import { PrimerRoot } from '../../src/primer/setup'

const writeText = vi.fn<(value: string) => Promise<void>>()

// jsdom 没有 ResizeObserver，Primer Dialog 的 useOverflow 需要
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', ResizeObserverStub)
  writeText.mockReset()
  writeText.mockResolvedValue()
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('DesignSystemPage', () => {
  it('呈现为静态 Reference，不含任何 Playground 控制器', () => {
    render(
      <PrimerRoot>
        <DesignSystemPage />
      </PrimerRoot>,
    )

    expect(screen.getByRole('heading', { name: '107 Primer UI Reference' })).toBeInTheDocument()
    for (const section of [
      'Foundations',
      'Brand',
      'Marks',
      'Colors',
      'Icons',
      'States',
      'Patterns',
      'Content',
    ]) {
      expect(screen.getByRole('heading', { name: section })).toBeInTheDocument()
    }
    // 旧 Playground 的入口全部不存在
    expect(screen.queryByText('场景控制台')).not.toBeInTheDocument()
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '恢复默认值' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/预设$/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/参考画布$/)).not.toBeInTheDocument()
  })

  it('呈现最终 107 Brand Mark 及 16/24/32px 样本', () => {
    render(
      <PrimerRoot>
        <DesignSystemPage />
      </PrimerRoot>,
    )

    expect(screen.getByLabelText('107 Brand Mark TopBar 示例')).toHaveTextContent('107 Workspace')
    for (const size of [16, 24, 32]) {
      expect(screen.getByRole('img', { name: `107 Brand Mark，${size} 像素` })).toHaveAttribute(
        'width',
        String(size),
      )
    }
    expect(screen.getByText('16px（optical padding）')).toBeInTheDocument()

    expect(screen.getByText(/C100 M80 Y0 K0/)).toBeInTheDocument()
    expect(screen.getByLabelText('Primer semantic colors remain distinct')).toHaveTextContent(
      '继续由 Primer semantic tokens 负责',
    )
    expect(screen.getByLabelText('产品对象 Octicon mapping')).toBeInTheDocument()
    for (const subject of ['Project', 'User Group', 'Run', '共享资源', '通知', '设置', '创建']) {
      expect(screen.getByText(subject, { selector: 'strong' })).toBeInTheDocument()
    }
  })

  it('品牌 affordance 保持可访问名称与真实键盘焦点', () => {
    render(
      <PrimerRoot>
        <DesignSystemPage />
      </PrimerRoot>,
    )

    expect(screen.getByRole('link', { name: '品牌链接' })).toHaveAttribute(
      'href',
      '#brand-colors-heading',
    )
    expect(screen.getByRole('link', { name: '已选导航' })).toHaveAttribute('aria-current', 'page')
    const focusExample = screen.getByRole('button', { name: 'Focus 示例' })
    focusExample.focus()
    expect(focusExample).toHaveFocus()
    expect(screen.getByRole('button', { name: '主要操作' })).toBeEnabled()
  })

  it('六类状态无需任何操作即可直接查看', () => {
    render(
      <PrimerRoot>
        <DesignSystemPage />
      </PrimerRoot>,
    )

    expect(screen.getByText('正在加载共享资源…')).toBeInTheDocument()
    expect(screen.getAllByText('这里还没有共享资源。').length).toBeGreaterThan(0)
    expect(screen.getAllByText('文件预览失败。').length).toBeGreaterThan(0)
    expect(screen.getAllByText('版本已发布').length).toBeGreaterThan(0)
    expect(screen.getAllByText('无法发布这个版本。').length).toBeGreaterThan(0)
    for (const name of ['加载中', '空态', '错误', '成功', '权限', '危险操作']) {
      expect(screen.getByLabelText(`${name} 状态参考`)).toBeInTheDocument()
    }
  })

  it('危险确认 Dialog 可打开与取消', async () => {
    render(
      <PrimerRoot>
        <DesignSystemPage />
      </PrimerRoot>,
    )

    const trigger = screen.getAllByRole('button', { name: '删除 Project' })[0]
    if (!trigger) throw new Error('缺少危险操作触发按钮')
    fireEvent.click(trigger)

    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toHaveAccessibleName('删除 Project“mnist-train”？')
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
  })

  it('页头提供响应式返回入口与完整规范来源', () => {
    render(
      <PrimerRoot>
        <DesignSystemPage />
      </PrimerRoot>,
    )

    expect(screen.queryByText('Internal reference')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回产品' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: '107 Workspace' })).toHaveAttribute('href', '/')
    expect(screen.getByText('docs/product/ui-copy.md')).toBeInTheDocument()
    expect(screen.getByText('frontend/README.md')).toBeInTheDocument()
    expect(screen.getByText('docs/references/brand/ustc-vis.md')).toBeInTheDocument()
  })

  it('复制范例源码并反馈结果，2 秒后恢复可复制', async () => {
    vi.useFakeTimers()
    render(
      <PrimerRoot>
        <DesignSystemPage />
      </PrimerRoot>,
    )

    fireEvent.click(screen.getByRole('button', { name: '复制能力感知空态代码' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(writeText).toHaveBeenCalledWith(EMPTY_RECIPE)
    expect(screen.getByText('代码已复制')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100)
    })
    expect(screen.queryByText('代码已复制')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '复制能力感知空态代码' })).toBeInTheDocument()
    vi.useRealTimers()
  })
})

describe('AsyncState', () => {
  it('加载中只呈现动作描述', () => {
    render(
      <AsyncState loading loadingText="正在加载共享资源…">
        内容
      </AsyncState>,
    )

    expect(screen.getByText('正在加载共享资源…')).toBeInTheDocument()
    expect(screen.queryByText('加载中')).not.toBeInTheDocument()
    expect(screen.queryByText('内容')).not.toBeInTheDocument()
  })

  it('loadingText 渲染为可见加载文案', () => {
    render(
      <AsyncState loading loadingText="正在加载首页内容…">
        内容
      </AsyncState>,
    )

    expect(screen.getByText('正在加载首页内容…')).toBeVisible()
    expect(screen.getByRole('status')).toHaveTextContent('正在加载首页内容…')
  })

  it('错误逐条展示问题并次级保留请求标识', () => {
    const onRetry = vi.fn()
    render(
      <AsyncState
        loading={false}
        loadingText="正在加载共享资源…"
        error={{
          message: '无法发布这个版本。',
          problems: ['文件 list.txt 已存在', '说明过长'],
          requestId: 'req_01K2ZQ',
        }}
        onRetry={onRetry}
      >
        内容
      </AsyncState>,
    )

    expect(screen.getByText('无法发布这个版本。')).toBeInTheDocument()
    expect(screen.getByText('文件 list.txt 已存在')).toBeInTheDocument()
    expect(screen.getByText('说明过长')).toBeInTheDocument()
    expect(screen.getByRole('list')).toBeInTheDocument()
    expect(screen.getByText('请求标识 req_01K2ZQ')).toBeInTheDocument()
    const retry = screen.getByRole('button', { name: '重试' })
    fireEvent.click(retry)
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('单条下一步说明不渲染为列表', () => {
    render(
      <AsyncState
        loading={false}
        loadingText="正在加载共享资源…"
        error={{ message: '无法发布这个版本。', problems: ['请修正文件问题后重试。'] }}
      >
        内容
      </AsyncState>,
    )

    expect(screen.getByText('请修正文件问题后重试。')).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('空态显示说明，正常状态渲染内容', () => {
    const { rerender } = render(
      <AsyncState
        loading={false}
        loadingText="正在加载共享资源…"
        empty
        emptyText="这里还没有共享资源。"
      >
        内容
      </AsyncState>,
    )
    expect(screen.getByText('这里还没有共享资源。')).toBeInTheDocument()

    rerender(
      <AsyncState loading={false} loadingText="正在加载共享资源…">
        内容
      </AsyncState>,
    )
    expect(screen.getByText('内容')).toBeInTheDocument()
  })
})
